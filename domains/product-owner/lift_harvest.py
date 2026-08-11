#!/usr/bin/env python3
"""lift_harvest.py — WS4-S2 PO Phase 2 harvest lift (RAW record -> training rows).

Implements the ENTIRE reconstruction contract of
``SPEC-po-phase2-harvest-lift.md`` §2: record routing (§2.1), Mac->host path
remap + integrity (§2.2), Rule R brief extraction + fallback brief +
corpus-document rendering (§2.3), Row A ``ProductRoadmap`` (§2.4), Row B
``EnrichmentBatch`` (§2.5), glue + think synthesis (§2.6), the five gates with
mutation-restarts-chain (§2.7), metadata + provenance (§2.8), args + outputs
(§2.9), and the named edge cases (§2.10).

Deterministic principle (coach-v3 lesson, plan §6): **code renders the JSON;
the LLM writes only the reasoning.** Every assistant JSON field is assembled
from the real artifacts; only the think block and the small glue-field
allowlist (bounded_context, priority_rationale, per-assumption category +
impact_if_wrong) are synthesised.

Teacher note (2026-08-11 bake-off verdict): the spec's default ``--think-model``
is ``gpt-oss-120b`` (Decision B teacher, §2.6) and that default is preserved
per §2.9; the operator will pass ``--think-model product-owner-agent`` per the
2026-08-11 bake-off verdict.

Serving-ops note (operator-side, NOT performed by this script): §2.6 keepalive
discipline — check the ``llama-swap-keepalive.timer`` state, pause it before
the run (``sudo systemctl stop llama-swap-keepalive.timer`` — Rich's sudo),
and restore the prior state after; never assume its state. Reconstructor and
Coach co-reside via ``autobuild_go`` at the :9000 endpoint (spec §6 footnote).

Pure functions importable by tests (no LLM, no I/O): ``normalise_text``,
``first_logical_line``, ``strip_context_flags``, ``rule_r_extract``,
``compose_fallback_brief``, ``feature_title``, ``narrative_block``,
``scope_first_paragraph``, ``scenario_names``, ``intent_line``,
``passes_two_sentences``, ``description_chain``, ``route_record``,
``triple_slug``, ``select_duplicates``, ``remap_path``, ``assign_weight``,
``derive_row_id``, ``serialize_pin``, ``build_row_a_object``,
``build_row_b_object``, ``render_brief_document_body``, ``render_row_a_user``,
``render_row_b_user``, ``derive_golden_slugs``, ``build_metadata``.

Recorded deviations / choices beyond the spec letter (each also marked with a
``DEVIATION-NOTE`` comment at the site):
  * ``--endpoint`` (plus operational ``--coach-temp``, ``--timeout``,
    ``--coach-max-tokens``, ``--think-max-tokens``, ``--goal``,
    ``--golden-dir``, ``--log-level``) are not in §2.9's arg list; the
    endpoint rides the §6 serving-ops footnote (both models at :9000) and the
    rest follow the ``score_golden_set.py`` precedent.
  * §2.6 names only two re-synthesis triggers (Coach non-accept, over-length)
    but says the budget applies "regardless of trigger"; think-text-caused
    gate-1/2 failures (and a belt-and-braces banned-term screen on the think)
    also consume the shared budget here, exhausting into
    ``rejected_rows.jsonl`` (no file is named for gates 1/2).
  * ``--resume`` skips primarily by stored ``(record_feature_id, row_type)``
    pairs (recomputing a row id would require re-running the glue call);
    stored row ids are ALSO honoured as a belt. Deleting a line still retries
    that entry, exactly as §2.6 specifies.
  * ``description_unrecoverable`` writes one stub per row (row_type "A" and
    "B", ``row_id: null``) — §2.6 reserves row_type "record" for the
    record-level glue failure; both stubs block their rows on resume.
  * The golden slug set is derived once at run start (§2.7-5 says "at write
    time"); within one run the two are equivalent, and the write-time
    assertion still runs per training row against that derived set.
  * ``metadata.harvest.row_id`` (§2.6) is stored as the FIRST harvest key;
    ``context_args_source`` (§2.3-1b) is written only when it is ``"rule_r"``.

Gate-3 precondition (§2.7-3): the GOAL Evaluation-Criteria "Shape-aware
criteria routing" note must be in place before any Coach-gated run — this
script aborts if the note is absent from the GOAL file. (Observed 2026-08-11:
``build_coach_prompt`` injects the criteria TABLE, not the section prose;
flagged for the coordinator — the §5.4 note text lives in GOAL prose.)

Never echoes credentials. Never touches NATS. Source repos are READ-ONLY
(§2.2, mirroring the harvester's AC-4).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --- make the factory packages importable when run from anywhere ------------
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
for _p in (_REPO, _REPO / "src", _HERE):
    _sp = str(_p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

# Load .env (OPENAI_API_KEY etc.) the same way score_golden_set.py does — the
# local llama-swap endpoint is OpenAI-compatible and the SDK still requires a
# key. The key value is never printed (binding: never echo credentials).
try:  # pragma: no cover - environment bootstrap
    from dotenv import load_dotenv

    load_dotenv(_REPO / ".env")
except Exception:  # pragma: no cover
    pass
os.environ.setdefault("OPENAI_API_KEY", "sk-local-llama-swap")

import yaml  # noqa: E402

# Vendored serving schemas (§2.7-1) — no runtime import from specialist-agent.
from po_schemas import EnrichmentBatch, ProductRoadmap  # noqa: E402

logger = logging.getLogger("lift_harvest")

# ---------------------------------------------------------------------------
# Constants (spec pins)
# ---------------------------------------------------------------------------

MAC_PREFIX = "/Users/richardwoollcott/Projects/appmilla_github/"
DEFAULT_REPOS_ROOT = "/home/richardwoollcott/Projects/appmilla_github"
DEFAULT_RECORDS = "~/po-dataset/po_history_records.jsonl"
DEFAULT_ENDPOINT = "http://localhost:9000/v1"

CLEAN_BRIEF_MIN_CHARS = 80  # §2.3-1e
INTENT_MAX_CHARS = 100  # §2.3-5
RESYNTHESIS_BUDGET = 2  # §2.6: initial think + at most 2 re-syntheses total
THINK_TARGET_TOKENS = 400  # §2.6
THINK_SHRINK_TOKENS = 200  # §2.7-4
ERA = "pre-fleet-memory-cutover"  # §2.8
DDD_DRIFT_CUTOFF = "2026-05-06"  # §4
BARE_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.&-]*")  # §2.3-1d

# §2.6 pinned category allowlist for glue-filled Assumption.category.
CATEGORY_ALLOWLIST = frozenset(
    {
        "technology",
        "integration",
        "data",
        "process",
        "security",
        "scale",
        "ux",
        "domain",
        "operations",
    }
)

# Both `--context <arg>` and `--context=<arg>` forms; the argument is one
# quoted or bare token (§2.3-1b).
_CONTEXT_FLAG_RE = re.compile(r"--context(?:=|\s+)(\"[^\"]*\"|'[^']*'|\S+)")

# Belt-and-braces screen on the synthesised think text (§2.6: "must never
# mention harvesting, reconstruction, transcripts, or that the answer
# pre-exists"). DEVIATION-NOTE: the spec states this as an instruction to the
# LLM; enforcing it deterministically is an addition — a hit consumes a
# re-synthesis from the shared budget.
_THINK_BANNED_RE = re.compile(
    r"harvest|reconstruct|transcript|pre-?exist", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Text normalisation (spec §2, "Text-normalisation rule")
# ---------------------------------------------------------------------------


def normalise_text(text: str) -> str:
    """Join physical lines with single spaces, collapse whitespace runs, strip."""
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Rule R — brief extraction (§2.3-1, deterministic; pure)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuleRResult:
    """Outcome of Rule R over one ``command_invocation``."""

    brief: str  # normalised remainder (may be "")
    context_flag_args: list[str]  # args of the --context flags removed in 1b
    grade: str  # "clean_brief" | "fallback_brief" (§2.3-1e)


def first_logical_line(invocation: str) -> str:
    """§2.3-1a: join backslash-continued physical lines; keep only the first
    logical line (drops assistant-echo bleed deterministically)."""
    parts: list[str] = []
    for line in invocation.splitlines():
        rstripped = line.rstrip()
        if rstripped.endswith("\\"):
            parts.append(rstripped[:-1])
            continue
        parts.append(line)
        break
    return " ".join(parts)


def strip_context_flags(line: str) -> tuple[str, list[str]]:
    """§2.3-1b: remove every ``--context`` flag + argument; return (line, args).

    Arguments are returned unquoted, in order of appearance.
    """
    args: list[str] = []

    def _repl(m: re.Match[str]) -> str:
        a = m.group(1)
        if len(a) >= 2 and a[0] == a[-1] and a[0] in "\"'":
            a = a[1:-1]
        args.append(a)
        return " "

    cleaned = _CONTEXT_FLAG_RE.sub(_repl, line)
    return cleaned, args


def _quote_rule(rem: str) -> str:
    """§2.3-1d quote rule: content between the first quote and the LAST ``"``
    in the remainder (remainder till end if no closing quote exists)."""
    body = rem[1:]  # drop the opening quote
    last = body.rfind('"')
    return body[:last] if last != -1 else body


def rule_r_extract(invocation: str) -> RuleRResult:
    """Rule R, steps a–e (§2.3-1). Pure and deterministic."""
    line = first_logical_line(invocation)
    line, flag_args = strip_context_flags(line)
    rem = line.strip()

    # Step c: strip the leading whitespace-delimited token that STARTS WITH
    # "/feature-spec" — the whole token, whatever its tail.
    parts = rem.split(maxsplit=1)
    if parts and parts[0].startswith("/feature-spec"):
        rem = parts[1] if len(parts) > 1 else ""
    rem = rem.strip()

    # Step d.
    if rem.startswith('"'):
        brief_raw = _quote_rule(rem)
    else:
        parts = rem.split(maxsplit=1)
        if parts and BARE_TOKEN_RE.fullmatch(parts[0]):
            rem = parts[1] if len(parts) > 1 else ""
            rem = rem.strip()
        if rem.startswith('"'):
            brief_raw = _quote_rule(rem)
        else:
            brief_raw = rem

    # Step e.
    brief = normalise_text(brief_raw)
    grade = "clean_brief" if len(brief) >= CLEAN_BRIEF_MIN_CHARS else "fallback_brief"
    return RuleRResult(brief=brief, context_flag_args=flag_args, grade=grade)


# ---------------------------------------------------------------------------
# .feature / _summary.md lifts (§2.3-2, §2.4, §2.5; pure)
# ---------------------------------------------------------------------------

_NARRATIVE_STOP_PREFIXES = ("#", "@", "Background", "Scenario", "Rule")


def feature_title(feature_text: str) -> str | None:
    """§2.3-2-ii: text after ``Feature:`` on the first line matching
    ``^Feature:`` at column 0 — never the ``# Feature: …`` header comment."""
    for line in feature_text.splitlines():
        if line.startswith("Feature:"):
            return normalise_text(line[len("Feature:"):])
    return None


def narrative_block(feature_text: str) -> str:
    """§2.3-2-iii: all non-empty lines between the ``Feature:`` line and the
    first line whose stripped text starts with ``#``/``@``/``Background``/
    ``Scenario``/``Rule``, normalised as one paragraph."""
    lines = feature_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("Feature:"):
            start = i + 1
            break
    if start is None:
        return ""
    collected: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped and stripped.startswith(_NARRATIVE_STOP_PREFIXES):
            break
        if stripped:
            collected.append(stripped)
    return normalise_text(" ".join(collected))


def scope_first_paragraph(summary_text: str) -> str | None:
    """§2.4: first paragraph after the ``## Scope`` heading of ``_summary.md``,
    normalised; ``None`` when the heading is absent. A paragraph is a maximal
    run of consecutive non-empty lines bounded by blank lines."""
    lines = summary_text.splitlines()
    idx = None
    for i, line in enumerate(lines):
        if line.strip() == "## Scope":
            idx = i + 1
            break
    if idx is None:
        return None
    # Skip blank lines, then collect the first paragraph.
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    para: list[str] = []
    while idx < len(lines) and lines[idx].strip():
        para.append(lines[idx])
        idx += 1
    return normalise_text(" ".join(para)) if para else None


_SCENARIO_LINE_RE = re.compile(r"^Scenario( Outline)?:\s*(.*)$")


def scenario_names(feature_text: str) -> list[str]:
    """§2.5: one string per ``Scenario:`` OR ``Scenario Outline:`` block in
    file order — line-anchored match on stripped lines, comment lines
    excluded; the scenario/outline name verbatim."""
    names: list[str] = []
    for line in feature_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        m = _SCENARIO_LINE_RE.match(stripped)
        if m:
            names.append(m.group(2).strip())
    return names


def passes_two_sentences(text: str) -> bool:
    """The pinned 2-sentence validator, byte-identical logic to
    ``po_schemas.FeatureSpecInput._at_least_two_sentences`` (§2.4)."""
    sentences = re.split(r"[.!?]\s+|[.!?]$", text.strip())
    return len([s for s in sentences if s.strip()]) >= 2


def description_chain(
    scope_p1: str | None, narrative: str
) -> tuple[str | None, str]:
    """§2.4 feature-description fallback chain.

    Base source = Scope ¶1 (or the narrative block when ``## Scope`` is
    absent); on 2-sentence rejection fall back to the narrative block; then to
    the deterministic concatenation (Scope ¶1 + space + narrative); else
    unrecoverable. Returns ``(description | None, source_label)``.
    """
    primary = scope_p1 if scope_p1 is not None else narrative
    if primary and passes_two_sentences(primary):
        return primary, "scope" if scope_p1 is not None else "narrative"
    if narrative and passes_two_sentences(narrative):
        return narrative, "narrative"
    if scope_p1 is not None:
        concatenated = f"{scope_p1} {narrative}".strip()
        if concatenated and passes_two_sentences(concatenated):
            return concatenated, "concatenated"
    return None, "unrecoverable"


def compose_fallback_brief(
    rule_r_remainder: str, title: str, narrative: str
) -> str:
    """§2.3-2 fallback brief: concatenate, in order, separated by blank lines,
    skipping empty/duplicate components: (i) the Rule-R remainder if non-empty
    and not case-insensitively equal to the feature title; (ii) the
    ``.feature`` title; (iii) the ``.feature`` narrative block."""
    components: list[str] = []
    seen: set[str] = set()

    def _add(part: str) -> None:
        norm = normalise_text(part)
        if not norm:
            return
        key = norm.casefold()
        if key in seen:
            return
        seen.add(key)
        components.append(norm)

    if rule_r_remainder and rule_r_remainder.casefold() != title.casefold():
        _add(rule_r_remainder)
    _add(title)
    _add(narrative)
    return "\n\n".join(components)


def intent_line(narrative: str) -> str:
    """§2.3-5: the first sentence of the narrative block (normalised); if it
    exceeds 100 chars, truncate at the last word boundary before 100 and
    append ``…``."""
    text = normalise_text(narrative)
    m = re.match(r"(.+?[.!?])(?:\s|$)", text)
    sentence = m.group(1) if m else text
    if len(sentence) > INTENT_MAX_CHARS:
        cut = sentence[:INTENT_MAX_CHARS]
        sp = cut.rstrip().rfind(" ")
        sentence = (cut[:sp] if sp > 0 else cut).rstrip() + "…"
    return sentence


# ---------------------------------------------------------------------------
# Routing, dedup, remap, weights, row ids (§2.1, §2.2, §2.6, §4; pure)
# ---------------------------------------------------------------------------


def triple_slug(record: dict[str, Any]) -> str | None:
    """The triple's directory slug, from ``paired_artefacts.feature_path``."""
    pa = record.get("paired_artefacts") or {}
    fp = pa.get("feature_path")
    if not fp:
        return None
    return Path(fp).parent.name


def route_record(record: dict[str, Any], golden_slugs: set[str]) -> str:
    """§2.1 precedence order, first match wins: R (partial) > Q (golden
    overlap) > T (train-eligible)."""
    if record.get("curation_richness") == "partial":
        return "R"
    slug = triple_slug(record)
    if slug is not None and slug in golden_slugs:
        return "Q"
    return "T"


def select_duplicates(
    records: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """§2.1 general dedup rule over Tier-T/Q-eligible records sharing a triple
    slug: keep the record with more ``phases_present``; the loser maps to
    ``duplicate_of`` (its winner's feature_id). Ties keep file order
    (DEVIATION-NOTE: tie-breaking is unspecified; first-in-file-order wins)."""
    by_slug: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        slug = triple_slug(rec)
        by_slug.setdefault(slug or f"__none__{id(rec)}", []).append(rec)
    winners: list[dict[str, Any]] = []
    losers: dict[str, str] = {}
    for group in by_slug.values():
        best = max(group, key=lambda r: len(r.get("phases_present") or []))
        for rec in group:
            if rec is best:
                winners.append(rec)
            else:
                losers[rec["feature_id"]] = best["feature_id"]
    # Preserve original ordering.
    order = {id(r): i for i, r in enumerate(records)}
    winners.sort(key=lambda r: order[id(r)])
    return winners, losers


def remap_path(mac_path: str, repos_root: str | Path) -> Path:
    """§2.2: remap the Mac-side prefix onto ``--repos-root``."""
    root = str(repos_root).rstrip("/") + "/"
    if mac_path.startswith(MAC_PREFIX):
        return Path(mac_path.replace(MAC_PREFIX, root, 1))
    return Path(mac_path)


def assign_weight(tier: str, grade: str, session_date: str) -> float:
    """§4 weighting made mechanical. Tier Q -> 0.0; Tier T clean 2.0 /
    fallback 1.5; ×0.75 DDD-drift discount when session_date >= 2026-05-06.
    (The empty "unpaired rubber_stamp" 1.0 bucket is unreachable here — an
    unpaired record has no triple and fails §2.2 with ``triple_missing``.)"""
    if tier == "Q":
        return 0.0
    base = 2.0 if grade == "clean_brief" else 1.5
    if session_date >= DDD_DRIFT_CUTOFF:
        base *= 0.75
    return base


def serialize_pin(obj: dict[str, Any]) -> str:
    """§2.4 serialization pin (Rows A and B): ``json.dumps(obj,
    ensure_ascii=False, indent=2)``; key order = construction order."""
    return json.dumps(obj, ensure_ascii=False, indent=2)


def derive_row_id(source_path: str, row_type: str, assistant_json: str) -> str:
    """§2.6 row id: sha256 of the UTF-8 bytes of
    ``"{record.source_path}\\n{row_type}\\n{assistant_json_bytes}"`` — think
    text deliberately excluded so re-synthesis does not change identity."""
    payload = f"{source_path}\n{row_type}\n{assistant_json}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def derive_golden_slugs(golden_dir: Path) -> set[str]:
    """§2.7-5: slug = basename of the directory of ``reference.summary_path``
    for every JSON line of ``golden_set/*.jsonl`` whose ``reference`` is an
    object containing ``summary_path``; other-shaped lines contribute
    nothing."""
    slugs: set[str] = set()
    for f in sorted(golden_dir.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            ref = obj.get("reference") if isinstance(obj, dict) else None
            if isinstance(ref, dict) and "summary_path" in ref:
                slugs.add(Path(ref["summary_path"]).parent.name)
    return slugs


# ---------------------------------------------------------------------------
# User-message rendering (§2.3-3, §2.3-5; pure)
# ---------------------------------------------------------------------------


def render_brief_document_body(brief: str, context_files: list[str]) -> str:
    """The brief document body under the ``## File:`` heading: ``# Brief`` +
    brief text + (when context_args non-empty) the trailing names-only
    paragraph inside the same document (§2.3-3)."""
    body = f"# Brief\n{brief}"
    if context_files:
        body += (
            "\n\nContext files referenced by this brief (names only, content "
            "not supplied): " + ", ".join(context_files) + "."
        )
    return body


def render_row_a_user(doc_name: str, body: str) -> str:
    """§2.3-3 corpus-document rendering — the Row A user message."""
    return (
        "Mode: extract\n"
        "Decompose the following feature brief. Surface unstated parameters "
        "and policies as assumptions; do not ask questions.\n"
        "\n"
        f"## File: {doc_name}\n"
        f"{body}"
    )


def render_row_b_user(
    doc_name: str,
    body: str,
    title: str,
    bounded_context: str,
    feature_id: str,
    intent: str,
) -> str:
    """§2.3-5: Row B user message — the serving Phase-B scope block (mirrors
    ``player_extract_features.md``) + the same brief document."""
    return (
        "Mode: extract (Phase B — features)\n"
        "\n"
        "## Phase B Scope\n"
        f'Target epic: EPIC-001 — "{title}" (bounded_context: '
        f'"{bounded_context}")\n'
        f"Cited docs: {doc_name}\n"
        "Stub allowlist:\n"
        f'- {feature_id} — "{title}" — intent: "{intent}"\n'
        "\n"
        f"## File: {doc_name}\n"
        f"{body}"
    )


# ---------------------------------------------------------------------------
# Assistant JSON builders (§2.4, §2.5; pure — construction order IS the pin)
# ---------------------------------------------------------------------------


def build_row_a_object(
    record: dict[str, Any],
    *,
    doc_name: str,
    title: str,
    epic_description: str,
    feature_description: str,
    context_args: list[str],
    glue: dict[str, Any],
    yaml_assumptions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Row A ``ProductRoadmap`` per the §2.4 field table (keys in table order;
    optional/None-default fields omitted; schema-required empty lists present
    as ``[]``)."""
    feature = {
        "feature_id": record["feature_id"],
        "title": title,
        "description": feature_description,
        "bounded_context": glue["bounded_context"],
        "source_documents": [doc_name],
        "constraints": [],
        "suggested_context_files": list(context_args),
        "depends_on": [],
        # optional enrichment fields + acceptance_criteria/technical_notes/
        # risks/open_questions/links/field_citations: keys absent (§2.4).
    }
    epic = {
        "id": "EPIC-001",
        "name": title,
        "bounded_context": glue["bounded_context"],
        "description": epic_description,
        "features": [feature],
        "source_documents": [doc_name],
        # field_citations: key absent (§2.4).
    }
    assumptions = []
    for entry in yaml_assumptions:
        aid = entry["id"]
        # Key order follows the §2.4 assumptions-row mapping order (the field
        # tables are the serialization pin's order authority).
        assumptions.append(
            {
                "id": aid,
                "statement": entry["assumption"],  # verbatim
                "confidence": entry["confidence"],
                "source": entry["basis"],  # verbatim
                "category": glue["categories"][aid],
                "impact_if_wrong": glue["impacts"][aid],
            }
        )
    return {
        "project_name": record["repo"],
        "mode": "extract",
        "epics": [epic],
        "feature_spec_inputs": [feature],  # identical object (§2.4)
        "priority_rationale": glue["priority_rationale"],
        "constraints_and_dependencies": [],
        "open_questions": [],
        # change_summary / estimate_unit: keys absent (§2.4).
        "coverage_score": 1.0,
        "source_documents": [
            {
                "filename": doc_name,
                "contribution": (
                    "The feature brief this decomposition was produced from."
                ),
            }
        ],
        "assumptions": assumptions,
    }


def build_row_b_object(
    record: dict[str, Any],
    *,
    doc_name: str,
    feature_description: str,
    context_args: list[str],
    acceptance_criteria: list[str],
) -> dict[str, Any]:
    """Row B ``EnrichmentBatch`` per the §2.5 field table (same serialization
    pin)."""
    citation = {"document": doc_name, "section_path": ["Brief"]}  # no quote
    enrichment = {
        "feature_id": record["feature_id"],
        "description": feature_description,
        "source_documents": [doc_name],
        "constraints": [],
        "technical_notes": [],
        "risks": [],
        "open_questions": [],
        "links": [],
        "depends_on": [],
        "suggested_context_files": list(context_args),
        "type": "Dev: Feature",  # serialized explicitly (§2.5)
        # role/priority/moscow/value/complexity: keys absent (None).
        "acceptance_criteria": list(acceptance_criteria),
        "field_citations": {
            "description": [dict(citation)],
            "acceptance_criteria": [dict(citation)],
        },
    }
    return {
        "project_name": record["repo"],
        "epic_id": "EPIC-001",
        "enrichments": [enrichment],
    }


# ---------------------------------------------------------------------------
# Metadata + provenance (§2.8; pure)
# ---------------------------------------------------------------------------


def build_harvest_block(
    record: dict[str, Any],
    *,
    row_id: str | None,
    grade: str,
    tier: str,
    triple_shas: dict[str, str],
    think_model: str,
    llm_filled_fields: list[str],
    lift_version: str,
    context_args_source: str,
    gate_outcome: str | None = None,
    gate_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The mandatory ``metadata.harvest`` provenance block (§2.8), with the
    §2.6 ``row_id`` stored first and Tier-Q ``gate_outcome`` (+ verdict/counts)
    inserted before ``era``."""
    h: dict[str, Any] = {
        "row_id": row_id,
        "record_feature_id": record["feature_id"],
        "repo": record["repo"],
        "session_date": record["date"],
        "date_basis": record["date_basis"],
        "history_source_path": record["source_path"],
        "curation_richness": record["curation_richness"],
        "reconstruction_grade": grade,
        "brief_trimmed": False,  # §2.3-4: hand-set true by the human skim only
        "tier": tier,
    }
    if context_args_source == "rule_r":
        h["context_args_source"] = "rule_r"  # §2.3-1b
    h["triple"] = {
        "feature_sha256": triple_shas["feature"],
        "assumptions_sha256": triple_shas["assumptions"],
        "summary_sha256": triple_shas["summary"],
    }
    h["think_model"] = think_model
    h["llm_filled_fields"] = list(llm_filled_fields)
    if gate_outcome is not None:  # Tier Q only (§2.7/§2.8)
        h["gate_outcome"] = gate_outcome
        if gate_extra:
            h.update(gate_extra)
    h["era"] = ERA
    h["lift_version"] = lift_version
    return h


def build_metadata(
    row_type: str, weight: float, harvest: dict[str, Any]
) -> dict[str, Any]:
    """§2.8 metadata (Row A: assumption_surfacing/full/assumption_confidence;
    Row B: acceptance_criteria/b/acceptance_criteria)."""
    is_a = row_type == "A"
    return {
        "layer": "behaviour",
        "type": "reasoning",
        "dimension": "assumption_surfacing" if is_a else "acceptance_criteria",
        "mode": "extract",
        "phase": "full" if is_a else "b",
        "source_books": [],
        "topic": "assumption_confidence" if is_a else "acceptance_criteria",
        "source": "harvest",
        "turns": 1,
        "weight": weight,
        "harvest": harvest,
    }


def failure_stub(
    row_id: str | None,
    record_feature_id: str,
    row_type: str,
    disposition: str,
    reason: str,
) -> dict[str, Any]:
    """§2.6 render-time failure-entry stub shape."""
    return {
        "row_id": row_id,
        "record_feature_id": record_feature_id,
        "row_type": row_type,
        "disposition": disposition,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# LLM plumbing (§2.6) — lazy factory imports so pure functions stay light
# ---------------------------------------------------------------------------


def _content_to_text(content: Any) -> str:
    """Coerce a chat-model response content into a plain string (mirrors
    ``score_golden_set.py``)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict):
                parts.append(str(p.get("text", "")))
            else:
                parts.append(str(p))
        return "".join(parts)
    return str(content)


def _invoke_retry(
    model: Any, messages: list[Any], *, retries: int = 4, backoff: float = 2.0
) -> Any:
    """Synchronous invoke with backoff on transient errors (mirrors the
    harness's ``_ainvoke_retry`` transient classification)."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            return model.invoke(messages)
        except Exception as exc:  # noqa: BLE001 - classify by message
            last = exc
            msg = str(exc).lower()
            transient = any(
                t in msg
                for t in (
                    "too many requests",
                    "429",
                    "rate limit",
                    "timeout",
                    "connection",
                    "overloaded",
                    "502",
                    "503",
                )
            )
            if attempt == retries - 1 or not transient:
                raise
            time.sleep(backoff * (2**attempt))
    raise last  # pragma: no cover


def _extract_json_obj(text: str) -> dict[str, Any]:
    """Extract one JSON object from an LLM response (fenced or bare)."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if not m:
        m = re.search(r"(\{.*\})", text, re.S)
    if not m:
        raise ValueError("no JSON object in LLM response")
    return json.loads(m.group(1))


GLUE_SYSTEM_PROMPT = (
    "You are the domain-analysis assistant preparing Product Owner training "
    "material. You will be given a feature brief document, a feature-spec "
    "summary, an assumptions manifest, proposal groups, and why-rationales.\n"
    "Respond with EXACTLY ONE JSON object (a ```json fence is fine) of the "
    "shape:\n"
    "{\n"
    '  "bounded_context": "<short domain-language noun phrase grounded in '
    'the brief>",\n'
    '  "priority_rationale": "<advisory prose grounded in the '
    'why-rationales and summary — never numeric scores>",\n'
    '  "assumptions": {"<assumption id>": {"category": "<one of: '
    "technology, integration, data, process, security, scale, ux, domain, "
    'operations>", "impact_if_wrong": "<one sentence, grounded in that '
    'assumption\'s scenario/basis>"}, ...}\n'
    "}\n"
    "Cover EVERY assumption id you are given. category MUST come from the "
    "allowlist verbatim. Output nothing but the JSON object."
)

THINK_SYSTEM_PROMPT = (
    "You write the hidden reasoning (<think> content) for an expert Product "
    "Owner's answer. You are given the user message the PO received, the "
    "exact JSON answer the PO gives, and supporting context. Write the "
    "reasoning that leads TO that answer — reason forward from the brief "
    "toward the decomposition; do not summarise or restate the JSON. Never "
    "mention that the answer already exists, and never mention harvesting, "
    "reconstruction, sessions, or transcripts. Output ONLY the raw reasoning "
    "text: no <think> tags, no JSON, no code fences, no headings."
)

_ROW_A_THINK_FOCUS = (
    "Reason in this order: (1) the real user/business outcome being pursued; "
    "(2) which unknowns must be surfaced as explicit assumptions (with a "
    "confidence level and a basis) rather than silently resolved; (3) what "
    "is in and out of scope; (4) how to sequence the work by value, risk, "
    "and dependency."
)

_ROW_B_THINK_FOCUS = (
    "Reason about the acceptance-criteria coverage strategy across the "
    "scenario groups — why the key examples, the boundary conditions, the "
    "negative cases, and the edge cases each earn their acceptance criteria."
)


def build_think_user_payload(
    row_type: str,
    user_message: str,
    assistant_json: str,
    glue: dict[str, Any],
    record_ctx: dict[str, Any],
    *,
    shrink: bool,
    feedback: str | None,
) -> str:
    """§2.6 think-call input: the row's full user message + its deterministic
    JSON + the glue + groups/whys/summary."""
    budget = THINK_SHRINK_TOKENS if shrink else THINK_TARGET_TOKENS
    sections = [
        f"## The user message the Product Owner received\n{user_message}",
        "## The exact JSON answer the Product Owner gives\n"
        f"```json\n{assistant_json}\n```",
        "## Glue fields (already final)\n"
        + json.dumps(
            {
                "bounded_context": glue["bounded_context"],
                "priority_rationale": glue["priority_rationale"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        "## Proposal groups\n"
        + json.dumps(record_ctx.get("proposal_groups") or [], ensure_ascii=False),
        "## Why-rationales (NOTE: may be line-clipped mid-sentence)\n"
        + json.dumps(record_ctx.get("why_rationales") or [], ensure_ascii=False),
        f"## Feature-spec summary\n{record_ctx.get('summary_text', '')}",
        "## Task\n"
        + (_ROW_A_THINK_FOCUS if row_type == "A" else _ROW_B_THINK_FOCUS)
        + f" Target AT MOST {budget} tokens. Reason, do not summarise.",
    ]
    if feedback:
        sections.append(f"## Revision feedback on your previous attempt\n{feedback}")
    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Resume state (§2.6 row-id semantics)
# ---------------------------------------------------------------------------


@dataclass
class ResumeState:
    """Stored ids/keys read from all four output files (§2.6)."""

    row_ids: set[str] = field(default_factory=set)
    row_keys: set[tuple[str, str]] = field(default_factory=set)
    blocked_records: set[str] = field(default_factory=set)

    def blocks_row(self, feature_id: str, row_type: str) -> bool:
        return (
            feature_id in self.blocked_records
            or (feature_id, row_type) in self.row_keys
        )


def load_resume_state(paths: list[Path]) -> ResumeState:
    """Read stored row ids / stubs from the four output files. A record-level
    stub blocks both rows until its line is deleted (§2.6)."""
    state = ResumeState()
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("resume: unparseable line in %s (skipped)", path)
                continue
            if "messages" in obj:  # a full rendered row (any outcome)
                meta = obj.get("metadata") or {}
                hv = meta.get("harvest") or {}
                rid = hv.get("row_id")
                if rid:
                    state.row_ids.add(rid)
                fid = hv.get("record_feature_id")
                row_type = "A" if meta.get("phase") == "full" else "B"
                if fid:
                    state.row_keys.add((fid, row_type))
            elif "row_id" in obj:  # a render-time failure stub
                if obj.get("row_id"):
                    state.row_ids.add(obj["row_id"])
                fid = obj.get("record_feature_id")
                row_type = obj.get("row_type")
                if fid and row_type == "record":
                    state.blocked_records.add(fid)
                elif fid and row_type in ("A", "B"):
                    state.row_keys.add((fid, row_type))
    return state


# ---------------------------------------------------------------------------
# The lift runner
# ---------------------------------------------------------------------------


@dataclass
class RecordOutcome:
    """Per-record disposition for the MANIFEST (§2.9: no silent drops)."""

    feature_id: str
    repo: str
    session_date: str
    richness: str
    tier: str
    grade: str = "—"
    weight: str = "—"
    brief_document: str | None = None
    row_outcomes: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class HarvestLift:
    """Impure orchestration around the pure contract functions."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.out_dir = Path(args.out)
        if not self.out_dir.is_absolute():
            self.out_dir = _REPO / self.out_dir
        self.train_path = self.out_dir / "train_harvest.jsonl"
        self.quarantine_path = self.out_dir / "quarantine_golden_overlap.jsonl"
        self.rejected_path = self.out_dir / "rejected_rows.jsonl"
        self.over_length_path = self.out_dir / "over_length.jsonl"
        self.manifest_path = self.out_dir / "MANIFEST-harvest-lift.md"
        self.lift_version = self._git_short_sha()
        self.golden_slugs: set[str] = set()
        self.resume = ResumeState()
        self.outcomes: list[RecordOutcome] = []
        self.q_stubs: list[dict[str, Any]] = []  # Tier-Q stubs -> MANIFEST only
        self.skipped_kinds = 0
        self.total_records = 0
        # Filled by _setup_llm():
        self.goal: Any = None
        self.coach_prompt: str = ""
        self.system_prompt: str = ""
        self.schema_lookup: dict[str, list[str]] = {}
        self.think_llm: Any = None
        self.coach_llm: Any = None
        self.tokenizer: Any = None
        self._parse_coach_verdict: Any = None
        self._training_example_cls: Any = None
        self._normalise_think_tags: Any = None
        self._sys_msg: Any = None
        self._hum_msg: Any = None

    # -- setup ---------------------------------------------------------------

    @staticmethod
    def _git_short_sha() -> str:
        try:
            return (
                subprocess.run(
                    ["git", "-C", str(_REPO), "rev-parse", "--short", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                .stdout.strip()
            )
        except Exception:  # pragma: no cover
            return "unknown"

    def _setup_llm(self) -> None:
        """Lazy factory/tokenizer imports — golden-harness seams exactly as
        ``score_golden_set.py`` uses them (§2.7-3)."""
        from langchain_core.messages import HumanMessage, SystemMessage

        from agents.model_factory import create_model
        from config.models import ModelConfig
        from domain_config.parser import parse_goal_md
        from prompts.coach_prompts import build_coach_prompt
        from synthesis.validator import normalise_think_closing_tags
        from tools.models import TrainingExample

        try:
            from entrypoint.generation_loop import _parse_coach_verdict
        except Exception:  # pragma: no cover - defensive fallback (harness precedent)
            from config.coach_verdict import CoachVerdict

            def _parse_coach_verdict(raw: str):  # type: ignore[misc]
                m = re.search(
                    r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S
                ) or re.search(r"(\{.*\})", raw, re.S)
                if not m:
                    raise ValueError("no JSON object in Coach response")
                return CoachVerdict.model_validate_json(m.group(1))

        self._sys_msg = SystemMessage
        self._hum_msg = HumanMessage
        self._parse_coach_verdict = _parse_coach_verdict
        self._training_example_cls = TrainingExample
        self._normalise_think_tags = normalise_think_closing_tags

        goal_path = Path(self.args.goal)
        # Gate-3 precondition (§2.7-3): the Shape-aware routing note must be
        # in place before any Coach-gated run.
        raw_goal = goal_path.read_text(encoding="utf-8")
        if "Shape-aware criteria routing" not in raw_goal:
            raise SystemExit(
                "ABORT: GOAL.md lacks the 'Shape-aware criteria routing' note "
                "— the §2.7-3 Coach-gate precondition (spec §5.4) is not met."
            )
        self.goal = parse_goal_md(goal_path)
        self.system_prompt = self.goal.system_prompt  # §2, message envelope
        self.coach_prompt = build_coach_prompt(self.goal, target_layer="behaviour")
        # DEVIATION-NOTE (2026-08-11, closes the verify pass's FUNCTIONAL GAP):
        # spec §5.4 assumes "the Coach prompt is built from the Evaluation Criteria
        # section, so the note reaches it" — but build_coach_prompt injects only the
        # criteria TABLE, so the Shape-aware routing note (GOAL prose) never reaches
        # the Coach and gate 3 would structurally reject Row A for AC absence (the
        # RESULTS-po-phase0.md:131 artifact the precondition exists to prevent).
        # Cure: append the note's block verbatim to the built prompt.
        m = re.search(
            r"^### Shape-aware criteria routing.*?(?=^#{2,3} |\Z)",
            raw_goal,
            re.M | re.S,
        )
        if not m:  # the :1085 substring check passed, so this cannot happen
            raise SystemExit("ABORT: routing note present but not extractable")
        self.coach_prompt += "\n\n" + m.group(0).strip()
        # write_output step-9 lookup (§2.7-2): only fields with valid_values.
        self.schema_lookup = {
            f.field: f.valid_values
            for f in self.goal.metadata_schema
            if f.valid_values
        }

        think_cfg = ModelConfig(
            provider="local",
            model=self.args.think_model,
            endpoint=self.args.endpoint,
            temperature=0.0,  # §2.6: temperature 0
            max_tokens=self.args.think_max_tokens,
        )
        coach_cfg = ModelConfig(
            provider="local",
            model=self.args.coach_model,
            endpoint=self.args.endpoint,
            temperature=self.args.coach_temp,
            max_tokens=self.args.coach_max_tokens,
        )
        if think_cfg.model == coach_cfg.model:
            # §2.7-3: Coach distinct from the reconstructor — no self-scoring.
            raise SystemExit(
                "ABORT: --think-model equals --coach-model — D9 discipline "
                "forbids self-scoring (§2.7-3)."
            )
        self.think_llm = create_model(think_cfg, timeout=self.args.timeout)
        self.coach_llm = create_model(coach_cfg, timeout=self.args.timeout)

        # §2.7-4: the REAL tokenizer, no chars-per-token heuristics.
        from transformers import AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(self.args.tokenizer)

    # -- output helpers ------------------------------------------------------

    def _append(self, path: Path, obj: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def _write_stub(
        self, tier: str, stub: dict[str, Any], outcome: RecordOutcome, label: str
    ) -> None:
        """§2.6 failure-entry destinations: Tier T stubs -> rejected_rows.jsonl;
        Tier Q stubs -> the MANIFEST only (tiers never mix)."""
        if tier == "Q":
            self.q_stubs.append(stub)
        else:
            self._append(self.rejected_path, stub)
        outcome.notes.append(label)

    # -- glue call (§2.6 call 1) --------------------------------------------

    def _glue_call(
        self,
        brief_document: str,
        summary_text: str,
        yaml_assumptions: list[dict[str, Any]],
        record: dict[str, Any],
    ) -> dict[str, Any] | None:
        """One glue call per record; one re-ask on category-allowlist
        violation, then None (record-level failure). Fields are frozen after
        this returns (§2.6)."""
        ids = [e["id"] for e in yaml_assumptions]
        payload = "\n\n".join(
            [
                f"## Feature brief document\n{brief_document}",
                f"## Feature-spec summary (_summary.md)\n{summary_text}",
                "## Assumptions manifest entries\n"
                + json.dumps(yaml_assumptions, ensure_ascii=False, indent=2),
                "## Proposal groups\n"
                + json.dumps(
                    record.get("proposal_groups") or [], ensure_ascii=False
                ),
                "## Why-rationales (NOTE: may be line-clipped mid-sentence)\n"
                + json.dumps(
                    record.get("why_rationales") or [], ensure_ascii=False
                ),
                "## Assumption ids requiring category + impact_if_wrong\n"
                + json.dumps(ids),
            ]
        )
        error: str | None = None
        for _attempt in range(2):  # initial + one re-ask (§2.6)
            content = payload if error is None else (
                payload + f"\n\n## Correction required\n{error}"
            )
            resp = _invoke_retry(
                self.think_llm,
                [
                    self._sys_msg(content=GLUE_SYSTEM_PROMPT),
                    self._hum_msg(content=content),
                ],
            )
            try:
                obj = _extract_json_obj(_content_to_text(resp.content))
            except (ValueError, json.JSONDecodeError) as exc:
                error = f"Response was not one parseable JSON object: {exc}"
                continue
            error = self._validate_glue(obj, ids)
            if error is None:
                per = obj.get("assumptions") or {}
                return {
                    "bounded_context": str(obj["bounded_context"]).strip(),
                    "priority_rationale": str(obj["priority_rationale"]).strip(),
                    "categories": {
                        i: str(per[i]["category"]).strip() for i in ids
                    },
                    "impacts": {
                        i: str(per[i]["impact_if_wrong"]).strip() for i in ids
                    },
                }
        logger.warning(
            "glue call failed for %s: %s", record["feature_id"], error
        )
        return None

    @staticmethod
    def _validate_glue(obj: dict[str, Any], ids: list[str]) -> str | None:
        if not str(obj.get("bounded_context") or "").strip():
            return "bounded_context must be a non-empty string."
        if not str(obj.get("priority_rationale") or "").strip():
            return "priority_rationale must be a non-empty string."
        per = obj.get("assumptions")
        if not isinstance(per, dict):
            return "assumptions must be an object keyed by assumption id."
        problems = []
        for i in ids:
            entry = per.get(i)
            if not isinstance(entry, dict):
                problems.append(f"missing entry for {i}")
                continue
            cat = str(entry.get("category") or "").strip()
            if cat not in CATEGORY_ALLOWLIST:
                problems.append(
                    f"{i}: category '{cat}' not in the allowlist "
                    f"{sorted(CATEGORY_ALLOWLIST)}"
                )
            if not str(entry.get("impact_if_wrong") or "").strip():
                problems.append(f"{i}: impact_if_wrong must be one sentence")
        return "; ".join(problems) if problems else None

    # -- think call (§2.6 calls 2/3) ----------------------------------------

    def _think_call(
        self,
        row_type: str,
        user_message: str,
        assistant_json: str,
        glue: dict[str, Any],
        record_ctx: dict[str, Any],
        *,
        shrink: bool,
        feedback: str | None,
    ) -> str:
        payload = build_think_user_payload(
            row_type,
            user_message,
            assistant_json,
            glue,
            record_ctx,
            shrink=shrink,
            feedback=feedback,
        )
        resp = _invoke_retry(
            self.think_llm,
            [
                self._sys_msg(content=THINK_SYSTEM_PROMPT),
                self._hum_msg(content=payload),
            ],
        )
        text = _content_to_text(resp.content).strip()
        # Defensive: the model must emit raw text; strip stray think tags so a
        # tag-echo cannot silently corrupt the §2.7-2 "exactly one block" rule.
        text = text.replace("<think>", "").replace("</think>", "").strip()
        return text

    # -- gates (§2.7) --------------------------------------------------------

    def _schema_gate(self, inner: dict[str, Any], row_type: str) -> str | None:
        """Gate 1: the fenced JSON validates against the vendored models."""
        try:
            if row_type == "A":
                ProductRoadmap.model_validate(inner)
            else:
                EnrichmentBatch.model_validate(inner)
        except Exception as exc:  # noqa: BLE001
            return f"schema gate: {exc}"
        return None

    def _format_gate(self, row: dict[str, Any]) -> str | None:
        """Gate 2: one think block + exactly one ```json fence, strict
        json.loads, TrainingExample envelope, and the write_output step-9
        valid_values check (§2.7-2 — replicated, not the tool)."""
        assistant = row["messages"][2]["content"]
        normalised = self._normalise_think_tags(assistant)  # write_output 6b
        if normalised != assistant:
            return "format gate: malformed <think> closing tag"
        if not assistant.startswith("<think>"):
            return "format gate: assistant must start with <think>"
        if assistant.count("<think>") != 1 or assistant.count("</think>") != 1:
            return "format gate: exactly one <think>…</think> block required"
        after = assistant.split("</think>", 1)[1]
        if after.count("```json") != 1 or after.count("```") != 2:
            return "format gate: exactly one ```json fence required"
        fence = after.split("```json", 1)[1].rsplit("```", 1)[0]
        try:
            json.loads(fence)
        except json.JSONDecodeError as exc:
            return f"format gate: fenced JSON does not strict-parse: {exc}"
        # Belt-and-braces banned-term screen on the think text (§2.6).
        think_text = assistant.split("</think>", 1)[0][len("<think>"):]
        m = _THINK_BANNED_RE.search(think_text)
        if m:
            return (
                "format gate: think text mentions a banned term "
                f"('{m.group(0)}') — never mention harvesting/reconstruction/"
                "transcripts or that the answer pre-exists"
            )
        try:
            self._training_example_cls.model_validate(row)
        except Exception as exc:  # noqa: BLE001
            return f"format gate: TrainingExample envelope invalid: {exc}"
        # write_output step 9 (§2.7-2): only keys with valid_values; skip
        # layer/type (validated by the envelope); None skipped; unknown keys
        # (phase/weight/harvest) ride through untouched.
        metadata = row["metadata"]
        for field_name, valid_values in self.schema_lookup.items():
            if field_name in ("layer", "type"):
                continue
            value = metadata.get(field_name)
            if value is None:
                continue
            if isinstance(value, list):
                invalid = [v for v in value if v not in valid_values]
                if invalid:
                    return (
                        f"format gate: metadata.{field_name} contains invalid "
                        f"values: {invalid}"
                    )
            elif str(value) not in valid_values:
                return (
                    f"format gate: metadata.{field_name} value '{value}' not "
                    "in valid values"
                )
        return None

    def _coach_gate(self, row: dict[str, Any]) -> Any:
        """Gate 3: Coach verdict via the golden-harness seams (§2.7-3).
        Returns the parsed ``CoachVerdict``."""
        example_json = json.dumps(row, ensure_ascii=False)
        last_exc: Exception | None = None
        for _attempt in range(2):
            resp = _invoke_retry(
                self.coach_llm,
                [
                    self._sys_msg(content=self.coach_prompt),
                    self._hum_msg(content=example_json),
                ],
            )
            try:
                return self._parse_coach_verdict(_content_to_text(resp.content))
            except Exception as exc:  # noqa: BLE001 - one re-ask on parse fail
                last_exc = exc
        raise RuntimeError(f"Coach verdict unparseable after retry: {last_exc}")

    def _sequence_gate(self, messages: list[dict[str, str]]) -> int:
        """Gate 4: token length of the full rendered chat in training shape."""
        tokens = self.tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=False
        )
        return len(tokens)

    def _holdout_gate(self, slug: str | None) -> None:
        """Gate 5 (write time, training file only): assert the row's triple
        slug is not in the derived golden slug set."""
        if slug is not None and slug in self.golden_slugs:
            raise RuntimeError(
                f"HOLDOUT-OVERLAP GATE: training row slug '{slug}' is in the "
                "golden set — §2.7-5 forbids the write; aborting the run."
            )

    # -- per-row pipeline ----------------------------------------------------

    def _process_row(
        self,
        row_type: str,
        record: dict[str, Any],
        *,
        tier: str,
        grade: str,
        user_message: str,
        inner: dict[str, Any],
        glue: dict[str, Any],
        record_ctx: dict[str, Any],
        triple_shas: dict[str, str],
        context_args_source: str,
        slug: str | None,
        outcome: RecordOutcome,
    ) -> None:
        """Render one row, run the §2.7 gate chain (any mutation restarts from
        gate 1), and write it to its §2.9 destination."""
        assistant_json = serialize_pin(inner)
        row_id = derive_row_id(record["source_path"], row_type, assistant_json)

        if self.args.resume and (
            row_id in self.resume.row_ids
            or self.resume.blocks_row(record["feature_id"], row_type)
        ):
            outcome.row_outcomes[row_type] = "resume_skip"
            return

        weight = assign_weight(tier, grade, record["date"])
        llm_fields = (
            [
                "epics[0].bounded_context",
                "features[0].bounded_context",
                "priority_rationale",
                "assumptions[].category",
                "assumptions[].impact_if_wrong",
                "think",
            ]
            if row_type == "A"
            # Row B's JSON is fully deterministic; the glue bounded_context
            # appears in its user-message scope block (§2.3-5).
            else ["user_message.phase_b_scope.bounded_context", "think"]
        )

        def _row_with(think: str) -> dict[str, Any]:
            assistant = f"<think>{think}</think>\n\n```json\n{assistant_json}\n```"
            harvest = build_harvest_block(
                record,
                row_id=row_id,
                grade=grade,
                tier=tier,
                triple_shas=triple_shas,
                think_model=self.args.think_model,
                llm_filled_fields=llm_fields,
                lift_version=self.lift_version,
                context_args_source=context_args_source,
            )
            return {
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant},
                ],
                "metadata": build_metadata(row_type, weight, harvest),
            }

        resyntheses_left = RESYNTHESIS_BUDGET
        shrink = False
        feedback: str | None = None
        think = self._think_call(
            row_type, user_message, assistant_json, glue, record_ctx,
            shrink=shrink, feedback=None,
        )
        last_fail: tuple[str, Any] = ("", None)

        while True:
            row = _row_with(think)
            fail: tuple[str, Any] | None = None

            err = self._schema_gate(inner, row_type)  # gate 1
            if err is None:
                err = self._format_gate(row)  # gate 2
                if err is not None:
                    fail = ("format", err)
            else:
                fail = ("schema", err)
            if fail is None:
                verdict = self._coach_gate(row)  # gate 3
                if not verdict.is_accepted:
                    fail = ("coach", verdict)
            if fail is None:
                token_count = self._sequence_gate(row["messages"])  # gate 4
                if token_count > self.args.max_seq_tokens:
                    fail = ("seq", token_count)

            if fail is None:
                self._write_accepted(row, tier, slug, outcome, row_type)
                return

            last_fail = fail
            if resyntheses_left == 0:
                self._write_exhausted(row, tier, last_fail, outcome, row_type)
                return

            # Mutation (think re-synthesis / shrink) — restarts the chain
            # from gate 1 on the next loop iteration (§2.7).
            resyntheses_left -= 1
            kind, detail = fail
            if kind == "seq":
                shrink = True  # §2.7-4: shrink to <= 200 tokens
                feedback = (
                    f"The full example was {detail} tokens against a "
                    f"{self.args.max_seq_tokens} budget — write a much "
                    f"shorter think block (at most {THINK_SHRINK_TOKENS} "
                    "tokens)."
                )
            elif kind == "coach":
                issues = "; ".join(
                    f"[{i.severity}] {i.description}"
                    for i in detail.issues
                ) or detail.quality_assessment
                feedback = f"The reviewer did not accept the example: {issues}"
            else:
                feedback = str(detail)
            logger.info(
                "%s row %s: gate '%s' failed — re-synthesising think "
                "(%d re-syntheses left)",
                record["feature_id"], row_type, kind, resyntheses_left,
            )
            think = self._think_call(
                row_type, user_message, assistant_json, glue, record_ctx,
                shrink=shrink, feedback=feedback,
            )

    def _write_accepted(
        self,
        row: dict[str, Any],
        tier: str,
        slug: str | None,
        outcome: RecordOutcome,
        row_type: str,
    ) -> None:
        if tier == "Q":
            # Every rendered Q row goes ONLY to the quarantine file (§2.7).
            row["metadata"]["harvest"] = self._q_harvest(row, "accepted", None)
            self._append(self.quarantine_path, row)
            outcome.row_outcomes[row_type] = "quarantined (accepted)"
        else:
            self._holdout_gate(slug)  # gate 5, at write time
            self._append(self.train_path, row)
            outcome.row_outcomes[row_type] = "accepted"

    def _write_exhausted(
        self,
        row: dict[str, Any],
        tier: str,
        fail: tuple[str, Any],
        outcome: RecordOutcome,
        row_type: str,
    ) -> None:
        """Re-synthesis budget exhausted: route to the file the last failing
        gate names (§2.6/§2.7). Gate failures on a rendered row write the full
        row + a verdict / token-count sidecar key (§2.6)."""
        kind, detail = fail
        if kind == "coach":
            extra: dict[str, Any] = {"verdict": detail.model_dump()}
            q_outcome, path, label = "rejected", self.rejected_path, "rejected (coach)"
        elif kind == "seq":
            extra = {
                "token_count": detail,
                "max_seq_tokens": self.args.max_seq_tokens,
            }
            q_outcome, path, label = "over_length", self.over_length_path, "over_length"
        else:
            # DEVIATION-NOTE: §2.6 names no file for gate-1/2 exhaustion
            # (deterministic renders should not fail them); rejected_rows is
            # the conservative destination.
            extra = {"verdict": {"error": f"{kind}: {detail}"}}
            q_outcome, path, label = "rejected", self.rejected_path, f"rejected ({kind})"

        if tier == "Q":
            row["metadata"]["harvest"] = self._q_harvest(row, q_outcome, extra)
            self._append(self.quarantine_path, row)
            outcome.row_outcomes[row_type] = f"quarantined ({q_outcome})"
        else:
            sidecar = dict(row)
            sidecar.update(extra)
            self._append(path, sidecar)
            outcome.row_outcomes[row_type] = label

    @staticmethod
    def _q_harvest(
        row: dict[str, Any], gate_outcome: str, extra: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Rebuild the harvest block with §2.7's Tier-Q ``gate_outcome`` (+
        verdict/counts) inserted before ``era`` (§2.8 key order)."""
        old = row["metadata"]["harvest"]
        h: dict[str, Any] = {}
        for k, v in old.items():
            if k == "era":
                h["gate_outcome"] = gate_outcome
                if extra:
                    h.update(extra)
            h[k] = v
        return h

    # -- per-record pipeline -------------------------------------------------

    def _process_record(self, record: dict[str, Any], tier: str) -> None:
        fid = record["feature_id"]
        outcome = RecordOutcome(
            feature_id=fid,
            repo=record["repo"],
            session_date=record["date"],
            richness=record["curation_richness"],
            tier=tier,
        )
        self.outcomes.append(outcome)

        if self.args.resume and fid in self.resume.blocked_records:
            outcome.notes.append(
                "resume: record-level stub present — blocked until the stub "
                "line is deleted (§2.6)"
            )
            outcome.row_outcomes = {"A": "resume_blocked", "B": "resume_blocked"}
            return
        both_done = self.args.resume and all(
            self.resume.blocks_row(fid, rt) for rt in ("A", "B")
        )
        if both_done:
            outcome.row_outcomes = {"A": "resume_skip", "B": "resume_skip"}
            outcome.notes.append("resume: both rows already stored")
            return

        # §2.2 remap + integrity (READ-ONLY on source repos).
        pa = record.get("paired_artefacts") or {}
        paths = {
            "feature": pa.get("feature_path"),
            "assumptions": pa.get("assumptions_path"),
            "summary": pa.get("summary_path"),
        }
        if any(p is None for p in paths.values()):
            stub = failure_stub(
                None, fid, "record", "triple_missing",
                "record carries no full paired_artefacts triple",
            )
            self._write_stub(tier, stub, outcome, "triple_missing (no triple)")
            outcome.row_outcomes = {"A": "triple_missing", "B": "triple_missing"}
            return
        host_paths = {
            k: remap_path(v, self.args.repos_root) for k, v in paths.items()
        }
        missing = [str(p) for p in host_paths.values() if not p.is_file()]
        if missing:
            stub = failure_stub(
                None, fid, "record", "triple_missing",
                f"absent after remap: {missing}",
            )
            self._write_stub(tier, stub, outcome, "triple_missing")
            outcome.row_outcomes = {"A": "triple_missing", "B": "triple_missing"}
            return
        triple_shas = {
            k: hashlib.sha256(p.read_bytes()).hexdigest()
            for k, p in host_paths.items()
        }
        feature_text = host_paths["feature"].read_text(encoding="utf-8")
        summary_text = host_paths["summary"].read_text(encoding="utf-8")
        assumptions_doc = yaml.safe_load(
            host_paths["assumptions"].read_text(encoding="utf-8")
        ) or {}
        # Only the top-level `assumptions:` list renders; any other top-level
        # lists (dropped_assumptions, implementer_hints) are provenance-only
        # (§2.4, §2.10).
        yaml_assumptions = assumptions_doc.get("assumptions") or []

        # §2.3 Rule R + brief.
        rr = rule_r_extract(record.get("command_invocation") or "")
        grade = rr.grade
        outcome.grade = grade
        title = feature_title(feature_text)
        narrative = narrative_block(feature_text)
        if title is None:
            stub = failure_stub(
                None, fid, "record", "triple_missing",
                "no line-anchored `Feature:` title in the .feature file",
            )
            self._write_stub(tier, stub, outcome, "no Feature: line")
            outcome.row_outcomes = {"A": "render_failed", "B": "render_failed"}
            return
        if grade == "clean_brief":
            brief = rr.brief
        else:
            brief = compose_fallback_brief(rr.brief, title, narrative)

        # §2.3-1b: context-args authority.
        record_ctx_args = list(record.get("context_args") or [])
        if rr.context_flag_args and not record_ctx_args:
            context_args = list(rr.context_flag_args)
            context_args_source = "rule_r"
        else:
            context_args = record_ctx_args
            context_args_source = "record"

        # §2.4 descriptions.
        scope_p1 = scope_first_paragraph(summary_text)
        epic_description = scope_p1 if scope_p1 is not None else narrative
        feature_description, desc_source = description_chain(scope_p1, narrative)
        if feature_description is None:
            # DEVIATION-NOTE: one stub per row (A and B), row_id null — §2.6
            # reserves row_type "record" for glue failure; both rows blocked.
            for rt in ("A", "B"):
                stub = failure_stub(
                    None, fid, rt, "description_unrecoverable",
                    "2-sentence validator rejected Scope ¶1, the narrative "
                    "block, and their concatenation",
                )
                self._write_stub(tier, stub, outcome, f"description_unrecoverable ({rt})")
            outcome.row_outcomes = {
                "A": "description_unrecoverable",
                "B": "description_unrecoverable",
            }
            return
        if desc_source == "concatenated":
            outcome.notes.append("description rescued by §2.4 concatenation")

        slug = record.get("feature_slug") or triple_slug(record)
        doc_name = f"{slug}-brief.md"
        body = render_brief_document_body(brief, context_args)
        row_a_user = render_row_a_user(doc_name, body)
        outcome.brief_document = body

        # §2.5 acceptance criteria + advisory-count reconciliation logging.
        names = scenario_names(feature_text)
        declared = (
            record.get("scenario_count"),
            record.get("scenario_count_counted"),
            record.get("scenario_count_declared_sum"),
        )
        if any(d is not None and d != len(names) for d in declared):
            note = (
                f"scenario-count mismatch: counted {len(names)} in .feature "
                f"vs record fields {declared} — logged, never reconciled by "
                "dropping scenarios (§2.5)"
            )
            logger.info("%s: %s", fid, note)
            outcome.notes.append(note)

        # §2.6 call 1 — record-level glue (before any row render).
        glue = self._glue_call(row_a_user, summary_text, yaml_assumptions, record)
        if glue is None:
            stub = failure_stub(
                None, fid, "record", "glue_category_exhaustion",
                "glue call failed category-allowlist validation after one "
                "re-ask (§2.6)",
            )
            self._write_stub(tier, stub, outcome, "glue_category_exhaustion")
            outcome.row_outcomes = {"A": "glue_failed", "B": "glue_failed"}
            return

        weight = assign_weight(tier, grade, record["date"])
        outcome.weight = f"{weight:g}"

        record_ctx = {
            "proposal_groups": record.get("proposal_groups"),
            "why_rationales": record.get("why_rationales"),
            "summary_text": summary_text,
        }

        # Row A.
        inner_a = build_row_a_object(
            record,
            doc_name=doc_name,
            title=title,
            epic_description=epic_description,
            feature_description=feature_description,
            context_args=context_args,
            glue=glue,
            yaml_assumptions=yaml_assumptions,
        )
        self._process_row(
            "A", record, tier=tier, grade=grade, user_message=row_a_user,
            inner=inner_a, glue=glue, record_ctx=record_ctx,
            triple_shas=triple_shas, context_args_source=context_args_source,
            slug=slug, outcome=outcome,
        )

        # Row B.
        row_b_user = render_row_b_user(
            doc_name, body, title, glue["bounded_context"],
            record["feature_id"], intent_line(narrative),
        )
        inner_b = build_row_b_object(
            record,
            doc_name=doc_name,
            feature_description=feature_description,
            context_args=context_args,
            acceptance_criteria=names,
        )
        self._process_row(
            "B", record, tier=tier, grade=grade, user_message=row_b_user,
            inner=inner_b, glue=glue, record_ctx=record_ctx,
            triple_shas=triple_shas, context_args_source=context_args_source,
            slug=slug, outcome=outcome,
        )

    # -- run -----------------------------------------------------------------

    def run(self) -> None:
        records_path = Path(self.args.records).expanduser()
        all_records = [
            json.loads(line)
            for line in records_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.total_records = len(all_records)
        feature_specs = [r for r in all_records if r.get("kind") == "feature_spec"]
        self.skipped_kinds = len(all_records) - len(feature_specs)
        if self.args.limit is not None:
            feature_specs = feature_specs[: self.args.limit]

        # §2.7-5: derive the golden slug set; abort the run if empty.
        self.golden_slugs = derive_golden_slugs(Path(self.args.golden_dir))
        if not self.golden_slugs:
            raise SystemExit(
                "ABORT: derived golden slug set is empty (§2.7-5) — refusing "
                "to run without a holdout-overlap fence."
            )
        logger.info(
            "golden slug set (%d): %s",
            len(self.golden_slugs), sorted(self.golden_slugs),
        )

        if self.args.resume:
            self.resume = load_resume_state(
                [
                    self.train_path,
                    self.quarantine_path,
                    self.rejected_path,
                    self.over_length_path,
                ]
            )
            logger.info(
                "resume: %d row ids, %d row keys, %d blocked records",
                len(self.resume.row_ids),
                len(self.resume.row_keys),
                len(self.resume.blocked_records),
            )

        self._setup_llm()

        # §2.1 routing (+ the general dedup rule over T/Q-eligible records).
        routed: list[tuple[dict[str, Any], str]] = [
            (r, route_record(r, self.golden_slugs)) for r in feature_specs
        ]
        tq_records = [r for r, t in routed if t in ("T", "Q")]
        _winners, losers = select_duplicates(tq_records)

        try:
            for record, tier in routed:
                fid = record["feature_id"]
                if tier == "R":
                    o = RecordOutcome(
                        feature_id=fid, repo=record["repo"],
                        session_date=record["date"],
                        richness=record["curation_richness"], tier="R",
                    )
                    o.notes.append(
                        "reference-only, excluded from training (§2.1 rule 1, "
                        "canon plan §6)"
                    )
                    self.outcomes.append(o)
                    continue
                if fid in losers:
                    o = RecordOutcome(
                        feature_id=fid, repo=record["repo"],
                        session_date=record["date"],
                        richness=record["curation_richness"], tier=tier,
                    )
                    o.notes.append(f"duplicate_of: {losers[fid]} (§2.1 dedup)")
                    self.outcomes.append(o)
                    continue
                logger.info("processing %s (tier %s)", fid, tier)
                self._process_record(record, tier)
        finally:
            self._write_manifest()

    # -- MANIFEST (§2.9) -----------------------------------------------------

    def _write_manifest(self) -> None:
        lines: list[str] = []
        lines.append("# MANIFEST-harvest-lift")
        lines.append("")
        lines.append(
            f"Run: {time.strftime('%Y-%m-%d %H:%M:%S')} · lift_version "
            f"`{self.lift_version}` · spec `SPEC-po-phase2-harvest-lift.md` §2"
        )
        lines.append(
            f"Records file: `{self.args.records}` — {self.total_records} "
            f"records read; {self.skipped_kinds} non-`feature_spec` records "
            "out of the lift's universe (the §2.9 disposition table covers "
            "the `feature_spec` records)."
        )
        if self.args.limit is not None:
            lines.append(
                f"NOTE: `--limit {self.args.limit}` capped the records "
                "processed this run (smoke); the table below covers only "
                "those records."
            )
        lines.append(
            f"Golden slug set ({len(self.golden_slugs)}): "
            + ", ".join(f"`{s}`" for s in sorted(self.golden_slugs))
        )
        lines.append("")
        lines.append("## Per-record dispositions (no silent drops)")
        lines.append("")
        lines.append(
            "| feature_id | repo | session_date | richness | tier | grade | "
            "weight | row A | row B | notes |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for o in self.outcomes:
            lines.append(
                f"| {o.feature_id} | {o.repo} | {o.session_date} | "
                f"{o.richness} | {o.tier} | {o.grade} | {o.weight} | "
                f"{o.row_outcomes.get('A', '—')} | "
                f"{o.row_outcomes.get('B', '—')} | "
                f"{'; '.join(o.notes) if o.notes else '—'} |"
            )
        lines.append("")
        lines.append("## Rendered briefs (§2.3-4 human skim — the only human step)")
        lines.append("")
        lines.append(
            "Review each rendered brief below; hand-delete residual non-brief "
            "text in the row files if found and record `brief_trimmed: true` "
            "in that row's provenance."
        )
        lines.append("")
        for o in self.outcomes:
            if o.brief_document is None:
                continue
            lines.append(f"### {o.feature_id} (tier {o.tier}, {o.grade})")
            lines.append("")
            lines.append("```text")
            lines.append(o.brief_document)
            lines.append("```")
            lines.append("")
        if self.q_stubs:
            lines.append("## Tier-Q render-time failure stubs (MANIFEST only, §2.6)")
            lines.append("")
            for stub in self.q_stubs:
                lines.append(f"- `{json.dumps(stub, ensure_ascii=False)}`")
            lines.append("")
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("MANIFEST written -> %s", self.manifest_path)


# ---------------------------------------------------------------------------
# CLI (§2.9)
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=(
            "WS4-S2 PO harvest lift — reconstructs training rows from the "
            "PO history corpus per SPEC-po-phase2-harvest-lift.md §2. "
            "Outputs under --out: train_harvest.jsonl, "
            "quarantine_golden_overlap.jsonl, rejected_rows.jsonl, "
            "over_length.jsonl, MANIFEST-harvest-lift.md."
        )
    )
    ap.add_argument("--records", default=DEFAULT_RECORDS)
    ap.add_argument("--repos-root", default=DEFAULT_REPOS_ROOT,
                    help="remap target for Mac-side paired_artefacts paths (§2.2)")
    ap.add_argument("--out", default="output/harvest/",
                    help="output dir, resolved against the factory repo root")
    ap.add_argument("--think-model", default="gpt-oss-120b",
                    help="reconstructor for glue + think calls (§2.6). The "
                         "operator passes 'product-owner-agent' per the "
                         "2026-08-11 bake-off verdict.")
    ap.add_argument("--coach-model", default="gemma4-coach",
                    help="gate-3 Coach — MUST differ from --think-model (D9)")
    ap.add_argument("--tokenizer", required=True,
                    help="REQUIRED (§2.7-4): path to the same gemma-4 "
                         "tokenizer artifact Phase-4 training will use")
    ap.add_argument("--max-seq-tokens", type=int, default=4096)
    ap.add_argument("--limit", type=int, default=None,
                    help="cap records processed (smoke)")
    ap.add_argument("--resume", action="store_true",
                    help="skip rows already stored in the four output files "
                         "(§2.6 row-id semantics; delete a line to retry)")
    # DEVIATION-NOTE: the args below are not in §2.9's list — the endpoint
    # rides the spec §6 serving-ops footnote (both models via autobuild_go at
    # :9000); the rest follow the score_golden_set.py precedent.
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT,
                    help="OpenAI-compatible endpoint for BOTH models")
    ap.add_argument("--goal", default=str(_HERE / "GOAL.md"))
    ap.add_argument("--golden-dir", default=str(_HERE / "golden_set"),
                    help="dir whose *.jsonl derive the golden slug set (§2.7-5)")
    ap.add_argument("--coach-temp", type=float, default=0.2)
    ap.add_argument("--coach-max-tokens", type=int, default=2048)
    ap.add_argument("--think-max-tokens", type=int, default=2000)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--log-level", default="INFO")
    return ap


def main() -> None:
    args = build_arg_parser().parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    HarvestLift(args).run()


if __name__ == "__main__":
    main()
