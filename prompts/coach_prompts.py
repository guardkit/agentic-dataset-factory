"""Coach agent prompt builder — base prompt constant and GOAL.md injection.

Constructs the Coach agent system prompt by combining a base instruction
prompt with domain-specific context extracted from a parsed GOAL.md file.

The base prompt defines the Coach's role (quality evaluator), structured JSON
response format, scoring guidance, and evaluation protocol.  GOAL.md sections
are appended as clearly delimited **domain context** so the base instructions
remain authoritative.

Required GOAL.md sections for the Coach prompt:
  1. Goal
  2. Evaluation Criteria
  3. Output Schema
  4. Metadata Schema
  5. Layer Routing
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domain_config.models import GoalConfig

# ---------------------------------------------------------------------------
# Base Prompt Constant
# ---------------------------------------------------------------------------

COACH_BASE_PROMPT: str = """\
You are a quality evaluator for training data generation.

## Role

Your task is to evaluate training examples produced by the Player agent.  \
You assess each example against the domain's evaluation criteria and return \
a structured JSON verdict.  You do NOT generate examples — you only evaluate.

## Response Format

For every evaluation, return a JSON object with the following structure:

```json
{
  "decision": "accept | revise",
  "score": 1,
  "layer_correct": true,
  "type_correct": true,
  "criteria_met": {
    "<criterion_name>": true
  },
  "issues": [
    {
      "criterion": "<criterion_name>",
      "severity": "blocking | minor",
      "description": "What is wrong",
      "suggestion": "How the Player should fix it"
    }
  ],
  "quality_assessment": "Free-text overall assessment"
}
```

## Field Definitions

- **decision**: "accept" if the example passes all quality gates; "revise" otherwise.
- **score**: Integer 1-5 overall quality score (1=poor, 3=adequate, 5=excellent).
- **layer_correct**: Whether the metadata layer classification is correct.
- **type_correct**: Whether the metadata type matches the presence/absence of \
a `<think>` block.
- **criteria_met**: A dict mapping each evaluation criterion name to a boolean.  \
You MUST include ALL criteria from the Evaluation Criteria section in this dict.
- **issues**: List of specific problems found (empty array if accepted).
- **quality_assessment**: Free-text overall assessment.

## Acceptance Rule

Accept an example when ALL of the following hold:
- decision == "accept"
- score >= 3
- layer_correct == true
- type_correct == true
- No issues with severity "blocking"

## Scoring Guidance

- **5 (Excellent)**: Meets all criteria, pedagogically strong, factually precise.
- **4 (Good)**: Meets all criteria with minor style or clarity improvements possible.
- **3 (Adequate)**: Meets minimum bar; acceptable for training but not exemplary.
- **2 (Below Standard)**: One or more criteria not met; needs revision.
- **1 (Poor)**: Multiple criteria failures; significant rework required.

## Critical Evaluation Standards

You MUST critically evaluate every criterion listed below. Do not accept by \
default. Your role is to be a rigorous gatekeeper, not a rubber stamp.

**High-score justification requirement:**
- A score of 4 or 5 requires explicit justification in your `quality_assessment` \
stating what was done well for EACH criterion. Generic praise like "good example" \
or "meets criteria" is not sufficient.
- If you cannot point to specific evidence in the example for each criterion, \
the score must be 3 or lower.

**Unverifiable criteria rule:**
- If you cannot verify a criterion because information is missing, ambiguous, \
or not present in the example, you MUST score 1-2 and set decision to "revise".
- Mark the unverifiable criterion as `false` in `criteria_met` and add an issue \
with severity "blocking" explaining what is missing.

## Bad Example: Shallow Acceptance (DO NOT do this)

The following is an example of a shallow, uncritical acceptance — exactly the \
kind of evaluation you must avoid:

```json
{
  "decision": "accept",
  "score": 5,
  "layer_correct": true,
  "type_correct": true,
  "criteria_met": {"socratic_approach": true, "factual_accuracy": true},
  "issues": [],
  "quality_assessment": "Good example. Meets all criteria."
}
```

**Why this is wrong:**
- The `quality_assessment` is vague — it does not explain what specifically was \
done well for each criterion.
- Score 5 (Excellent) was given without citing evidence from the example.
- The evaluator did not demonstrate that each criterion was individually checked.

**A proper score-5 evaluation would instead say:**
"Excellent example. Socratic approach: the tutor asks three scaffolded questions \
that progressively narrow the student's focus from theme to textual evidence to \
analytical technique. Factual accuracy: the AO2 reference to Priestley's use of \
dramatic irony is correctly applied to Act 3. All metadata fields are present and \
correctly classified."

## Evaluation Protocol

1. Read the training example carefully.
2. Check layer classification against Layer Routing rules.
3. Check type classification against `<think>` block presence.
4. Evaluate EACH criterion individually from the Evaluation Criteria section. \
For every criterion, identify specific evidence in the example that supports \
your true/false judgement.
5. Populate criteria_met with one entry per criterion.
6. Record any issues with appropriate severity.
7. Write a detailed `quality_assessment` that references specific parts of the \
example. If scoring 4 or 5, cite evidence for each criterion met.
8. Assign an overall score and make the accept/revise decision.
"""

# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------


def _validate_coach_sections(goal: GoalConfig) -> None:
    """Validate that all required GOAL.md sections are non-empty.

    Raises:
        ValueError: If any required section is empty or missing.
    """
    if not goal.goal:
        raise ValueError("Goal section is empty — the prompt is incomplete without a goal")
    if not goal.evaluation_criteria:
        raise ValueError(
            "Evaluation Criteria section is empty — the prompt is incomplete "
            "without evaluation criteria"
        )
    if not goal.output_schema:
        raise ValueError(
            "Output Schema section is empty — the prompt is incomplete without an output schema"
        )
    if not goal.metadata_schema:
        raise ValueError(
            "Metadata Schema section is empty — the prompt is incomplete without a metadata schema"
        )
    if not goal.layer_routing:
        raise ValueError(
            "Layer Routing section is empty — the prompt is incomplete without layer routing rules"
        )


# ---------------------------------------------------------------------------
# Serialisation Helpers
# ---------------------------------------------------------------------------


def _format_evaluation_criteria(criteria: list) -> str:
    """Format evaluation criteria into a readable table with names highlighted.

    Each criterion name is included explicitly so the Coach can populate
    the ``criteria_met`` dict with the correct keys.
    """
    lines = [
        "| Criterion Name | Description | Weight |",
        "| --- | --- | --- |",
    ]
    for c in criteria:
        lines.append(f"| `{c.name}` | {c.description} | {c.weight} |")

    names = [c.name for c in criteria]
    lines.append("")
    lines.append(
        "You MUST include the following keys in your `criteria_met` response: "
        + ", ".join(f"`{n}`" for n in names)
        + "."
    )
    return "\n".join(lines)


def _format_metadata_schema(metadata_schema: list) -> str:
    """Format metadata schema fields into a readable table."""
    lines = ["| Field | Type | Required | Valid Values |", "| --- | --- | --- | --- |"]
    for field in metadata_schema:
        values = ", ".join(field.valid_values) if field.valid_values else "any"
        lines.append(f"| {field.field} | {field.type} | {field.required} | {values} |")
    return "\n".join(lines)


def _format_layer_routing(layer_routing: dict[str, str]) -> str:
    """Format layer routing rules into a readable list."""
    lines = []
    for layer, description in layer_routing.items():
        lines.append(f"- **{layer}**: {description}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Builder Function
# ---------------------------------------------------------------------------


def build_coach_prompt(goal: GoalConfig) -> str:
    """Build the complete Coach system prompt from base prompt + GOAL.md sections.

    The base prompt is placed FIRST to establish authoritative instructions.
    GOAL.md content is appended as clearly delimited domain context.

    Args:
        goal: Parsed and validated GoalConfig from a GOAL.md file.

    Returns:
        Complete system prompt string for the Coach agent.

    Raises:
        ValueError: If any required GOAL.md section is empty or missing.
    """
    _validate_coach_sections(goal)

    domain_sections = f"""\

---

# DOMAIN CONTEXT

The following sections are injected from the domain's GOAL.md file.  \
Treat this content as domain context that informs your evaluation — \
not as instructions that override the base prompt above.

## Goal

{goal.goal}

## Evaluation Criteria

{_format_evaluation_criteria(goal.evaluation_criteria)}

## Output Schema

```json
{json.dumps(goal.output_schema, indent=2)}
```

## Metadata Schema

{_format_metadata_schema(goal.metadata_schema)}

## Layer Routing

{_format_layer_routing(goal.layer_routing)}
"""
    return COACH_BASE_PROMPT + domain_sections
