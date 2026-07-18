"""DCL row / metadata contracts + validators — pins OUTPUT-CONTRACT.md shapes in code.

Two row modes, both ShareGPT-enveloped and both routed to the behaviour layer:

- **AUTHOR** (``mode=dcl_author``, ``type=direct``): user = feature brief + the
  compiler-verified vocabulary reference; assistant = ONE ```` ```dcl ```` fenced
  capability, **no ``<think>`` block**. The capability compiles clean (the label the
  compiler fixed — never a model).
- **REPAIR** (``mode=dcl_repair``, ``type=reasoning``): user = a broken ``.dcl`` + the
  VERBATIM compiler diagnostics JSON + a repair instruction; assistant =
  ``<think>``rationale``</think>`` then ONE ```` ```dcl ```` fenced **corrected**
  capability. The correction is the pre-injection original **by construction**.

Every label (author-accepted text; repair-corrected text) is compiler-verified, never
model-decided — mirroring the QAV "labels fixed by the injector, model authors only the
rationale" discipline.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from dcl.checker import COMPILER_PIN

VOCAB_PIN = "4f9fbe56"
COMPILER_PIN_SHORT = COMPILER_PIN  # "4f9fbe56"
DOMAIN = "dcl-capability-language"

MODES = frozenset({"dcl_author", "dcl_repair"})
SPLITS = frozenset({"train", "eval_dcl"})
TYPES = frozenset({"direct", "reasoning"})
LAYERS = frozenset({"behaviour"})
PROVENANCE_SOURCES = frozenset({"synthetic-brief", "derived", "harvested"})
PROVENANCE_KEYS = ("source", "vocab_pin", "compiler_pin")
# W2c: harvested rows (real plan-commit briefs) carry three extra provenance keys naming
# WHERE the brief came from — REQUIRED when source=="harvested", FORBIDDEN otherwise.
HARVESTED_PROVENANCE_EXTRA_KEYS = ("repo", "feature", "run")
HARVESTED_PROVENANCE_KEYS = PROVENANCE_KEYS + HARVESTED_PROVENANCE_EXTRA_KEYS
# Author-mode rows may originate from the synthetic brief bank OR a harvested real brief.
AUTHOR_PROVENANCE_SOURCES = frozenset({"synthetic-brief", "harvested"})

_VOCAB_PATH = Path(__file__).resolve().parent / "vocab-reference.md"


class RowValidationError(ValueError):
    """Raised when a row / metadata object violates the OUTPUT-CONTRACT."""


# --------------------------------------------------------------------------------------
# System prompt — the DCL authoring identity + the closed-vocabulary discipline.
# Stored joined (hard line-wraps removed); the GOAL.md "System Prompt" section carries it
# (whitespace-normalised) so the two never silently diverge (asserted in tests).
# --------------------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are an expert author of the Declarative Capability Language (DCL v1.0), a "
    "closed-vocabulary language for modelling business-system capabilities. You translate a "
    "plain-language feature brief into a single, compiler-clean DCL capability, and you repair "
    "capabilities the compiler has rejected.\n\n"
    "Your core discipline: **DCL is a closed vocabulary, and the compiler is the only "
    "authority.** Every actor kind, effect kind, policy family, policy concern, concern value, "
    "field type, observation type, lifecycle step kind, and causation keyword comes from a "
    "fixed set given in the vocabulary reference — you never invent a literal outside it. "
    "Inventing an actor kind (`is machine`), an effect kind (`is in_memory`), a policy concern, "
    "a concern value, or a field type (`String`, `Int`) makes the file fail to compile, even "
    "when the invention reads plausibly. A capability that does not compile is worthless.\n\n"
    "You reason from the brief to the smallest faithful capability: one actor, a typed intent "
    "shape, the declared outcomes, the emitted events, the effects, the governing policy, and — "
    "when the brief implies process state — a lifecycle whose `when` block causes every declared "
    "outcome. You keep identifiers well-formed, you attach policies to legal targets, and you "
    "satisfy the compiler's cross-cutting rules (a retry policy requires an idempotency "
    "guarantee on the same target; every declared outcome must be caused in `when`).\n\n"
    "When repairing, you read the compiler diagnostics as ground truth: you diagnose the named "
    "`DCL_*` error, change only what the diagnostics require, and preserve every unaffected "
    "declaration. You never rewrite a capability from scratch to dodge a single defect, and you "
    "never introduce a new literal to patch an old one."
)


def load_vocab_reference() -> str:
    """The compiler-verified vocabulary reference text, embedded in every author row."""
    return _VOCAB_PATH.read_text(encoding="utf-8")


# --------------------------------------------------------------------------------------
# User-message assembly. Author row_id hashes user+assistant; repair hashes the user (§4).
# --------------------------------------------------------------------------------------
def build_author_user_message(brief: str, vocab_reference: str) -> str:
    """AUTHOR user message: the feature brief + the closed vocabulary (OUTPUT-CONTRACT §2)."""
    return (
        "## Feature brief\n"
        f"{brief.strip()}\n\n"
        "## DCL vocabulary reference (closed — author using ONLY these literals)\n"
        f"{vocab_reference.strip()}\n\n"
        "## Task\n"
        "Author a single DCL capability that models the brief. Use only the compiler-verified "
        "closed vocabulary above. Emit exactly one ```dcl fenced block and nothing else."
    )


def build_repair_user_message(broken_dcl: str, diagnostics_json: str) -> str:
    """REPAIR user message: the broken .dcl + VERBATIM compiler diagnostics (OUTPUT-CONTRACT §2)."""
    return (
        "## Broken DCL capability\n"
        "```dcl\n"
        f"{broken_dcl.strip()}\n"
        "```\n\n"
        "## Compiler diagnostics (verbatim from the DCL compiler)\n"
        "```json\n"
        f"{diagnostics_json.strip()}\n"
        "```\n\n"
        "## Task\n"
        "This capability fails to compile. Diagnose the cause named in the diagnostics and emit "
        "the corrected capability as one ```dcl fenced block, changing only what the diagnostics "
        "require and preserving every unaffected declaration."
    )


def row_id(user_message_content: str) -> str:
    """Content-addressed row id — ``dcl-<sha256[:16]>`` of the user message (OUTPUT-CONTRACT §4).

    This is the **repair** row_id semantics (unchanged): a repair row's user message already
    carries the broken ``.dcl`` + the verbatim diagnostics, so the user message alone uniquely
    identifies the row."""
    digest = hashlib.sha256(user_message_content.encode("utf-8")).hexdigest()
    return f"dcl-{digest[:16]}"


# Separator that cannot appear in a fenced ```dcl block or the vocab reference, so the
# concatenation is unambiguous (no user/assistant boundary collision).
_ROW_ID_SEP = "\x00"


def author_row_id(user_message_content: str, assistant_content: str) -> str:
    """Content-addressed **author** row id over the FULL row (user + assistant).

    Author user messages are the brief + the shared vocabulary reference, so two DIFFERENT
    completions of the SAME brief share a user message and would COLLIDE under the user-only
    hash. Hashing user+assistant lets ``author_reps`` distinct completions coexist as distinct
    rows, while byte-identical duplicate rows still hash equal and dedupe (OUTPUT-CONTRACT §4)."""
    digest = hashlib.sha256(
        (user_message_content + _ROW_ID_SEP + assistant_content).encode("utf-8")
    ).hexdigest()
    return f"dcl-{digest[:16]}"


def expected_row_id(mode: str, user_message_content: str, assistant_content: str) -> str:
    """The row_id a row must carry for its ``mode`` — author hashes user+assistant, repair
    hashes the user message alone. The single source of truth for id computation + validation."""
    if mode == "dcl_author":
        return author_row_id(user_message_content, assistant_content)
    return row_id(user_message_content)


# --------------------------------------------------------------------------------------
# Assistant-message assembly.
# --------------------------------------------------------------------------------------
def author_assistant_content(dcl_text: str) -> str:
    """AUTHOR assistant turn: ONE fenced dcl block, NO think block (direct type)."""
    return f"```dcl\n{dcl_text.strip()}\n```"


def repair_assistant_content(think: str, dcl_text: str) -> str:
    """REPAIR assistant turn: ``<think>``rationale``</think>`` then ONE fenced dcl block."""
    return f"<think>\n{think.strip()}\n</think>\n\n```dcl\n{dcl_text.strip()}\n```"


_THINK_RE = re.compile(r"<think>(.*?)</think>", re.S)
_DCL_FENCE_RE = re.compile(r"```dcl\s*\n(.*?)\n```", re.S)


def extract_capability(row: dict[str, Any]) -> str:
    """Recover the fenced dcl capability text from a row's assistant message."""
    content = row["messages"][-1]["content"]
    m = _DCL_FENCE_RE.search(content)
    if not m:
        raise RowValidationError("assistant content missing a ```dcl fenced block")
    return m.group(1)


def user_message(row: dict[str, Any]) -> str:
    """The user message content — what ``row_id`` is content-addressed on."""
    return row["messages"][1]["content"]


# --------------------------------------------------------------------------------------
# Metadata + row assembly — OUTPUT-CONTRACT §4, §1.
# --------------------------------------------------------------------------------------
def _expected_provenance_keys(source: str) -> set[str]:
    """The exact provenance key set for a source — harvested rows carry three extra keys."""
    return set(HARVESTED_PROVENANCE_KEYS) if source == "harvested" else set(PROVENANCE_KEYS)


def build_provenance(
    source: str,
    *,
    repo: str | None = None,
    feature: str | None = None,
    run: str | None = None,
) -> dict[str, str]:
    """Provenance block. ``source=="harvested"`` REQUIRES repo/feature/run; every other
    source FORBIDS them (the additive W2c contract — synthetic/derived stay byte-identical)."""
    if source not in PROVENANCE_SOURCES:
        raise RowValidationError(f"provenance source {source!r} not in {sorted(PROVENANCE_SOURCES)}")
    prov = {"source": source, "vocab_pin": VOCAB_PIN, "compiler_pin": COMPILER_PIN_SHORT}
    if source == "harvested":
        if repo is None or feature is None or run is None:
            raise RowValidationError(
                "harvested provenance requires repo, feature and run (the {repo, feature, run} keys)"
            )
        prov["repo"], prov["feature"], prov["run"] = repo, feature, run
    elif any(v is not None for v in (repo, feature, run)):
        raise RowValidationError(
            "repo/feature/run are only permitted when provenance.source == 'harvested'"
        )
    return prov


def build_metadata(
    *,
    user_msg: str,
    assistant_msg: str,
    mode: str,
    type_: str,
    split: str,
    provenance: dict[str, str],
    recipe_id: str | None,
    compile_verified: bool = True,
) -> dict[str, Any]:
    if mode not in MODES:
        raise RowValidationError(f"mode {mode!r} not in {sorted(MODES)}")
    if type_ not in TYPES:
        raise RowValidationError(f"type {type_!r} not in {sorted(TYPES)}")
    if split not in SPLITS:
        raise RowValidationError(f"split {split!r} not in {sorted(SPLITS)}")
    if provenance.get("source") not in PROVENANCE_SOURCES:
        raise RowValidationError("provenance.source invalid")
    if set(provenance) != _expected_provenance_keys(provenance["source"]):
        raise RowValidationError(
            f"provenance keys must be {sorted(_expected_provenance_keys(provenance['source']))} "
            f"for source {provenance['source']!r}"
        )
    return {
        "row_id": expected_row_id(mode, user_msg, assistant_msg),
        "domain": DOMAIN,
        "layer": "behaviour",
        "type": type_,
        "mode": mode,
        "split": split,
        "recipe_id": recipe_id,
        "provenance": dict(provenance),
        "compile_verified": bool(compile_verified),
    }


def build_author_row(
    *,
    brief: str,
    dcl_text: str,
    vocab_reference: str,
    split: str,
    provenance: dict[str, str] | None = None,
    compile_verified: bool = True,
) -> dict[str, Any]:
    """Assemble + validate an AUTHOR row (brief -> compiler-clean capability).

    ``provenance`` defaults to a ``synthetic-brief`` block (the synthetic path stays
    byte-identical). Harvested real briefs pass a ``harvested`` provenance built via
    :func:`build_provenance` with repo/feature/run."""
    user_msg = build_author_user_message(brief, vocab_reference)
    assistant_msg = author_assistant_content(dcl_text)
    prov = provenance if provenance is not None else build_provenance("synthetic-brief")
    row = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": assistant_msg},
        ],
        "metadata": build_metadata(
            user_msg=user_msg,
            assistant_msg=assistant_msg,
            mode="dcl_author",
            type_="direct",
            split=split,
            provenance=prov,
            recipe_id=None,
            compile_verified=compile_verified,
        ),
    }
    validate_row(row)
    return row


def build_repair_row(
    *,
    broken_dcl: str,
    diagnostics_json: str,
    think: str,
    corrected_dcl: str,
    recipe_id: str,
    split: str,
    compile_verified: bool = True,
) -> dict[str, Any]:
    """Assemble + validate a REPAIR row (broken + diagnostics -> corrected capability)."""
    user_msg = build_repair_user_message(broken_dcl, diagnostics_json)
    assistant_msg = repair_assistant_content(think, corrected_dcl)
    row = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": assistant_msg},
        ],
        "metadata": build_metadata(
            user_msg=user_msg,
            assistant_msg=assistant_msg,
            mode="dcl_repair",
            type_="reasoning",
            split=split,
            provenance=build_provenance("derived"),
            recipe_id=recipe_id,
            compile_verified=compile_verified,
        ),
    }
    validate_row(row)
    return row


_META_KEYS = {
    "row_id", "domain", "layer", "type", "mode", "split", "recipe_id",
    "provenance", "compile_verified",
}


def validate_row(row: dict[str, Any]) -> None:
    """Full structural validation of an assembled row (OUTPUT-CONTRACT §1–§4)."""
    if set(row) != {"messages", "metadata"}:
        raise RowValidationError(f"row keys must be {{messages, metadata}}, got {sorted(row)}")
    msgs = row["messages"]
    if [m.get("role") for m in msgs] != ["system", "user", "assistant"]:
        raise RowValidationError("messages must be [system, user, assistant] in order")
    for m in msgs:
        if set(m) != {"role", "content"}:
            raise RowValidationError("each message must carry exactly {role, content}")
    if msgs[0]["content"] != SYSTEM_PROMPT:
        raise RowValidationError("system message must be the pinned DCL system prompt")

    meta = row["metadata"]
    if set(meta) != _META_KEYS:
        raise RowValidationError(f"metadata keys must be {sorted(_META_KEYS)}, got {sorted(meta)}")
    if meta["domain"] != DOMAIN:
        raise RowValidationError(f"domain must be {DOMAIN!r}")
    if meta["layer"] != "behaviour":
        raise RowValidationError("dcl rows route to the behaviour layer")
    if meta["mode"] not in MODES:
        raise RowValidationError(f"mode {meta['mode']!r} invalid")
    if meta["type"] not in TYPES:
        raise RowValidationError(f"type {meta['type']!r} invalid")
    if meta["split"] not in SPLITS:
        raise RowValidationError(f"split {meta['split']!r} invalid")
    if meta["compile_verified"] is not True:
        raise RowValidationError("compile_verified must be True — every row's label is compiler-checked")
    prov_source = meta["provenance"].get("source")
    if prov_source not in PROVENANCE_SOURCES:
        raise RowValidationError(f"provenance.source {prov_source!r} not in {sorted(PROVENANCE_SOURCES)}")
    if set(meta["provenance"]) != _expected_provenance_keys(prov_source):
        raise RowValidationError(
            "provenance must be the pinned keys for its source "
            f"({sorted(_expected_provenance_keys(prov_source))})"
        )
    if meta["provenance"]["vocab_pin"] != VOCAB_PIN or meta["provenance"]["compiler_pin"] != COMPILER_PIN_SHORT:
        raise RowValidationError(f"provenance pins must be {VOCAB_PIN!r}")
    if meta["row_id"] != expected_row_id(meta["mode"], user_message(row), msgs[2]["content"]):
        raise RowValidationError(
            "row_id is not content-addressed as its mode requires "
            "(author: user+assistant; repair: user message)"
        )

    assistant = msgs[2]["content"]
    has_think = "<think>" in assistant
    fence = _DCL_FENCE_RE.search(assistant)
    if not fence:
        raise RowValidationError("assistant content missing a ```dcl fenced capability")
    if not fence.group(1).strip():
        raise RowValidationError("assistant ```dcl fence is empty")

    if meta["mode"] == "dcl_author":
        if meta["type"] != "direct":
            raise RowValidationError("dcl_author rows are type=direct")
        if has_think:
            raise RowValidationError("dcl_author rows must NOT carry a <think> block (direct)")
        if meta["recipe_id"] is not None:
            raise RowValidationError("dcl_author rows carry no recipe_id")
        if meta["provenance"]["source"] not in AUTHOR_PROVENANCE_SOURCES:
            raise RowValidationError(
                "dcl_author provenance.source must be synthetic-brief or harvested"
            )
    else:  # dcl_repair
        if meta["type"] != "reasoning":
            raise RowValidationError("dcl_repair rows are type=reasoning")
        if not has_think:
            raise RowValidationError("dcl_repair rows must carry a <think> block (reasoning)")
        think = _THINK_RE.search(assistant)
        if not think or not think.group(1).strip():
            raise RowValidationError("dcl_repair <think> block is empty")
        if not meta["recipe_id"]:
            raise RowValidationError("dcl_repair rows must record the injection recipe_id")
        if meta["provenance"]["source"] != "derived":
            raise RowValidationError("dcl_repair provenance.source must be derived")
