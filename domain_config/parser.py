"""Markdown section splitter, table parser, and JSON extractor for GOAL.md.

Provides three utilities for the domain_config module:

- ``split_sections`` — splits raw GOAL.md text into its 9 named sections
  using a whitelist approach so embedded ``##`` headings are preserved.
- ``parse_table`` — converts a markdown table section into a list of
  Pydantic model instances (or a ``dict[str, str]`` for Layer Routing).
- ``extract_json`` — extracts and validates a JSON code block from the
  Output Schema section.

All functions are consumed by the higher-level GOAL.md file loader
(future task) to populate a ``GoalConfig`` instance.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from domain_config.models import GoalValidationError

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SEPARATOR_RE = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
"""Matches markdown table separator rows like ``|---|---|`` or ``| :---: | :---: |``."""


def _parse_row(line: str) -> list[str]:
    """Split a markdown table row on ``|`` and strip each cell.

    Handles rows with or without a trailing pipe.

    Returns:
        List of stripped cell values (leading/trailing empty cells from
        the outer pipes are removed).
    """
    stripped = line.strip()
    if not stripped:
        return []
    # Split on pipe
    cells = stripped.split("|")
    # Remove the empty strings caused by leading/trailing pipes
    # e.g., "| a | b |" -> ["", " a ", " b ", ""]
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.strip() for c in cells]


def _is_separator(line: str) -> bool:
    """Return True if *line* is a markdown table separator row."""
    return bool(_SEPARATOR_RE.match(line.strip()))


def _coerce_weight(raw: str) -> str:
    """Convert a percentage string like ``'25%'`` to a decimal string ``'0.25'``.

    If the value does not end with ``%``, return it unchanged so that
    Pydantic can attempt its own coercion (e.g., ``'0.5'``).
    """
    raw = raw.strip()
    if raw.endswith("%"):
        numeric = raw[:-1].strip()
        return str(float(numeric) / 100)
    return raw


def _coerce_required(raw: str) -> str:
    """Convert yes/no strings to ``'true'``/``'false'`` for Pydantic bool coercion."""
    normalised = raw.strip().lower()
    if normalised in ("yes", "y", "true", "1"):
        return "true"
    if normalised in ("no", "n", "false", "0"):
        return "false"
    return raw


_RANGE_NOTATION_RE = re.compile(r"^\d+\+")
"""Matches range notations like ``1+`` or ``0+`` at the start of a cell."""


def _coerce_valid_values(raw: str) -> list[str]:
    """Parse a comma-separated cell into a list of stripped strings.

    An empty or whitespace-only cell returns an empty list.
    Range notations like ``1+`` or ``0+`` return an empty list because
    they express constraints, not enumerations — the Pydantic model
    handles range validation.
    """
    stripped = raw.strip()
    if not stripped:
        return []
    if _RANGE_NOTATION_RE.match(stripped):
        return []
    return [v.strip() for v in stripped.split(",") if v.strip()]


# Mapping from model field name to the pre-processing coercion function.
_FIELD_COERCIONS: dict[str, Any] = {
    "weight": _coerce_weight,
    "required": _coerce_required,
    "valid_values": _coerce_valid_values,
}


# ---------------------------------------------------------------------------
# Section splitter — whitelist of the 9 known GOAL.md headings
# ---------------------------------------------------------------------------

_REQUIRED_SECTIONS: list[str] = [
    "Goal",
    "Source Documents",
    "System Prompt",
    "Generation Targets",
    "Generation Guidelines",
    "Evaluation Criteria",
    "Output Schema",
    "Metadata Schema",
    "Layer Routing",
]

# Regex matching only the 9 whitelisted section headings.
# Uses re.MULTILINE so ``^`` matches start of every line.
# Allows optional trailing whitespace after the heading name.
_SECTION_HEADING_RE = re.compile(
    r"^##\s+(" + "|".join(re.escape(name) for name in _REQUIRED_SECTIONS) + r")\s*$",
    re.MULTILINE,
)


def split_sections(content: str | Path) -> dict[str, str]:
    """Split GOAL.md content into named sections.

    Uses a whitelist approach: only the 9 known section headings are
    treated as boundaries.  Any other ``##`` headings found in the text
    are preserved as part of the enclosing section's body.

    Args:
        content: Raw markdown text of the GOAL.md file, **or** a
            ``pathlib.Path`` pointing to the file on disk.  When a
            ``Path`` is given, the file is read as UTF-8 text.

    Returns:
        Dict mapping section name to section body text (stripped).

    Raises:
        GoalValidationError: If any required section is missing, if
            the content is empty / contains no recognised headings,
            or if a ``Path`` is given and the file does not exist.
    """
    if isinstance(content, Path):
        if not content.exists():
            raise GoalValidationError(
                section="GOAL.md",
                message=f"File not found: {content}",
            )
        content = content.read_text(encoding="utf-8")

    matches = list(_SECTION_HEADING_RE.finditer(content))

    # --- Build dict from located headings ---
    sections: dict[str, str] = {}
    for idx, match in enumerate(matches):
        name = match.group(1)
        body_start = match.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        body = content[body_start:body_end].strip()
        sections[name] = body

    # --- Validate all 9 sections are present ---
    missing = [name for name in _REQUIRED_SECTIONS if name not in sections]
    if missing:
        missing_list = ", ".join(missing)
        if len(missing) == len(_REQUIRED_SECTIONS):
            raise GoalValidationError(
                section="GOAL.md",
                message=f"No sections found. Missing all required sections: {missing_list}",
            )
        raise GoalValidationError(
            section="GOAL.md",
            message=f"Missing required sections: {missing_list}",
        )

    return sections


# ---------------------------------------------------------------------------
# Public API — table parser and JSON extractor
# ---------------------------------------------------------------------------


def parse_table(
    section_body: str,
    model_class: type[BaseModel] | type[dict],
    column_map: dict[str, str],
) -> list[BaseModel] | dict[str, str]:
    """Parse a markdown table into a list of Pydantic model instances.

    For the special case where *model_class* is ``dict``, returns a
    ``dict[str, str]`` built from rows whose column_map maps headers to
    ``"key"`` and ``"value"``.

    Args:
        section_body: Raw section text containing a markdown table.
        model_class: Pydantic model class to instantiate per row, or
            ``dict`` for key/value tables (Layer Routing).
        column_map: Maps table column headers to model field names
            (or ``"key"``/``"value"`` for dict mode).

    Returns:
        List of validated model instances, or a ``dict[str, str]`` when
        *model_class* is ``dict``.
    """
    lines = [ln for ln in section_body.splitlines() if ln.strip()]

    if not lines:
        if model_class is dict:
            return {}
        return []

    # --- Locate the header row (first pipe-delimited line matching column_map) ---
    header_line_idx = None
    for i, ln in enumerate(lines):
        if "|" in ln and not _is_separator(ln):
            cells = _parse_row(ln)
            # Check if any cell matches a known column header
            if any(c.strip() in column_map for c in cells):
                header_line_idx = i
                break

    if header_line_idx is None:
        if model_class is dict:
            return {}
        return []

    header_cells = _parse_row(lines[header_line_idx])
    # Build an ordered mapping: column_index -> model_field_name
    col_index_to_field: dict[int, str] = {}
    for idx, header in enumerate(header_cells):
        header_stripped = header.strip()
        if header_stripped in column_map:
            col_index_to_field[idx] = column_map[header_stripped]

    # --- Process data rows (skip everything before header + separator) ---
    dict_result: dict[str, str] = {}
    model_results: list[BaseModel] = []

    for line in lines[header_line_idx + 1:]:
        if _is_separator(line):
            continue

        # Skip non-table lines (no pipes)
        if "|" not in line:
            continue

        cells = _parse_row(line)
        if not cells:
            continue

        # Build a raw kwargs dict from the row
        raw_kwargs: dict[str, Any] = {}
        for col_idx, field_name in col_index_to_field.items():
            if col_idx < len(cells):
                raw_value = cells[col_idx]
            else:
                raw_value = ""

            # Apply field-specific coercions
            coercion = _FIELD_COERCIONS.get(field_name)
            if coercion is not None:
                raw_kwargs[field_name] = coercion(raw_value)
            else:
                raw_kwargs[field_name] = raw_value

        if model_class is dict:
            key = raw_kwargs.get("key", "")
            value = raw_kwargs.get("value", "")
            if key:
                dict_result[key] = value
        else:
            instance = model_class(**raw_kwargs)
            model_results.append(instance)

    if model_class is dict:
        return dict_result

    return model_results


def extract_json(section_body: str) -> dict:
    """Extract and parse JSON from a markdown code block.

    Finds the first ````` ```json ````` fenced code block in *section_body*,
    extracts the content between the opening fence and the next ````` ``` `````
    closing fence, and parses it as JSON.

    The parsed dictionary is validated to contain the required top-level
    keys ``messages`` and ``metadata``.

    Args:
        section_body: Raw section text containing a ````` ```json ````` code fence.

    Returns:
        Parsed JSON as a dict.

    Raises:
        GoalValidationError: If no JSON block is found, the JSON is invalid,
            or required top-level keys are missing.
    """
    # Match the first ```json ... ``` block.
    # Use a non-greedy match and look for a closing ``` that starts at
    # the beginning of a line (after optional whitespace).
    pattern = r"```json\s*\n(.*?)(?:^|\n)\s*```"
    match = re.search(pattern, section_body, re.DOTALL)

    if match is None:
        raise GoalValidationError(
            section="Output Schema",
            message="No ```json code block found in section body.",
        )

    json_text = match.group(1).strip()

    if not json_text:
        raise GoalValidationError(
            section="Output Schema",
            message="The ```json code block is empty.",
        )

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise GoalValidationError(
            section="Output Schema",
            message=f"Malformed JSON in code block: {exc}",
        ) from exc

    if not isinstance(parsed, dict):
        raise GoalValidationError(
            section="Output Schema",
            message=f"Expected a JSON object (dict), got {type(parsed).__name__}.",
        )

    # Validate required top-level keys
    missing_keys = {"messages", "metadata"} - set(parsed.keys())
    if missing_keys:
        sorted_missing = sorted(missing_keys)
        raise GoalValidationError(
            section="Output Schema",
            message=f"Missing required top-level keys: {', '.join(sorted_missing)}.",
        )

    return parsed


# ---------------------------------------------------------------------------
# Public API — parse_goal_md
# ---------------------------------------------------------------------------

# Column maps for each table section, matching the GOAL.md schema.
_SOURCE_DOCS_COLUMN_MAP: dict[str, str] = {
    "File Pattern": "file_pattern",
    "Mode": "mode",
    "Notes": "notes",
}

_GENERATION_TARGETS_COLUMN_MAP: dict[str, str] = {
    "Category": "category",
    "Type": "type",
    "Count": "count",
}

_EVALUATION_CRITERIA_COLUMN_MAP: dict[str, str] = {
    "Criterion": "name",
    "Description": "description",
    "Weight": "weight",
}

_METADATA_SCHEMA_COLUMN_MAP: dict[str, str] = {
    "Field": "field",
    "Type": "type",
    "Required": "required",
    "Valid Values": "valid_values",
}

_LAYER_ROUTING_COLUMN_MAP: dict[str, str] = {
    "Layer": "key",
    "Destination": "value",
}


def parse_goal_md(goal_path: Path) -> GoalConfig:
    """Parse and validate a GOAL.md file.

    Orchestrates the full parsing pipeline:
    1. Read file from disk (raises GoalValidationError if not found)
    2. Split into 9 named sections
    3. Parse each section using the appropriate parser
    4. Construct a GoalConfig
    5. Run cross-section validation
    6. Return the validated config

    Args:
        goal_path: Path to the GOAL.md file on disk.

    Returns:
        Validated GoalConfig instance with all 9 sections populated.

    Raises:
        GoalValidationError: If the file is not found, is empty,
            has missing sections, contains malformed data, or fails
            any cross-section validation rule.
    """
    from domain_config.models import (
        EvaluationCriterion,
        GenerationTarget,
        GoalConfig,
        MetadataField,
        SourceDocument,
    )
    from domain_config.validators import validate_goal_config

    # Step 1-2: Read file and split into sections.
    # split_sections handles FileNotFoundError and empty-file cases.
    sections = split_sections(goal_path)

    # Step 3: Parse each section into its appropriate data structure.
    source_documents = parse_table(
        sections["Source Documents"],
        SourceDocument,
        _SOURCE_DOCS_COLUMN_MAP,
    )

    generation_targets = parse_table(
        sections["Generation Targets"],
        GenerationTarget,
        _GENERATION_TARGETS_COLUMN_MAP,
    )

    evaluation_criteria = parse_table(
        sections["Evaluation Criteria"],
        EvaluationCriterion,
        _EVALUATION_CRITERIA_COLUMN_MAP,
    )

    output_schema = extract_json(sections["Output Schema"])

    metadata_schema = parse_table(
        sections["Metadata Schema"],
        MetadataField,
        _METADATA_SCHEMA_COLUMN_MAP,
    )

    layer_routing = parse_table(
        sections["Layer Routing"],
        dict,
        _LAYER_ROUTING_COLUMN_MAP,
    )

    # Step 4: Construct GoalConfig using model_construct() to bypass
    # Pydantic field-level validators (min_length, Field(min_length=N)).
    # This allows validate_goal_config() in Step 5 to aggregate ALL
    # failures with proper section names rather than Pydantic failing
    # on the first constraint at model construction time.
    config = GoalConfig.model_construct(
        goal=sections["Goal"],
        source_documents=source_documents,
        system_prompt=sections["System Prompt"],
        generation_targets=generation_targets,
        generation_guidelines=sections["Generation Guidelines"],
        evaluation_criteria=evaluation_criteria,
        output_schema=output_schema,
        metadata_schema=metadata_schema,
        layer_routing=layer_routing,
    )

    # Step 5: Run cross-section validation (aggregates all failures).
    # This is the single point of validation — it checks all 10 rules
    # from DM-goal-schema.md and raises with all failures at once.
    validate_goal_config(sections, config)

    # Step 6: Return the validated config.
    return config
