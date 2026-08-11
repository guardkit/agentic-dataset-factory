"""WS4-S2 PO Phase 2 harvest lift — pure-function tests (spec §6 Tests row).

Covers, with fixture data derived from the spec's own worked examples
(SPEC-po-phase2-harvest-lift.md §1, §2.3, §2.10):

  * Rule R brief extraction (§2.3-1): echo-bleed drop, ``--context`` /
    ``--context=`` removal, ``/feature-spec`` whole-token strip (incl. the
    FEAT-FORGE-008 ``/feature-spec-FEAT-FORGE-004-history.md`` garbage tail),
    quoted-brief extraction (last-quote rule), bare feature-id strip, and the
    >=80-char clean/fallback threshold.
  * Tier routing precedence (§2.1): partial -> R, golden-slug -> Q, else T;
    the duplicate-slug richer-phases rule.
  * Fallback-brief composition (§2.3-2): component order + dedup-vs-title.
  * The §2.4 serialization pin: ensure_ascii=False, indent=2, key order =
    field-table order, omit-vs-[] semantics (Rows A and B).
  * Weight assignment (§4): clean 2.0 / fallback 1.5, the 0.75 DDD-drift
    discount at session_date >= 2026-05-06, Tier-Q 0.0 (+ the Phase-4 drop
    rule's arithmetic rationale).
  * Row-id derivation (§2.6): sha256 preimage, think excluded from identity.

No LLM, no network, no NATS, no writes outside pytest tmp dirs.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_PO_DIR = _REPO / "domains" / "product-owner"
if str(_PO_DIR) not in sys.path:
    sys.path.insert(0, str(_PO_DIR))

import lift_harvest as lh  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures — derived from the spec's worked examples (§1, §2.3, §2.10).
# The corpus is private (DF-008); these reproduce the *anatomies* the spec
# pins: invocation shapes, echo-bleed text, flag forms, slugs, dates.
# ---------------------------------------------------------------------------

# §1: "three records (FEAT-FORGE-002, FEAT-FORGE-006, JARVIS-003) additionally
# captured a second physical line of assistant echo text ('I'll execute the
# /feature-spec command… Starting Phase 1…'), which is transcript bleed".
ECHO_BLEED = (
    "I'll execute the /feature-spec command for this feature. "
    "Starting Phase 1: Requirements analysis..."
)

# JARVIS-003 anatomy: prose brief (262 chars in the corpus; >=80 here), a
# backslash-continued --context flag, then the echo line as a SECOND physical
# line (§1, §2.10 "Assistant-echo bleed").
JARVIS_003_BRIEF = (
    "Build the fleet registration and specialist dispatch flow over NATS so "
    "that every specialist agent announces itself on startup and the "
    "dispatcher can route feature work to a registered specialist by role."
)
JARVIS_003_INVOCATION = (
    f'/feature-spec JARVIS-003 "{JARVIS_003_BRIEF}" \\\n'
    "  --context docs/architecture/fleet-registration.md\n"
    f"{ECHO_BLEED}\n"
)

# FEAT-FORGE-002 anatomy (§1, §2.10 "Id+context-only invocations"): id +
# context flags only — the real brief WAS the context files; echo bleed on a
# second physical line. Rule R must reduce this to an empty brief.
FORGE_002_INVOCATION = (
    "/feature-spec FEAT-FORGE-002 "
    "--context docs/forge/pipeline-stages.md "
    "--context docs/forge/task-contract.md\n"
    f"{ECHO_BLEED}\n"
)

# wire-the-production anatomy (§1, §2.3-1b, §2.10): a real 58-char quoted
# title + 16 ``--context=``-form flags the harvester never parsed into
# context_args.
WIRE_TITLE_58 = "Wire the production pipeline orchestrator end-to-end fully"
WIRE_CONTEXT_FLAGS = [f"docs/pipeline/context-{i:02d}.md" for i in range(16)]
WIRE_INVOCATION = (
    f'/feature-spec "{WIRE_TITLE_58}" '
    + " ".join(f"--context={p}" for p in WIRE_CONTEXT_FLAGS)
    + "\n"
)

# FEAT-FORGE-008 anatomy (Tier Q; §2.3-1c, §2.10 "Garbage /feature-spec-…
# token"): the whole token is stripped, whatever its tail.
FORGE_008_INVOCATION = (
    "/feature-spec-FEAT-FORGE-004-history.md FEAT-FORGE-008 "
    "--context docs/forge/mode-b.md\n"
)

# autobuild-runner-style .feature (§2.3-2, §2.10): header COMMENT vs real
# ``Feature:`` line; a five-line hard-wrapped story with a folded purpose
# clause; Background/Scenario/Scenario Outline/comment lines.
AUTOBUILD_FEATURE = """\
# Feature: autobuild-runner (header comment — never the title source)
@autobuild
Feature: Autobuild runner drives queued tasks to completion
  As a factory operator
  I want the autobuild runner to pick up queued feature tasks
  and drive each one through build, verify, and merge
  so that completed work lands without a human
  babysitting every step of the pipeline

  Background:
    Given a registered repository with a queued task

  Scenario: Runner picks up the oldest queued task first
    Given two queued tasks
    When the runner starts
    Then the older task is dispatched first

  # Scenario: a commented-out scenario never counts
  Scenario Outline: Runner retries transient failures up to <n> times
    Given a task that fails transiently
    When the runner executes it
    Then it retries <n> times
"""

AUTOBUILD_TITLE = "Autobuild runner drives queued tasks to completion"
AUTOBUILD_NARRATIVE = (
    "As a factory operator I want the autobuild runner to pick up queued "
    "feature tasks and drive each one through build, verify, and merge so "
    "that completed work lands without a human babysitting every step of "
    "the pipeline"
)

# §1 golden-set overlap: the 6 slugs (7 records) derived by joining
# reference.summary_path slugs against paired feature-path slugs.
GOLDEN_SLUGS = {
    "mode-b-feature-and-mode-c-review-fix",
    "feat-jarvis-005-build-queue-dispatch-to-forge",
    "feat-jarvis-004-fleet-registration-and-specialist-dispatch",
    "architect-ingestion-v2",
    "graphiti-student-model",
    "primary-text-rag-and-quote-verifier",
}

MAC_ROOT = "/Users/richardwoollcott/Projects/appmilla_github"


def _record(
    feature_id: str,
    richness: str,
    slug: str | None = None,
    phases: list[str] | None = None,
    repo: str = "specialist-agent",
    date: str = "2026-03-14",
) -> dict:
    rec: dict = {
        "feature_id": feature_id,
        "curation_richness": richness,
        "repo": repo,
        "date": date,
        "date_basis": "session-file-mtime",
        "source_path": f"~/po-dataset/histories/{feature_id}.md",
    }
    if slug is not None:
        rec["paired_artefacts"] = {
            "feature_path": f"{MAC_ROOT}/{repo}/features/{slug}/{slug}.feature",
            "assumptions_path": f"{MAC_ROOT}/{repo}/features/{slug}/{slug}_assumptions.yaml",
            "summary_path": f"{MAC_ROOT}/{repo}/features/{slug}/{slug}_summary.md",
        }
    if phases is not None:
        rec["phases_present"] = phases
    return rec


# ---------------------------------------------------------------------------
# Rule R — §2.3-1
# ---------------------------------------------------------------------------


class TestRuleRBriefExtraction:
    def test_echo_bleed_dropped_by_first_logical_line(self):
        """§2.3-1a: the second physical line of assistant echo never reaches
        the brief (FEAT-FORGE-002/006, JARVIS-003 anatomy)."""
        res = lh.rule_r_extract(JARVIS_003_INVOCATION)
        assert "I'll execute" not in res.brief
        assert "Starting Phase 1" not in res.brief
        assert res.brief == JARVIS_003_BRIEF
        assert res.grade == "clean_brief"

    def test_echo_bleed_dropped_on_id_and_context_only_record(self):
        """FEAT-FORGE-002: id + context flags + echo -> empty brief (§1: 'the
        six FEAT-FORGE-00x records … reduce to empty')."""
        res = lh.rule_r_extract(FORGE_002_INVOCATION)
        assert res.brief == ""
        assert res.grade == "fallback_brief"
        assert res.context_flag_args == [
            "docs/forge/pipeline-stages.md",
            "docs/forge/task-contract.md",
        ]

    def test_backslash_continuation_joins_into_one_logical_line(self):
        """§2.3-1a: backslash-continued physical lines are one logical line;
        the continued --context flag is still removed."""
        line = lh.first_logical_line(JARVIS_003_INVOCATION)
        assert "docs/architecture/fleet-registration.md" in line
        assert "I'll execute" not in line

    def test_context_space_form_removed(self):
        cleaned, args = lh.strip_context_flags(
            "/feature-spec FEAT-X --context docs/a.md --context docs/b.md"
        )
        assert "--context" not in cleaned
        assert args == ["docs/a.md", "docs/b.md"]

    def test_context_equals_form_removed(self):
        """§2.3-1b: the ``--context=<path>`` form (wire-the-production's 16
        unparsed flags) is removed identically."""
        cleaned, args = lh.strip_context_flags(
            "/feature-spec --context=docs/a.md --context=docs/b.md"
        )
        assert "--context" not in cleaned
        assert args == ["docs/a.md", "docs/b.md"]

    def test_context_quoted_argument_unquoted(self):
        """§2.3-1b: the argument is one quoted or bare token; quotes are
        stripped from the captured arg."""
        cleaned, args = lh.strip_context_flags(
            '/feature-spec --context "docs/with space.md" tail'
        )
        assert args == ["docs/with space.md"]
        assert "--context" not in cleaned
        assert "tail" in cleaned

    def test_wire_the_production_sixteen_equals_flags(self):
        """§2.10: harvester missed the ``--context=`` flags — Rule R must
        capture all 16 (they become the context list, source ``rule_r``)."""
        res = lh.rule_r_extract(WIRE_INVOCATION)
        assert res.context_flag_args == WIRE_CONTEXT_FLAGS
        assert len(res.context_flag_args) == 16

    def test_wire_the_production_58_char_quoted_title_is_fallback(self):
        """§1: wire-the-production reduces to its 58-char quoted title — under
        the 80-char threshold, so fallback_brief."""
        assert len(WIRE_TITLE_58) == 58
        res = lh.rule_r_extract(WIRE_INVOCATION)
        assert res.brief == WIRE_TITLE_58
        assert res.grade == "fallback_brief"

    def test_feature_spec_token_stripped_plain_and_dotted(self):
        """§2.3-1c: the whole leading token starting with /feature-spec is
        stripped — handles ``/feature-spec`` and ``/feature-spec.``."""
        assert lh.rule_r_extract('/feature-spec "x y z"').brief == "x y z"
        assert lh.rule_r_extract('/feature-spec. "x y z"').brief == "x y z"

    def test_forge_008_garbage_tail_does_not_leak(self):
        """§2.3-1c: FEAT-FORGE-008's ``/feature-spec-FEAT-FORGE-004-history.md``
        token is stripped whole — its tail must not leak into a brief."""
        res = lh.rule_r_extract(FORGE_008_INVOCATION)
        assert res.brief == ""
        assert "FEAT-FORGE-004" not in res.brief
        assert "history" not in res.brief
        assert res.context_flag_args == ["docs/forge/mode-b.md"]
        assert res.grade == "fallback_brief"

    def test_quoted_brief_extraction_uses_last_quote(self):
        """§2.3-1d: the brief is the content between the first quote and the
        LAST quote in the remainder — inner quotes survive."""
        inv = (
            '/feature-spec fine-tune-comparision "Compare the "small" and '
            '"large" fine-tune runs against the frozen golden set and report '
            'per-metric deltas for the review sitting"'
        )
        res = lh.rule_r_extract(inv)
        assert res.brief.startswith('Compare the "small" and "large"')
        assert res.brief.endswith("review sitting")
        assert res.grade == "clean_brief"

    def test_bare_feature_id_stripped_before_prose(self):
        """§2.3-1d: one leading bare token matching the feature-id grammar is
        stripped; the rest is the brief (deterministic-session-planner
        anatomy — 90-char prose brief)."""
        prose = (
            "Plan every tutoring session deterministically from the recorded "
            "curriculum state and history"
        )
        res = lh.rule_r_extract(f"/feature-spec deterministic-session-planner {prose}")
        assert res.brief == prose
        assert res.grade == "clean_brief"

    def test_bare_feature_id_with_ampersand_stripped(self):
        """§2.10: ``&`` in a feature id is legal in the id-token grammar
        (NATS-Fleet-Registration&Specialist-Dispatch)."""
        inv = (
            '/feature-spec NATS-Fleet-Registration&Specialist-Dispatch '
            f'"{JARVIS_003_BRIEF}"'
        )
        res = lh.rule_r_extract(inv)
        assert res.brief == JARVIS_003_BRIEF
        assert "NATS-Fleet" not in res.brief

    def test_bare_id_then_quoted_brief(self):
        """§2.3-1d second branch: id stripped, then the quote rule applies."""
        res = lh.rule_r_extract('/feature-spec JARVIS-003 "a short quoted brief"')
        assert res.brief == "a short quoted brief"

    def test_threshold_80_chars_is_clean(self):
        """§2.3-1e: >= 80 chars -> clean_brief (exact boundary)."""
        res = lh.rule_r_extract('/feature-spec "' + "a" * 80 + '"')
        assert len(res.brief) == 80
        assert res.grade == "clean_brief"

    def test_threshold_79_chars_is_fallback(self):
        """§2.3-1e: < 80 chars -> fallback_brief (one under the boundary)."""
        res = lh.rule_r_extract('/feature-spec "' + "a" * 79 + '"')
        assert len(res.brief) == 79
        assert res.grade == "fallback_brief"

    def test_brief_is_normalised(self):
        """§2 text-normalisation rule applies to the extracted brief:
        whitespace runs collapse, ends stripped."""
        res = lh.rule_r_extract('/feature-spec "  spaced   out\tbrief  "')
        assert res.brief == "spaced out brief"


# ---------------------------------------------------------------------------
# Tier routing — §2.1
# ---------------------------------------------------------------------------


class TestTierRouting:
    def test_partial_routes_r_even_when_golden(self):
        """§2.1 rule 1 beats rule 2 (first match wins): the paired partial
        duplicate ``architect-ingestion-v2-llama-swap-…`` is Tier R although
        its slug is in the golden set."""
        rec = _record(
            "architect-ingestion-v2-llama-swap-plan",
            "partial",
            slug="architect-ingestion-v2",
        )
        assert lh.route_record(rec, GOLDEN_SLUGS) == "R"

    def test_unpaired_partial_routes_r(self):
        """§2.10: FEAT-FORGE-003 (empty invocation, mode unclear, partial)
        never reaches the brief rule — Tier R."""
        rec = _record("FEAT-FORGE-003", "partial")
        assert lh.route_record(rec, GOLDEN_SLUGS) == "R"

    def test_golden_slug_routes_q(self):
        """§2.1 rule 2: FEAT-RAG-08 pairs to architect-ingestion-v2, a golden
        slug -> Tier Q."""
        rec = _record("FEAT-RAG-08", "rubber_stamp", slug="architect-ingestion-v2")
        assert lh.route_record(rec, GOLDEN_SLUGS) == "Q"

    def test_graphiti_student_model_routes_q(self):
        rec = _record(
            "Graphiti-Student-Model", "rubber_stamp", slug="graphiti-student-model"
        )
        assert lh.route_record(rec, GOLDEN_SLUGS) == "Q"

    def test_non_golden_rubber_stamp_routes_t(self):
        rec = _record(
            "JARVIS-003",
            "rubber_stamp",
            slug="feat-jarvis-003-conductor-activation",
        )
        assert lh.route_record(rec, GOLDEN_SLUGS) == "T"

    def test_rubber_stamp_without_triple_routes_t(self):
        """No paired_artefacts -> no slug -> rule 3 (the §2.2 triple_missing
        check catches it later; routing itself is T)."""
        rec = _record("fine-tune-comparision", "rubber_stamp")
        assert lh.route_record(rec, GOLDEN_SLUGS) == "T"

    def test_triple_slug_derivation(self):
        rec = _record("FEAT-RAG-08", "rubber_stamp", slug="architect-ingestion-v2")
        assert lh.triple_slug(rec) == "architect-ingestion-v2"
        assert lh.triple_slug(_record("X", "rubber_stamp")) is None

    def test_duplicate_slug_richer_phases_wins(self):
        """§2.1 general dedup rule: two records sharing a triple slug —
        reconstruct only the one with more phases_present; the loser is
        logged as duplicate_of the winner (the FEAT-RAG-08 vs
        architect-ingestion-v2-llama-swap pair's shape)."""
        rag08 = _record(
            "FEAT-RAG-08",
            "rubber_stamp",
            slug="architect-ingestion-v2",
            phases=["propose", "review", "accept", "summary"],
        )
        dup = _record(
            "architect-ingestion-v2-llama-swap-plan",
            "partial",
            slug="architect-ingestion-v2",
            phases=["propose"],
        )
        other = _record(
            "JARVIS-003",
            "rubber_stamp",
            slug="feat-jarvis-003-conductor-activation",
            phases=["propose", "accept"],
        )
        winners, losers = lh.select_duplicates([rag08, dup, other])
        assert winners == [rag08, other]  # original order preserved
        assert losers == {"architect-ingestion-v2-llama-swap-plan": "FEAT-RAG-08"}

    def test_duplicate_slug_tie_keeps_file_order(self):
        """Tie-breaking is unspecified in the spec; the implementation records
        first-in-file-order as its DEVIATION-NOTE — pin that behaviour."""
        a = _record("A-first", "rubber_stamp", slug="same-slug", phases=["p1"])
        b = _record("B-second", "rubber_stamp", slug="same-slug", phases=["p2"])
        winners, losers = lh.select_duplicates([a, b])
        assert winners == [a]
        assert losers == {"B-second": "A-first"}


# ---------------------------------------------------------------------------
# Fallback-brief composition — §2.3-2
# ---------------------------------------------------------------------------


class TestFallbackBriefComposition:
    def test_feature_title_ignores_header_comment(self):
        """§2.3-2-ii: line-anchored ``^Feature:`` at column 0 — never the
        ``# Feature: …`` header comment."""
        assert lh.feature_title(AUTOBUILD_FEATURE) == AUTOBUILD_TITLE

    def test_narrative_block_five_line_hardwrapped_story(self):
        """§2.3-2-iii + §1: autobuild-runner's five-line hard-wrapped story
        with a folded purpose clause normalises to one paragraph, stopping at
        Background."""
        assert lh.narrative_block(AUTOBUILD_FEATURE) == AUTOBUILD_NARRATIVE
        assert "Background" not in lh.narrative_block(AUTOBUILD_FEATURE)

    def test_empty_remainder_composes_title_then_narrative(self):
        """FEAT-FORGE-00x / autobuild-runner path: empty Rule-R remainder ->
        title + blank line + narrative, in that order."""
        out = lh.compose_fallback_brief("", AUTOBUILD_TITLE, AUTOBUILD_NARRATIVE)
        assert out.split("\n\n") == [AUTOBUILD_TITLE, AUTOBUILD_NARRATIVE]

    def test_real_quoted_title_kept_first(self):
        """wire-the-production (§2.3-2-i, §2.10): the real 58-char quoted
        text differs from the .feature title, so it is kept as the FIRST
        component."""
        feature_title = "Wire the production pipeline orchestrator end to end"
        narrative = (
            "As a factory operator I want the production pipeline wired "
            "end-to-end so that a queued task flows to a merged feature"
        )
        out = lh.compose_fallback_brief(WIRE_TITLE_58, feature_title, narrative)
        assert out.split("\n\n") == [WIRE_TITLE_58, feature_title, narrative]

    def test_remainder_equal_to_title_is_deduplicated(self):
        """§2.3-2-i: the remainder is dropped when case-insensitively equal to
        the feature title."""
        out = lh.compose_fallback_brief(
            AUTOBUILD_TITLE.upper(), AUTOBUILD_TITLE, AUTOBUILD_NARRATIVE
        )
        assert out.split("\n\n") == [AUTOBUILD_TITLE, AUTOBUILD_NARRATIVE]

    def test_duplicate_components_skipped(self):
        """§2.3-2: 'skipping empty/duplicate components' — a narrative that
        equals the title (case-insensitively) appears once."""
        out = lh.compose_fallback_brief("", AUTOBUILD_TITLE, AUTOBUILD_TITLE.lower())
        assert out == AUTOBUILD_TITLE

    def test_components_are_normalised(self):
        out = lh.compose_fallback_brief("", "Title  with   runs", "narrative\ntext")
        assert out == "Title with runs\n\nnarrative text"


# ---------------------------------------------------------------------------
# Serialization pin — §2.4 (Rows A and B)
# ---------------------------------------------------------------------------

ROW_A_RECORD = _record(
    "NATS-Fleet-Registration&Specialist-Dispatch",
    "rubber_stamp",
    slug="feat-jarvis-004-fleet-registration-and-specialist-dispatch",
)

GLUE = {
    "bounded_context": "fleet dispatch",
    "priority_rationale": (
        "Registration precedes dispatch — the fleet cannot route work to "
        "unregistered specialists…"
    ),
    "categories": {"A-1": "integration", "A-2": "process"},
    "impacts": {
        "A-1": "Dispatch messages would be published to subjects nobody subscribes to.",
        "A-2": "Specialists would silently drop work items on restart.",
    },
}

YAML_ASSUMPTIONS = [
    {
        "id": "A-1",
        "assumption": "NATS subjects follow the fleet.<role> naming convention",
        "confidence": "medium",
        "basis": "observed in the broker configuration",
        "scenario": "provenance-only, never rendered",
        "human_response": "confirmed",
    },
    {
        "id": "A-2",
        "assumption": "Specialists re-announce themselves after a restart",
        "confidence": "high",
        "basis": "startup handler registers on connect",
        "human_response": "signed-off-with-implementation-evidence",
        "signed_off_at": "2026-04-02",
    },
]

DOC_NAME = "feat-jarvis-004-fleet-registration-and-specialist-dispatch-brief.md"

EPIC_DESCRIPTION = (
    "Fleet registration and dispatch over NATS. Specialists announce "
    "themselves and receive routed feature work."
)
FEATURE_DESCRIPTION = EPIC_DESCRIPTION
CONTEXT_ARGS = ["docs/architecture/fleet-registration.md"]


def _row_a():
    return lh.build_row_a_object(
        ROW_A_RECORD,
        doc_name=DOC_NAME,
        title="Fleet registration and specialist dispatch",
        epic_description=EPIC_DESCRIPTION,
        feature_description=FEATURE_DESCRIPTION,
        context_args=CONTEXT_ARGS,
        glue=GLUE,
        yaml_assumptions=YAML_ASSUMPTIONS,
    )


def _row_b():
    return lh.build_row_b_object(
        ROW_A_RECORD,
        doc_name=DOC_NAME,
        feature_description=FEATURE_DESCRIPTION,
        context_args=CONTEXT_ARGS,
        acceptance_criteria=lh.scenario_names(AUTOBUILD_FEATURE),
    )


class TestSerializationPin:
    def test_ensure_ascii_false(self):
        """§2.4 pin: ensure_ascii=False — non-ASCII bytes (em dash, ellipsis)
        appear raw, never \\uXXXX-escaped."""
        s = lh.serialize_pin(_row_a())
        assert "—" in s
        assert "…" in s
        assert "\\u2014" not in s
        assert "\\u2026" not in s

    def test_indent_two(self):
        """§2.4 pin: indent=2."""
        s = lh.serialize_pin(_row_a())
        lines = s.splitlines()
        assert lines[0] == "{"
        assert lines[1] == '  "project_name": "specialist-agent",'
        assert s == json.dumps(_row_a(), ensure_ascii=False, indent=2)

    def test_row_a_top_level_key_order(self):
        """§2.4 field-table order, with change_summary/estimate_unit omitted."""
        obj = json.loads(lh.serialize_pin(_row_a()))
        assert list(obj.keys()) == [
            "project_name",
            "mode",
            "epics",
            "feature_spec_inputs",
            "priority_rationale",
            "constraints_and_dependencies",
            "open_questions",
            "coverage_score",
            "source_documents",
            "assumptions",
        ]

    def test_row_a_epic_key_order_and_field_citations_absent(self):
        obj = json.loads(lh.serialize_pin(_row_a()))
        epic = obj["epics"][0]
        assert list(epic.keys()) == [
            "id",
            "name",
            "bounded_context",
            "description",
            "features",
            "source_documents",
        ]
        assert epic["id"] == "EPIC-001"
        assert epic["source_documents"] == [DOC_NAME]  # plain strings (§5.7)

    def test_row_a_feature_key_order_omit_vs_empty_list(self):
        """§2.4: optional/None-default fields = key ABSENT; schema-required
        empty lists = ``[]`` present."""
        obj = json.loads(lh.serialize_pin(_row_a()))
        feat = obj["epics"][0]["features"][0]
        assert list(feat.keys()) == [
            "feature_id",
            "title",
            "description",
            "bounded_context",
            "source_documents",
            "constraints",
            "suggested_context_files",
            "depends_on",
        ]
        assert feat["constraints"] == []
        assert feat["depends_on"] == []
        assert feat["suggested_context_files"] == CONTEXT_ARGS
        # Omitted: enrichment fields + the Phase-B territory fields.
        for absent in (
            "type",
            "role",
            "priority",
            "moscow",
            "value",
            "complexity",
            "acceptance_criteria",
            "technical_notes",
            "risks",
            "open_questions",
            "links",
            "field_citations",
        ):
            assert absent not in feat, absent

    def test_row_a_omitted_keys_not_in_bytes(self):
        s = lh.serialize_pin(_row_a())
        assert '"change_summary"' not in s
        assert '"estimate_unit"' not in s
        assert '"field_citations"' not in s  # absent at epic AND feature level

    def test_row_a_required_empty_lists_in_bytes(self):
        s = lh.serialize_pin(_row_a())
        assert '"constraints_and_dependencies": []' in s
        assert '"open_questions": []' in s

    def test_row_a_feature_spec_inputs_identical_object(self):
        """§2.4: feature_spec_inputs = [ features[0] ] — the identical object
        (the flatten validator requires the same feature_id set)."""
        obj = _row_a()
        assert obj["feature_spec_inputs"][0] == obj["epics"][0]["features"][0]

    def test_row_a_ampersand_feature_id_verbatim(self):
        """§2.10: ``&`` is legal JSON string content — feature_id verbatim."""
        obj = json.loads(lh.serialize_pin(_row_a()))
        assert (
            obj["epics"][0]["features"][0]["feature_id"]
            == "NATS-Fleet-Registration&Specialist-Dispatch"
        )

    def test_row_a_roadmap_source_documents_are_objects(self):
        """§2.4/§5.7: objects at roadmap level ONLY."""
        obj = json.loads(lh.serialize_pin(_row_a()))
        assert obj["source_documents"] == [
            {
                "filename": DOC_NAME,
                "contribution": "The feature brief this decomposition was produced from.",
            }
        ]
        assert obj["coverage_score"] == 1.0

    def test_row_a_assumptions_order_and_provenance_only_keys(self):
        """§2.4 assumptions row: file order; id/statement/confidence/source
        verbatim from the yaml; category + impact_if_wrong glue-filled; the
        yaml's scenario/human_response/signed_off_at NEVER rendered."""
        obj = json.loads(lh.serialize_pin(_row_a()))
        assumptions = obj["assumptions"]
        assert [a["id"] for a in assumptions] == ["A-1", "A-2"]
        assert list(assumptions[0].keys()) == [
            "id",
            "statement",
            "confidence",
            "source",
            "category",
            "impact_if_wrong",
        ]
        assert assumptions[0]["statement"] == YAML_ASSUMPTIONS[0]["assumption"]
        assert assumptions[0]["source"] == YAML_ASSUMPTIONS[0]["basis"]
        assert assumptions[0]["category"] == "integration"
        s = lh.serialize_pin(_row_a())
        for banned in ("human_response", "signed_off_at", "provenance-only"):
            assert banned not in s, banned

    def test_row_b_top_level_key_order(self):
        """§2.5 field-table order."""
        obj = json.loads(lh.serialize_pin(_row_b()))
        assert list(obj.keys()) == ["project_name", "epic_id", "enrichments"]
        assert obj["epic_id"] == "EPIC-001"

    def test_row_b_enrichment_key_order_omit_vs_empty_list(self):
        obj = json.loads(lh.serialize_pin(_row_b()))
        enr = obj["enrichments"][0]
        assert list(enr.keys()) == [
            "feature_id",
            "description",
            "source_documents",
            "constraints",
            "technical_notes",
            "risks",
            "open_questions",
            "links",
            "depends_on",
            "suggested_context_files",
            "type",
            "acceptance_criteria",
            "field_citations",
        ]
        for empty in (
            "constraints",
            "technical_notes",
            "risks",
            "open_questions",
            "links",
            "depends_on",
        ):
            assert enr[empty] == [], empty
        assert enr["type"] == "Dev: Feature"  # serialized explicitly (§2.5)
        for absent in ("role", "priority", "moscow", "value", "complexity"):
            assert absent not in enr, absent

    def test_row_b_acceptance_criteria_are_scenario_names(self):
        """§2.5: one string per Scenario/Scenario Outline in file order, name
        verbatim; comment lines excluded; NO Given/When/Then bodies."""
        names = lh.scenario_names(AUTOBUILD_FEATURE)
        assert names == [
            "Runner picks up the oldest queued task first",
            "Runner retries transient failures up to <n> times",
        ]
        enr = json.loads(lh.serialize_pin(_row_b()))["enrichments"][0]
        assert enr["acceptance_criteria"] == names
        assert not any("Given" in ac for ac in enr["acceptance_criteria"])

    def test_row_b_field_citations_shape_no_quote(self):
        """§2.5: C = {document, section_path: ["Brief"]}, no ``quote`` key."""
        enr = json.loads(lh.serialize_pin(_row_b()))["enrichments"][0]
        citation = {"document": DOC_NAME, "section_path": ["Brief"]}
        assert enr["field_citations"] == {
            "description": [citation],
            "acceptance_criteria": [citation],
        }
        assert "quote" not in lh.serialize_pin(_row_b())


# ---------------------------------------------------------------------------
# Weight assignment — §4
# ---------------------------------------------------------------------------


class TestWeightAssignment:
    def test_tier_t_clean_brief_is_2_0(self):
        assert lh.assign_weight("T", "clean_brief", "2026-02-14") == 2.0

    def test_tier_t_fallback_brief_is_1_5(self):
        assert lh.assign_weight("T", "fallback_brief", "2026-04-30") == 1.5

    def test_ddd_discount_applies_at_cutoff(self):
        """§4: ×0.75 when session_date >= 2026-05-06 — fine-tune-comparision
        (clean, 2026-05-06) and autobuild-runner (fallback, 2026-05-06)."""
        assert lh.assign_weight("T", "clean_brief", "2026-05-06") == 1.5  # 2.0×0.75
        assert lh.assign_weight("T", "fallback_brief", "2026-05-06") == 1.125  # 1.5×0.75

    def test_ddd_discount_not_applied_day_before(self):
        assert lh.assign_weight("T", "clean_brief", "2026-05-05") == 2.0
        assert lh.assign_weight("T", "fallback_brief", "2026-05-05") == 1.5

    def test_ddd_discount_after_cutoff(self):
        """§1: the latest rubber_stamp session is 2026-05-10 — still
        discounted."""
        assert lh.assign_weight("T", "fallback_brief", "2026-05-10") == 1.125

    def test_tier_q_always_zero(self):
        """§4: Tier Q (quarantine) -> 0.0, whatever the grade or date."""
        assert lh.assign_weight("Q", "clean_brief", "2026-03-01") == 0.0
        assert lh.assign_weight("Q", "fallback_brief", "2026-05-10") == 0.0

    def test_copies_arithmetic_documents_the_phase4_drop_rule(self):
        """§4: copies = max(1, round(weight)) in the Phase-4 assembly. The
        table's copies column reproduces (2.0->2, 1.5->2, 1.125->1) AND the
        rule's hazard: max(1, round(0.0)) == 1, which is exactly why the
        assembly MUST drop weight == 0.0 rows (belt-and-braces against an
        accidentally merged quarantine row)."""

        def copies(weight: float) -> int:
            return max(1, round(weight))

        assert copies(2.0) == 2
        assert copies(1.5) == 2
        assert copies(1.125) == 1
        assert copies(3.0) == 3  # reserved `considered` bucket
        assert copies(1.0) == 1  # future unpaired-rubber_stamp bucket
        # The hazard the drop rule exists for:
        assert copies(0.0) == 1


# ---------------------------------------------------------------------------
# Row-id derivation — §2.6
# ---------------------------------------------------------------------------


class TestRowIdDerivation:
    SOURCE_PATH = "~/po-dataset/histories/JARVIS-003.md"

    def test_sha256_preimage_exact(self):
        """§2.6: sha256 of the UTF-8 bytes of
        ``"{record.source_path}\\n{row_type}\\n{assistant_json_bytes}"``."""
        inner = lh.serialize_pin(_row_a())
        expected = hashlib.sha256(
            f"{self.SOURCE_PATH}\nA\n{inner}".encode("utf-8")
        ).hexdigest()
        assert lh.derive_row_id(self.SOURCE_PATH, "A", inner) == expected

    def test_think_text_excluded_from_identity(self):
        """§2.6: the think text is deliberately excluded, so re-synthesis does
        not change identity — two assistants differing ONLY in their think
        block carry the same row id."""
        inner = lh.serialize_pin(_row_b())
        assistant_v1 = f"<think>first synthesis attempt</think>\n\n```json\n{inner}\n```"
        assistant_v2 = f"<think>a completely different re-synthesised reasoning</think>\n\n```json\n{inner}\n```"

        def fenced_json(assistant: str) -> str:
            return assistant.split("```json\n", 1)[1].rsplit("\n```", 1)[0]

        id_v1 = lh.derive_row_id(self.SOURCE_PATH, "B", fenced_json(assistant_v1))
        id_v2 = lh.derive_row_id(self.SOURCE_PATH, "B", fenced_json(assistant_v2))
        assert id_v1 == id_v2

    def test_row_type_and_source_path_change_identity(self):
        inner = lh.serialize_pin(_row_a())
        id_a = lh.derive_row_id(self.SOURCE_PATH, "A", inner)
        id_b = lh.derive_row_id(self.SOURCE_PATH, "B", inner)
        id_other = lh.derive_row_id("~/po-dataset/histories/other.md", "A", inner)
        assert id_a != id_b
        assert id_a != id_other

    def test_assistant_json_bytes_change_identity(self):
        """The §2.4 serialization pin is load-bearing for identity: any change
        to the inner JSON bytes changes the id; re-serializing the same object
        does not."""
        inner1 = lh.serialize_pin(_row_a())
        inner2 = lh.serialize_pin(_row_a())  # same object, same bytes
        assert lh.derive_row_id(self.SOURCE_PATH, "A", inner1) == lh.derive_row_id(
            self.SOURCE_PATH, "A", inner2
        )
        mutated = _row_a()
        mutated["coverage_score"] = 0.9
        assert lh.derive_row_id(
            self.SOURCE_PATH, "A", lh.serialize_pin(mutated)
        ) != lh.derive_row_id(self.SOURCE_PATH, "A", inner1)
