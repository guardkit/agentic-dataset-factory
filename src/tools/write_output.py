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

from synthesis.validator import normalise_think_closing_tags

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

_ALLOWED_MESSAGE_KEYS: frozenset[str] = frozenset({"role", "content"})
_VALID_ROLES: frozenset[str] = frozenset({"system", "user", "assistant"})

# 2026-08-18 (Rich's word): metadata LABEL fields whose invented values must
# never lose a Coach-ACCEPTED row.  The 08-13/14 PO run dropped 41 accepted
# rows because the Player invented a ``metadata.topic`` outside the GOAL enum
# and write validation failed 3 times.  For these fields the tool now falls
# back deterministically to the nearest valid value, records the original
# label on the row (``metadata.<field>_original``) and appends a line to the
# ``rejected_metadata.jsonl`` sidecar next to train.jsonl — nothing vanishes
# silently.  Every OTHER schema field keeps the strict path (``mode`` is
# injected by the loop and checked downstream; a wrong ``mode`` corrupts).
_LABEL_FALLBACK_FIELDS: frozenset[str] = frozenset({"topic"})
_REJECTED_METADATA_SIDECAR = "rejected_metadata.jsonl"
_DEFAULT_FALLBACK_LABELS: tuple[str, ...] = ("other", "general", "misc")


def _normalise_label(value: str) -> str:
    """Case-fold and collapse separators so ``Feature-Slicing`` == ``feature_slicing``."""
    out = value.strip().lower()
    for ch in (" ", "-", "/", "."):
        out = out.replace(ch, "_")
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


def resolve_label_fallback(value: str, valid_values: list[str]) -> tuple[str, str]:
    """Deterministically map an invented label to the nearest valid enum value.

    Order (first hit wins; enum order breaks ties):
      1. ``exact_ci``  — case/separator-insensitive exact match.
      2. ``substring`` — a valid value contained in the label, or the label
         contained in a valid value (normalised); the LONGEST overlapping
         valid value wins, enum order on ties.
      3. ``token``     — any underscore-token of the label equals a token of
         a valid value (e.g. ``prioritisation_matrix`` → ``prioritisation_value_risk``);
         most shared tokens wins, enum order on ties.
      4. ``default``   — ``other``/``general``/``misc`` if the enum has one,
         else the FIRST enum value.

    Returns:
        ``(fallback_value, strategy)``.
    """
    if not valid_values:
        return value, "no_enum"
    norm = _normalise_label(str(value))
    normalised = [(_normalise_label(v), v) for v in valid_values]

    for nv, v in normalised:
        if nv == norm:
            return v, "exact_ci"

    if norm:
        best: tuple[int, int, str] | None = None  # (-len, enum_idx, value)
        for idx, (nv, v) in enumerate(normalised):
            if nv and (nv in norm or norm in nv):
                cand = (-len(nv), idx, v)
                if best is None or cand < best:
                    best = cand
        if best is not None:
            return best[2], "substring"

        tokens = {t for t in norm.split("_") if len(t) > 2}
        best_tok: tuple[int, int, str] | None = None  # (-shared, enum_idx, value)
        for idx, (nv, v) in enumerate(normalised):
            shared = len(tokens & {t for t in nv.split("_") if len(t) > 2})
            if shared:
                cand = (-shared, idx, v)
                if best_tok is None or cand < best_tok:
                    best_tok = cand
        if best_tok is not None:
            return best_tok[2], "token"

    for dflt in _DEFAULT_FALLBACK_LABELS:
        for nv, v in normalised:
            if nv == dflt:
                return v, "default"
    return valid_values[0], "default"


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

        # -- Step 2b: Validate every message dict has exactly {"role", "content"}
        #    with a valid role value (TASK-DKW-001, bug TASK-REV-4AA0).
        #    Catches LLM-produced malformed keys like " role" (leading space)
        #    that json.loads accepts but downstream consumers reject.
        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                return f"Error: messages[{i}] is not an object"
            keys = set(msg.keys())
            unexpected = keys - _ALLOWED_MESSAGE_KEYS
            missing = _ALLOWED_MESSAGE_KEYS - keys
            if unexpected or missing:
                return (
                    f"Error: messages[{i}] has invalid keys "
                    f"(unexpected={sorted(unexpected)}, missing={sorted(missing)})"
                )
            if msg["role"] not in _VALID_ROLES:
                return (
                    f"Error: messages[{i}].role invalid value "
                    f"{msg['role']!r} (expected: system, user, assistant)"
                )

        # -- Step 3: Check messages[0].role == "system" -------------------------
        if messages[0]["role"] != "system":
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

        # -- Step 6b: Normalise malformed <think> closing tags -----------------
        for msg in messages:
            if (
                isinstance(msg, dict)
                and msg.get("role") == "assistant"
                and isinstance(msg.get("content"), str)
            ):
                msg["content"] = normalise_think_closing_tags(msg["content"])

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
        label_fallbacks: list[dict[str, object]] = []
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
                    if field_name in _LABEL_FALLBACK_FIELDS:
                        # Never lose an accepted row on a label: fall back,
                        # record the original on the row, sidecar it below.
                        fallback, strategy = resolve_label_fallback(
                            str(field_value), valid_values
                        )
                        metadata[f"{field_name}_original"] = field_value
                        metadata[field_name] = fallback
                        label_fallbacks.append(
                            {
                                "field": field_name,
                                "original": field_value,
                                "fallback": fallback,
                                "strategy": strategy,
                            }
                        )
                        logger.warning(
                            "metadata.%s %r not in valid values — falling back "
                            "to %r (%s); original kept in metadata.%s_original "
                            "and %s",
                            field_name,
                            field_value,
                            fallback,
                            strategy,
                            field_name,
                            _REJECTED_METADATA_SIDECAR,
                        )
                        continue
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

            if label_fallbacks:
                _append_rejected_metadata_sidecar(
                    output_dir, label_fallbacks, str(target_path), count, metadata
                )
                notes = "; ".join(
                    f"metadata.{fb['field']} {fb['original']!r} -> "
                    f"{fb['fallback']!r} ({fb['strategy']})"
                    for fb in label_fallbacks
                )
                return (
                    f"Written to {target_path} (example #{count}) "
                    f"[label fallback: {notes}]"
                )

            return f"Written to {target_path} (example #{count})"

        except OSError as exc:
            logger.error("Write failed for %s: %s", target_path, exc)
            return f"Error: Failed to write to {target_path}: {exc}"

    return write_output


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _append_rejected_metadata_sidecar(
    output_dir: Path,
    fallbacks: list[dict[str, object]],
    written_to: str,
    example_number: int,
    metadata: dict,
) -> None:
    """Append one line per label fallback to ``rejected_metadata.jsonl``.

    Best-effort: a sidecar write failure is logged, never raised, and never
    fails the (already written) row.
    """
    sidecar = output_dir / _REJECTED_METADATA_SIDECAR
    try:
        with open(sidecar, "a", encoding="utf-8") as f:
            for fb in fallbacks:
                line = {
                    "field": fb["field"],
                    "original": fb["original"],
                    "fallback": fb["fallback"],
                    "strategy": fb["strategy"],
                    "written_to": written_to,
                    "example_number": example_number,
                    "layer": metadata.get("layer"),
                    "mode": metadata.get("mode"),
                    "dimension": metadata.get("dimension"),
                }
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
            f.flush()
    except OSError as exc:
        logger.error("Sidecar write failed for %s: %s", sidecar, exc)


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
