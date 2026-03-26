"""Factory and LangChain tool for writing validated training examples to JSONL.

Provides ``create_write_output_tool`` which returns a LangChain ``@tool``-decorated
``write_output`` function. The tool validates training examples against a metadata
schema and routes them to the correct output file based on ``metadata.layer``.

Layer routing:
  - ``behaviour`` -> ``{output_dir}/train.jsonl``
  - ``knowledge`` -> ``{output_dir}/rag_index/knowledge.jsonl``

All errors are returned as descriptive strings — the tool never raises
exceptions (D7).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from langchain_core.tools import tool

if TYPE_CHECKING:
    from domain_config.models import MetadataField

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Layer -> file path mapping
# ---------------------------------------------------------------------------

_LAYER_PATHS: dict[str, str] = {
    "behaviour": "train.jsonl",
    "knowledge": "rag_index/knowledge.jsonl",
}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_write_output_tool(
    output_dir: Path,
    metadata_schema: list[MetadataField],
) -> Callable:
    """Create a LangChain ``write_output`` tool bound to an output directory and schema.

    The returned tool validates each training example against the 10-step
    validation chain defined in API-tools.md, then appends it as a single
    JSON line to the appropriate output file based on ``metadata.layer``.

    Args:
        output_dir: Root output directory. Files are written relative to this path.
        metadata_schema: List of :class:`MetadataField` definitions from the
            domain's GOAL.md. Fields with non-empty ``valid_values`` are
            validated against their allowed values.

    Returns:
        A LangChain ``@tool``-decorated callable with signature
        ``write_output(example_json: str) -> str``.
    """
    # Build a lookup of field -> valid_values for step 9 validation.
    # Only include fields that have a non-empty valid_values list.
    schema_lookup: dict[str, list[str]] = {}
    for field_def in metadata_schema:
        if field_def.valid_values:
            schema_lookup[field_def.field] = field_def.valid_values

    # Per-file example counters (closure state).
    example_counts: dict[str, int] = {}

    @tool
    def write_output(example_json: str) -> str:
        """Validate and write an accepted training example to the correct output file.

        Routes by metadata.layer field:
          - "behaviour" -> output/train.jsonl
          - "knowledge" -> output/rag_index/knowledge.jsonl

        Args:
            example_json: Complete training example as JSON string, conforming to
                          GOAL.md Output Schema. Must include both 'messages' and
                          'metadata' top-level keys.

        Returns:
            Success: "Written to {path} (example #N)"
            Error: Descriptive error string.
        """
        # -- Step 1: Parse JSON ------------------------------------------------
        try:
            data = json.loads(example_json)
        except (json.JSONDecodeError, TypeError):
            return "Error: Invalid JSON"

        if not isinstance(data, dict):
            return "Error: Missing required field 'messages'"

        # -- Step 2: Check messages exists and is non-empty array ---------------
        messages = data.get("messages")
        if not isinstance(messages, list) or len(messages) == 0:
            return "Error: Missing required field 'messages'"

        # -- Step 3: Check messages[0].role == "system" -------------------------
        first_msg = messages[0]
        if not isinstance(first_msg, dict) or first_msg.get("role") != "system":
            return "Error: messages[0].role must be 'system'"

        # -- Step 4: Check metadata exists and is object ------------------------
        metadata = data.get("metadata")
        if not isinstance(metadata, dict):
            return "Error: Missing required field 'metadata'"

        # -- Step 5: Check metadata.layer is valid ------------------------------
        layer = metadata.get("layer")
        if layer not in ("behaviour", "knowledge"):
            return (
                f"Error: Invalid metadata.layer value '{layer}' "
                f"(expected: behaviour, knowledge)"
            )

        # -- Step 6: Check metadata.type is valid -------------------------------
        example_type = metadata.get("type")
        if example_type not in ("reasoning", "direct"):
            return (
                f"Error: Invalid metadata.type value '{example_type}' "
                f"(expected: reasoning, direct)"
            )

        # -- Steps 7 & 8: Think-block checks on last assistant message ----------
        last_assistant_content = _find_last_assistant_content(messages)

        if last_assistant_content is not None:
            has_think = "<think>" in last_assistant_content

            if example_type == "reasoning" and not has_think:
                return (
                    "Error: metadata.type is 'reasoning' but assistant "
                    "content has no <think> block"
                )
            if example_type == "direct" and has_think:
                return (
                    "Error: metadata.type is 'direct' but assistant "
                    "content contains <think> block"
                )

        # -- Step 9: Validate metadata fields against schema valid_values -------
        for field_name, valid_values in schema_lookup.items():
            # Skip layer and type — already validated in steps 5/6
            if field_name in ("layer", "type"):
                continue
            field_value = metadata.get(field_name)
            if field_value is None:
                continue
            if isinstance(field_value, list):
                invalid = [v for v in field_value if v not in valid_values]
                if invalid:
                    return (
                        f"Error: metadata.{field_name} contains invalid "
                        f"values: {invalid}"
                    )
            else:
                if str(field_value) not in valid_values:
                    return (
                        f"Error: metadata.{field_name} value '{field_value}' "
                        f"not in valid values"
                    )

        # -- Step 10: Append validated JSON line to correct output file ----------
        relative_path = _LAYER_PATHS[layer]
        target_path = output_dir / relative_path

        try:
            # Create parent directories (e.g., rag_index/) if needed
            target_path.parent.mkdir(parents=True, exist_ok=True)

            line = json.dumps(data, ensure_ascii=False)
            with open(target_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()

            # Update per-file counter
            path_key = str(target_path)
            example_counts[path_key] = example_counts.get(path_key, 0) + 1
            count = example_counts[path_key]

            return f"Written to {target_path} (example #{count})"

        except OSError as exc:
            logger.error("Write failed for %s: %s", target_path, exc)
            return f"Error: Failed to write to {target_path}: {exc}"

    return write_output


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_last_assistant_content(messages: list[dict]) -> str | None:
    """Return the content of the last assistant message, or None if absent.

    Args:
        messages: List of message dicts with 'role' and 'content' keys.

    Returns:
        The content string of the last message with ``role == "assistant"``,
        or ``None`` if no assistant message exists.
    """
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            return msg.get("content", "")
    return None
