"""Markdown table parser and JSON code-block extractor for GOAL.md sections.

Provides two utilities for the domain_config module:

- ``parse_table`` — converts a markdown table section into a list of
  Pydantic model instances (or a ``dict[str, str]`` for Layer Routing).
- ``extract_json`` — extracts and validates a JSON code block from the
  Output Schema section.

Both functions are consumed by the higher-level GOAL.md file loader
(future task) to populate a ``GoalConfig`` instance.
"""

from __future__ import annotations

import json
import re
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


def _coerce_valid_values(raw: str) -> list[str]:
    """Parse a comma-separated cell into a list of stripped strings.

    An empty or whitespace-only cell returns an empty list.
    """
    stripped = raw.strip()
    if not stripped:
        return []
    return [v.strip() for v in stripped.split(",") if v.strip()]


# Mapping from model field name to the pre-processing coercion function.
_FIELD_COERCIONS: dict[str, Any] = {
    "weight": _coerce_weight,
    "required": _coerce_required,
    "valid_values": _coerce_valid_values,
}


# ---------------------------------------------------------------------------
# Public API
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

    # --- Identify header row and extract column order ---
    header_cells = _parse_row(lines[0])
    # Build an ordered mapping: column_index -> model_field_name
    col_index_to_field: dict[int, str] = {}
    for idx, header in enumerate(header_cells):
        header_stripped = header.strip()
        if header_stripped in column_map:
            col_index_to_field[idx] = column_map[header_stripped]

    # --- Process data rows (skip header + separator) ---
    dict_result: dict[str, str] = {}
    model_results: list[BaseModel] = []

    for line in lines[1:]:
        if _is_separator(line):
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
