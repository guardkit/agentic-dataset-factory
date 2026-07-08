"""QAV row / label / metadata / bundle contracts + validators.

Pins the OUTPUT-CONTRACT.md shapes in code so hold-out discipline and schema fidelity
are *enforced*, not conventional (WS2-B11 guardrail: "hold-out discipline enforced in
code, not convention"). Every constant here traces to a committed spec section — no
invented fields.

References:
- ``domains/qa-verifier/OUTPUT-CONTRACT.md`` §1 (envelope), §2 (input bundle), §3 (label),
  §4 (metadata), §5 (manifest).
- ``domains/qa-verifier/GOAL.md`` (system prompt, admissible DC set).
- CoachEvidenceBundle field set pinned at guardkit ``41a0ebe457``
  (``guardkit/orchestrator/quality_gates/coach_evidence.py`` — ``dataclasses.asdict`` of
  the 25-field dataclass; verified field-for-field on disk 2026-07-08).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

# --------------------------------------------------------------------------------------
# Bundle field set — OUTPUT-CONTRACT §2, pinned at guardkit 41a0ebe457.
# Order matches the dataclass declaration; `honesty` is the only non-Optional field.
# --------------------------------------------------------------------------------------
PINNED_BUNDLE_SCHEMA_SHA = "41a0ebe457"

BUNDLE_FIELDS: tuple[str, ...] = (
    "honesty",
    "gathering_status",
    "gathering_error",
    "quality_gates",
    "coverage_details",
    "plan_audit",
    "bdd",
    "bdd_authoring_sweep",
    "arch_review",
    "tests",
    "wiring",
    "mocked_seam",
    "spec_gap",
    "stub_scan",
    "coverage",
    "behavioural_oracle",
    "independent_tests",
    "independent_test_classification",
    "requirements",
    "runtime_parity",
    "evidence_repo_tests",
    "severity_recommendations",
    "advisory_issues",
    "task_type",
    "profile_name",
)
BUNDLE_FIELD_SET = frozenset(BUNDLE_FIELDS)
REQUIRED_BUNDLE_FIELD = "honesty"

# --------------------------------------------------------------------------------------
# Label / metadata enums — OUTPUT-CONTRACT §3, §4 + PLAN §3 dated note.
# --------------------------------------------------------------------------------------
# Phase-1 admissible DC classes: only the *named/documented* classes (PLAN §3 dated note —
# the nine unnamed DC ids are out of scope until a committed taxonomy doc names them).
PHASE1_DC_CLASSES = frozenset({"DC-03", "DC-05", "DC-08", "DC-12", "DC-14"})

GROUND_TRUTH_SOURCES = frozenset(
    {"coach_correct", "operator_caught", "merge_review_caught", "live_gate_caught", "seeded"}
)
GENERATION_MODES = frozenset({"seeded_code", "seeded_bundle", "harvest", "gold_negative"})
SPLITS = frozenset({"train", "eval_qav"})
RECONSTRUCTION_FIDELITIES = frozenset({"verbatim", "reconstructed", None})
VERDICTS = frozenset({"approve", "reject"})

# Provenance is the scope-pinned quintet, verbatim keys (OUTPUT-CONTRACT §4).
PROVENANCE_KEYS = ("repo", "feature", "task", "run", "sha")

LIVE_GATE_ABSENT_MARKER = "(none available)"


class RowValidationError(ValueError):
    """Raised when a row / label / bundle / manifest violates the OUTPUT-CONTRACT."""


# --------------------------------------------------------------------------------------
# System prompt — GOAL.md "System prompt" section, verbatim in substance.
# Stored joined (hard line-wraps removed); ``test_qav_contracts`` asserts GOAL.md still
# carries it (whitespace-normalised) so the two never silently diverge.
# --------------------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are an expert QA verification judge for an autonomous software factory. You read a "
    "structured evidence bundle gathered about one task's implementation — honesty "
    "verification, quality gates, test results, independent test runs, BDD oracle and "
    "authoring-sweep results, wiring/mocked-seam/stub-scan/coverage/behavioural-oracle "
    "analyses, plan audit, and runtime parity — and you decide whether the evidence supports "
    "approving the work.\n\n"
    "Your core belief: **per-task green is not feature green, and absence of failure is never "
    "success.** Passing unit tests that inject dependencies directly tell you nothing about "
    "production call sites. A guard with no wired producer protects nothing. A green suite over "
    "a soft-failed TypeError is a dead feature with good manners. Evidence that was never "
    "gathered is absent signal, not clean signal — you read every null field against "
    "gathering_status before interpreting it.\n\n"
    "You are equally calibrated in both directions. You approve honest work that carries "
    "advisory blemishes, demoted discrepancies, profile-legitimate gate opt-outs, or "
    "infrastructure-classified failures — a judge that rejects every imperfection is as useless "
    "as one that approves everything. A false approval ships a broken feature; a false block "
    "burns the factory's throughput; you are measured on both.\n\n"
    "You render exactly one verdict per bundle: approve, or reject with named findings. Every "
    "finding carries its defect class from the documented taxonomy and the locus in the "
    "evidence where your judgment anchors. You reason from the evidence in front of you — you "
    "never invent evidence that is not in the bundle, and you never let a confident "
    "implementation narrative outweigh a discrepancy the honesty verification actually recorded."
)


# --------------------------------------------------------------------------------------
# Bundle validation — OUTPUT-CONTRACT §2 + the additive-sha mixing rule.
# --------------------------------------------------------------------------------------
def validate_bundle(bundle: dict[str, Any]) -> None:
    """Validate a serialized CoachEvidenceBundle dict against the pinned field set.

    A bundle is valid when every key is a known field (``extra=forbid`` semantics — an
    unknown key is drift, not additive growth) and ``honesty`` is present. A *subset* of
    the pinned fields is allowed: older-schema verbatim bundles (e.g. GN-3, serialized
    before the L2/L3/sweep fields existed) are additively compatible — missing keys read
    as absent/null (OUTPUT-CONTRACT §2 bundle-schema drift rule).
    """
    if not isinstance(bundle, dict):
        raise RowValidationError(f"bundle must be a dict, got {type(bundle).__name__}")
    unknown = set(bundle) - BUNDLE_FIELD_SET
    if unknown:
        raise RowValidationError(
            f"bundle carries non-pinned field(s) {sorted(unknown)} — not additive over "
            f"{PINNED_BUNDLE_SCHEMA_SHA}; a new field needs a dated note, not silent invention"
        )
    if REQUIRED_BUNDLE_FIELD not in bundle:
        raise RowValidationError(
            f"bundle missing required field {REQUIRED_BUNDLE_FIELD!r} (the only non-Optional "
            "CoachEvidenceBundle field)"
        )


# --------------------------------------------------------------------------------------
# Label validation — OUTPUT-CONTRACT §3 (the pinned trio; nothing else in the object).
# --------------------------------------------------------------------------------------
def validate_label(label: dict[str, Any]) -> None:
    if not isinstance(label, dict):
        raise RowValidationError("label must be a dict")
    extra = set(label) - {"verdict", "findings", "ground_truth_source"}
    if extra:
        raise RowValidationError(f"label carries unpinned keys {sorted(extra)} (trio only)")
    missing = {"verdict", "findings", "ground_truth_source"} - set(label)
    if missing:
        raise RowValidationError(f"label missing keys {sorted(missing)}")
    if label["verdict"] not in VERDICTS:
        raise RowValidationError(f"verdict must be one of {sorted(VERDICTS)}")
    if label["ground_truth_source"] not in GROUND_TRUTH_SOURCES:
        raise RowValidationError(
            f"ground_truth_source {label['ground_truth_source']!r} not in {sorted(GROUND_TRUTH_SOURCES)}"
        )
    findings = label["findings"]
    if not isinstance(findings, list):
        raise RowValidationError("findings must be a list")
    if label["verdict"] == "approve" and findings:
        raise RowValidationError("verdict=approve requires findings=[]")
    if label["verdict"] == "reject" and not findings:
        raise RowValidationError("verdict=reject requires >=1 finding")
    for f in findings:
        if set(f) != {"class", "locus"}:
            raise RowValidationError(
                f"finding must have exactly {{class, locus}}, got {sorted(f)}"
            )
        if f["class"] not in PHASE1_DC_CLASSES:
            raise RowValidationError(
                f"finding class {f['class']!r} not in the Phase-1 admissible set "
                f"{sorted(PHASE1_DC_CLASSES)} (PLAN §3 dated note)"
            )
        if not isinstance(f["locus"], str) or not f["locus"].strip():
            raise RowValidationError("finding locus must be a non-empty string")


# --------------------------------------------------------------------------------------
# User message assembly — OUTPUT-CONTRACT §2 layout. row_id hashes THIS content.
# --------------------------------------------------------------------------------------
def build_user_message(bundle: dict[str, Any], live_gate: str = LIVE_GATE_ABSENT_MARKER) -> str:
    """Serialize the evidence input exactly per OUTPUT-CONTRACT §2 (deterministic order)."""
    bundle_json = json.dumps(bundle, indent=2, sort_keys=True, ensure_ascii=False)
    return (
        "## Evidence bundle\n"
        "```json\n"
        f"{bundle_json}\n"
        "```\n\n"
        "## Live-gate results\n"
        f"{live_gate}\n"
    )


def row_id(user_message_content: str) -> str:
    """Content-addressed row id — ``qav-<sha256[:16]>`` of the user message (OUTPUT-CONTRACT §4).

    This is the value the contamination check intersects across the split boundary.
    """
    digest = hashlib.sha256(user_message_content.encode("utf-8")).hexdigest()
    return f"qav-{digest[:16]}"


def assistant_content(think: str, verdict_obj: dict[str, Any]) -> str:
    """Assemble the assistant turn: ``<think>…</think>`` then ONE fenced json verdict (§1)."""
    verdict_json = json.dumps(verdict_obj, indent=2, ensure_ascii=False)
    return f"<think>\n{think.strip()}\n</think>\n\n```json\n{verdict_json}\n```"


_THINK_RE = re.compile(r"<think>(.*?)</think>", re.S)
# Capture to the CLOSING fence, not the first "}" — bundle/label JSON is nested.
_FENCE_RE = re.compile(r"```json\s*(.*?)\s*```", re.S)


def parse_assistant_content(content: str) -> tuple[str, dict[str, Any]]:
    """Inverse of ``assistant_content`` — used by validators and the (later) serving parse."""
    tm = _THINK_RE.search(content)
    fm = _FENCE_RE.search(content)
    if not tm:
        raise RowValidationError("assistant content missing <think> block")
    if not fm:
        raise RowValidationError("assistant content missing fenced json verdict")
    return tm.group(1).strip(), json.loads(fm.group(1))


# --------------------------------------------------------------------------------------
# Metadata + row assembly — OUTPUT-CONTRACT §4, §1.
# --------------------------------------------------------------------------------------
def build_metadata(
    *,
    provenance: dict[str, Any],
    split: str,
    generation_mode: str,
    dc_class: str | None,
    user_message: str,
    bundle_schema_sha: str = PINNED_BUNDLE_SCHEMA_SHA,
    reconstruction_fidelity: str | None = None,
    injection_recipe: str | None = None,
) -> dict[str, Any]:
    if set(provenance) != set(PROVENANCE_KEYS):
        raise RowValidationError(
            f"provenance must be exactly {list(PROVENANCE_KEYS)}, got {sorted(provenance)}"
        )
    if split not in SPLITS:
        raise RowValidationError(f"split {split!r} not in {sorted(SPLITS)}")
    if generation_mode not in GENERATION_MODES:
        raise RowValidationError(f"generation_mode {generation_mode!r} not in {sorted(GENERATION_MODES)}")
    if dc_class is not None and dc_class not in PHASE1_DC_CLASSES:
        raise RowValidationError(f"dc_class {dc_class!r} not in {sorted(PHASE1_DC_CLASSES)}")
    if reconstruction_fidelity not in RECONSTRUCTION_FIDELITIES:
        raise RowValidationError(f"reconstruction_fidelity {reconstruction_fidelity!r} invalid")
    meta = {
        "row_id": row_id(user_message),
        "provenance": dict(provenance),
        "split": split,
        "generation_mode": generation_mode,
        "dc_class": dc_class,
        "bundle_schema_sha": bundle_schema_sha,
        "reconstruction_fidelity": reconstruction_fidelity,
        "injection_recipe": injection_recipe,
    }
    return meta


def build_row(
    *,
    bundle: dict[str, Any],
    think: str,
    label: dict[str, Any],
    provenance: dict[str, Any],
    split: str,
    generation_mode: str,
    dc_class: str | None,
    bundle_schema_sha: str = PINNED_BUNDLE_SCHEMA_SHA,
    reconstruction_fidelity: str | None = None,
    injection_recipe: str | None = None,
    live_gate: str = LIVE_GATE_ABSENT_MARKER,
) -> dict[str, Any]:
    """Assemble a complete, validated QAV row (ShareGPT envelope + metadata)."""
    validate_bundle(bundle)
    validate_label(label)
    user_message = build_user_message(bundle, live_gate=live_gate)
    row = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_content(think, label)},
        ],
        "metadata": build_metadata(
            provenance=provenance,
            split=split,
            generation_mode=generation_mode,
            dc_class=dc_class,
            user_message=user_message,
            bundle_schema_sha=bundle_schema_sha,
            reconstruction_fidelity=reconstruction_fidelity,
            injection_recipe=injection_recipe,
        ),
    }
    validate_row(row)
    return row


_BUNDLE_FENCE_RE = re.compile(r"## Evidence bundle\s*```json\s*(.*?)\s*```", re.S)


def extract_bundle(row: dict[str, Any]) -> dict[str, Any]:
    """Recover the evidence bundle dict from an assembled row's user message (§2 layout)."""
    user = row["messages"][1]["content"]
    m = _BUNDLE_FENCE_RE.search(user)
    if not m:
        raise RowValidationError("could not extract evidence bundle from user message")
    return json.loads(m.group(1))


def extract_label(row: dict[str, Any]) -> dict[str, Any]:
    """Recover the verdict object (the label) from an assembled row's assistant message."""
    _, verdict_obj = parse_assistant_content(row["messages"][2]["content"])
    return verdict_obj


def validate_row(row: dict[str, Any]) -> None:
    """Full structural validation of an assembled row (OUTPUT-CONTRACT §1–§4)."""
    if set(row) != {"messages", "metadata"}:
        raise RowValidationError(f"row keys must be {{messages, metadata}}, got {sorted(row)}")
    msgs = row["messages"]
    if [m.get("role") for m in msgs] != ["system", "user", "assistant"]:
        raise RowValidationError("messages must be [system, user, assistant] in order")
    if msgs[0]["content"] != SYSTEM_PROMPT:
        raise RowValidationError("system message must be the pinned QAV system prompt")
    # user message must round-trip a valid bundle and match §2 layout
    user = msgs[1]["content"]
    if "## Evidence bundle" not in user or "## Live-gate results" not in user:
        raise RowValidationError("user message missing §2 sections")
    # assistant must carry a think block + a valid label
    think, verdict_obj = parse_assistant_content(msgs[2]["content"])
    if not think:
        raise RowValidationError("empty <think> block")
    validate_label(verdict_obj)
    # metadata
    meta = row["metadata"]
    expected_meta_keys = {
        "row_id",
        "provenance",
        "split",
        "generation_mode",
        "dc_class",
        "bundle_schema_sha",
        "reconstruction_fidelity",
        "injection_recipe",
    }
    if set(meta) != expected_meta_keys:
        raise RowValidationError(f"metadata keys must be {sorted(expected_meta_keys)}, got {sorted(meta)}")
    if meta["row_id"] != row_id(user):
        raise RowValidationError("row_id is not content-addressed on the user message")
    if set(meta["provenance"]) != set(PROVENANCE_KEYS):
        raise RowValidationError("provenance must be the pinned quintet")
    if meta["split"] not in SPLITS:
        raise RowValidationError("bad split")
    if meta["generation_mode"] not in GENERATION_MODES:
        raise RowValidationError("bad generation_mode")
    # verdict/mode coherence: gold_negative is always a reject holdout
    if meta["generation_mode"] == "gold_negative":
        if verdict_obj["verdict"] != "reject" or meta["split"] != "eval_qav":
            raise RowValidationError("gold_negative rows are reject + split=eval_qav by contract")
    if meta["generation_mode"] == "seeded_code" and verdict_obj["verdict"] == "reject":
        if not meta.get("injection_recipe"):
            raise RowValidationError("seeded_code reject rows must record injection_recipe")
