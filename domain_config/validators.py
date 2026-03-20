"""Cross-section validation and error aggregation for GOAL.md configuration.

Validates the parsed GoalConfig against business rules that span across
sections, collecting ALL validation failures before raising a single
comprehensive GoalValidationError.

Validation rules (per DM-goal-schema.md):
1. Goal minimum 50 characters
2. System Prompt minimum 100 characters
3. Generation Guidelines minimum 100 characters
4. Source Documents at least 1 entry
5. Evaluation Criteria at least 3 criteria
6. Evaluation Criteria names are valid Python identifiers and not reserved keywords
7. Output Schema contains ``messages`` and ``metadata`` top-level keys
8. Metadata Schema all fields have ``required = True``
9. Layer Routing contains both ``behaviour`` and ``knowledge`` entries
10. Generation targets reasoning percentage >= 70%
"""

from __future__ import annotations

import keyword

from domain_config.models import GoalConfig, GoalValidationError


def _validate_min_length(
    section_name: str,
    text: str,
    min_chars: int,
    errors: list[tuple[str, str]],
) -> None:
    """Check that *text* meets the minimum character count for *section_name*."""
    if len(text) < min_chars:
        errors.append((
            section_name,
            f"Section must be at least {min_chars} characters (got {len(text)}).",
        ))


def _validate_source_documents(
    parsed: GoalConfig,
    errors: list[tuple[str, str]],
) -> None:
    """Rule 4: source_documents must have at least 1 entry."""
    if len(parsed.source_documents) < 1:
        errors.append((
            "Source Documents",
            "At least 1 source document entry is required.",
        ))


def _validate_evaluation_criteria(
    parsed: GoalConfig,
    errors: list[tuple[str, str]],
) -> None:
    """Rules 5-6: at least 3 criteria; names are valid identifiers, not keywords."""
    if len(parsed.evaluation_criteria) < 3:
        errors.append((
            "Evaluation Criteria",
            f"At least 3 evaluation criteria are required (got {len(parsed.evaluation_criteria)}).",
        ))

    for criterion in parsed.evaluation_criteria:
        if not criterion.name.isidentifier():
            errors.append((
                "Evaluation Criteria",
                f"Criterion name '{criterion.name}' is not a valid Python identifier.",
            ))
        elif keyword.iskeyword(criterion.name):
            errors.append((
                "Evaluation Criteria",
                f"Criterion name '{criterion.name}' must not be a Python reserved keyword.",
            ))


def _validate_output_schema(
    parsed: GoalConfig,
    errors: list[tuple[str, str]],
) -> None:
    """Rule 7: output_schema must contain ``messages`` and ``metadata`` keys."""
    missing_keys = {"messages", "metadata"} - set(parsed.output_schema.keys())
    if missing_keys:
        sorted_missing = sorted(missing_keys)
        errors.append((
            "Output Schema",
            f"Missing required top-level keys: {', '.join(sorted_missing)}.",
        ))


def _validate_metadata_schema(
    parsed: GoalConfig,
    errors: list[tuple[str, str]],
) -> None:
    """Rule 8: all metadata fields must have ``required = True``."""
    for mf in parsed.metadata_schema:
        if not mf.required:
            errors.append((
                "Metadata Schema",
                f"Field '{mf.field}' must have required=True.",
            ))


def _validate_layer_routing(
    parsed: GoalConfig,
    errors: list[tuple[str, str]],
) -> None:
    """Rule 9: layer_routing must contain both ``behaviour`` and ``knowledge``."""
    required_layers = {"behaviour", "knowledge"}
    missing_layers = required_layers - set(parsed.layer_routing.keys())
    if missing_layers:
        sorted_missing = sorted(missing_layers)
        errors.append((
            "Layer Routing",
            f"Missing required layer routing entries: {', '.join(sorted_missing)}.",
        ))


def _validate_reasoning_split(
    parsed: GoalConfig,
    errors: list[tuple[str, str]],
) -> None:
    """Rule 10: reasoning targets must be >= 70% of total count.

    Uses counts as authoritative (not percentages which are advisory).
    """
    total_count = sum(t.count for t in parsed.generation_targets)
    if total_count == 0:
        errors.append((
            "Generation Targets",
            "At least one generation target with count > 0 is required.",
        ))
        return

    reasoning_count = sum(
        t.count for t in parsed.generation_targets if t.type == "reasoning"
    )
    reasoning_pct = reasoning_count / total_count * 100

    if reasoning_pct < 70:
        errors.append((
            "Generation Targets",
            f"Reasoning targets must be at least 70% of total "
            f"(got {reasoning_pct:.1f}% — {reasoning_count}/{total_count}).",
        ))


def validate_goal_config(
    sections: dict[str, str],
    parsed: GoalConfig,
) -> None:
    """Run all validation rules and raise a single error with all failures.

    Validates the raw sections dict and the parsed GoalConfig against the
    10 business rules defined in DM-goal-schema.md. Collects ALL failures
    before raising, so the caller receives a comprehensive error report.

    Args:
        sections: Dict mapping section name to raw section body text,
            as produced by ``split_sections()``.
        parsed: Fully parsed GoalConfig instance, as built from
            ``parse_table()`` and ``extract_json()`` output.

    Returns:
        None if all validation rules pass.

    Raises:
        GoalValidationError: If any validation rule fails. The error
            has a ``failures`` attribute containing
            ``list[tuple[str, str]]`` with ``(section_name, message)``
            for every failing rule.
    """
    errors: list[tuple[str, str]] = []

    # Rules 1-3: Minimum character lengths — validated from raw sections
    # dict since Pydantic model-level validators may prevent construction
    # of GoalConfig with short text. Using sections allows aggregation of
    # ALL failures rather than failing at model construction time.
    _validate_min_length("Goal", sections.get("Goal", ""), 50, errors)
    _validate_min_length("System Prompt", sections.get("System Prompt", ""), 100, errors)
    _validate_min_length(
        "Generation Guidelines",
        sections.get("Generation Guidelines", ""),
        100,
        errors,
    )

    # Rule 4: Source Documents at least 1 entry
    _validate_source_documents(parsed, errors)

    # Rules 5-6: Evaluation Criteria count and identifier validation
    _validate_evaluation_criteria(parsed, errors)

    # Rule 7: Output Schema required keys
    _validate_output_schema(parsed, errors)

    # Rule 8: Metadata Schema required fields
    _validate_metadata_schema(parsed, errors)

    # Rule 9: Layer Routing required entries
    _validate_layer_routing(parsed, errors)

    # Rule 10: Reasoning split >= 70%
    _validate_reasoning_split(parsed, errors)

    if errors:
        # Build a comprehensive error message listing all failures
        failure_lines = [f"  [{section}] {msg}" for section, msg in errors]
        summary = (
            f"GOAL.md validation failed with {len(errors)} error(s):\n"
            + "\n".join(failure_lines)
        )
        err = GoalValidationError(
            section="GOAL.md",
            message=summary,
        )
        # Attach the structured failures list for programmatic access
        err.failures = errors
        raise err
