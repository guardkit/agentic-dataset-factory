"""Focused tests for domains/product-owner/filter_trace_export.py stages 3-6.

Synthetic fixtures only — never touches the real raw export or the
specialist-agent traces. The module lives in a hyphenated directory, so it is
loaded via importlib from its file path.
"""

import importlib.util
import json
from pathlib import Path

MODULE_PATH = (Path(__file__).parent.parent / "domains" / "product-owner"
               / "filter_trace_export.py")
_spec = importlib.util.spec_from_file_location("filter_trace_export", MODULE_PATH)
fte = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fte)

LONG = "x" * 200  # comfortably over the 150-char user-content floor


# ---------------------------------------------------------------------------
# Stage 3 — probe drop / user-content extraction
# ---------------------------------------------------------------------------

class TestExtractUserContent:
    def test_role_prefixed_string_single_user_section(self):
        prompt = "user: ## Mode\nscope\n\n## Constraint\nc\n\n## Current Roadmap\nr"
        got = fte.extract_user_content(prompt)
        assert got.startswith("## Mode")
        assert "Constraint" in got

    def test_role_prefixed_string_excludes_system_and_assistant(self):
        prompt = ("system: obey the rubric\n"
                  "user: the actual brief\nspanning two lines\n"
                  "assistant: prior answer noise")
        got = fte.extract_user_content(prompt)
        assert "the actual brief" in got
        assert "spanning two lines" in got
        assert "obey the rubric" not in got
        assert "prior answer noise" not in got

    def test_plain_string_without_role_markers_is_all_user(self):
        assert fte.extract_user_content("just a bare brief") == "just a bare brief"

    def test_messages_list_counts_only_user_parts(self):
        prompt = [
            {"role": "system", "content": "sys " * 100},
            {"role": "user", "content": "short"},
            {"role": "assistant", "content": "asst " * 100},
        ]
        assert fte.extract_user_content(prompt) == "short"

    def test_messages_dict_wrapper(self):
        prompt = {"messages": [{"role": "user", "content": "wrapped brief"}]}
        assert fte.extract_user_content(prompt) == "wrapped brief"

    def test_json_encoded_messages_string(self):
        prompt = json.dumps([{"role": "user", "content": "encoded brief"}])
        assert fte.extract_user_content(prompt) == "encoded brief"

    def test_content_block_list_shape(self):
        prompt = [{"role": "user",
                   "content": [{"type": "text", "text": "block one"},
                               {"type": "text", "text": "block two"}]}]
        got = fte.extract_user_content(prompt)
        assert "block one" in got and "block two" in got

    def test_none_prompt_is_empty(self):
        assert fte.extract_user_content(None) == ""


class TestProbeDrop:
    def test_trivial_short_user_content_dropped(self):
        assert fte.is_trivial_prompt("user: ## Mode\nscope\n\n## Constraint\nc") is True

    def test_long_user_content_kept(self):
        assert fte.is_trivial_prompt("user: " + LONG) is False

    def test_exactly_149_chars_is_trivial(self):
        assert fte.is_trivial_prompt("user: " + "a" * 149) is True

    def test_exactly_150_chars_survives(self):
        assert fte.is_trivial_prompt("user: " + "a" * 150) is False

    def test_long_system_content_does_not_rescue_short_user(self):
        prompt = [{"role": "system", "content": LONG},
                  {"role": "user", "content": "tiny"}]
        assert fte.is_trivial_prompt(prompt) is True


# ---------------------------------------------------------------------------
# Stage 4 — shape tag
# ---------------------------------------------------------------------------

class TestClassifyShape:
    def test_roadmap_modes(self):
        for mode in ("greenfield", "idea", "scope", "evolve"):
            completion = '```json\n{\n  "project_name": "P",\n  "mode": "%s"\n}' % mode
            assert fte.classify_shape(completion) == mode

    def test_mode_regex_tolerates_whitespace(self):
        assert fte.classify_shape('{"mode"  :   "idea"}') == "idea"

    def test_unknown_mode_value_is_not_a_roadmap(self):
        assert fte.classify_shape('{"mode": "sideways"}') == "other"

    def test_feature_spec_needs_all_three_markers(self):
        spec = ("Feature: Login\n  Scenario: happy path\n"
                "## Assumptions\n- A1: users exist")
        assert fte.classify_shape(spec) == "feature-spec"
        assert fte.classify_shape("Feature: Login\n  Scenario: happy path") == "other"
        assert fte.classify_shape("Feature: Login\nassumptions only") == "other"

    def test_feature_plan_markers(self):
        plan = ("id: FEAT-1\ntasks:\n  - file_path: "
                ".guardkit/features/FEAT-1.yaml\n  - file_path: "
                "tasks/backlog/t/TASK-1.md")
        assert fte.classify_shape(plan) == "feature-plan"
        assert fte.classify_shape(".guardkit/features only") == "other"
        assert fte.classify_shape("tasks/backlog only") == "other"

    def test_mode_wins_over_feature_markers(self):
        text = ('{"mode": "greenfield"} Feature: X Scenario assumptions '
                ".guardkit/features tasks/backlog")
        assert fte.classify_shape(text) == "greenfield"

    def test_empty_completion_is_other(self):
        assert fte.classify_shape("") == "other"


# ---------------------------------------------------------------------------
# Stage 5 — distinct-brief dedup
# ---------------------------------------------------------------------------

def _row(sid, iteration, prompt, record_id=None):
    return {"record_id": record_id or f"{sid}-{iteration}", "session_id": sid,
            "iteration": iteration, "prompt": prompt, "completion": "c",
            "dataset": "player_imitation", "mask_prompt": True,
            "prompt_mask_label": -100}


BRIEF_A = "user: ## Problem Statement\nBuild a CRM for SMBs" + " pad" * 40
BRIEF_B = "user: ## Problem Statement\nBuild an LMS for schools" + " pad" * 40


class TestDedupSessions:
    def test_shared_brief_keeps_highest_score_all_iterations(self):
        rows = [
            _row("aaa", 1, BRIEF_A), _row("aaa", 2, BRIEF_A + "\nfeedback"),
            _row("bbb", 1, BRIEF_A),
        ]
        hashes = fte.build_brief_hashes(rows)
        assert hashes["aaa"] == hashes["bbb"]
        meta = {"aaa": {"score": 0.9, "date": "2026-07-15"},
                "bbb": {"score": 0.7, "date": "2026-07-10"}}
        kept, log = fte.dedup_sessions(rows, hashes, meta)
        assert {r["session_id"] for r in kept} == {"aaa"}
        assert len(kept) == 2  # BOTH iterations of the kept session survive
        assert log == [{"session_id": "bbb", "duplicate_of": "aaa",
                        "brief_hash": hashes["bbb"], "final_score": 0.7,
                        "session_date": "2026-07-10"}]

    def test_score_tie_breaks_to_earliest_date(self):
        rows = [_row("old", 1, BRIEF_A), _row("new", 1, BRIEF_A)]
        hashes = fte.build_brief_hashes(rows)
        meta = {"old": {"score": 0.8, "date": "2026-07-01"},
                "new": {"score": 0.8, "date": "2026-07-20"}}
        kept, log = fte.dedup_sessions(rows, hashes, meta)
        assert {r["session_id"] for r in kept} == {"old"}
        assert log[0]["session_id"] == "new"
        assert log[0]["duplicate_of"] == "old"

    def test_distinct_briefs_all_survive(self):
        rows = [_row("aaa", 1, BRIEF_A), _row("bbb", 1, BRIEF_B)]
        hashes = fte.build_brief_hashes(rows)
        kept, log = fte.dedup_sessions(
            rows, hashes,
            {"aaa": {"score": 0.9, "date": "d"}, "bbb": {"score": 0.1, "date": "d"}})
        assert len(kept) == 2 and log == []

    def test_brief_hash_uses_first_iteration_user_content(self):
        # Iteration 2 prompts differ (feedback appended) but the brief is the
        # iteration-1 user content, so the two sessions still collide.
        rows = [
            _row("aaa", 1, BRIEF_A), _row("aaa", 2, BRIEF_A + "\ncoach says X"),
            _row("bbb", 1, BRIEF_A), _row("bbb", 2, BRIEF_A + "\ncoach says Y"),
        ]
        hashes = fte.build_brief_hashes(rows)
        assert hashes["aaa"] == hashes["bbb"]

    def test_three_way_collision_keeps_exactly_one(self):
        rows = [_row(s, 1, BRIEF_A) for s in ("s1", "s2", "s3")]
        hashes = fte.build_brief_hashes(rows)
        meta = {"s1": {"score": 0.6, "date": "2026-07-03"},
                "s2": {"score": 0.95, "date": "2026-07-05"},
                "s3": {"score": 0.8, "date": "2026-07-01"}}
        kept, log = fte.dedup_sessions(rows, hashes, meta)
        assert {r["session_id"] for r in kept} == {"s2"}
        assert {d["session_id"] for d in log} == {"s1", "s3"}
        assert all(d["duplicate_of"] == "s2" for d in log)


# ---------------------------------------------------------------------------
# Stage 6 — leakage gate
# ---------------------------------------------------------------------------

class TestLeakageGate:
    def test_clean_row_passes(self):
        row = _row("aaa", 1, BRIEF_A)
        assert fte.leakage_hits(row) == []

    def test_each_listed_variant_is_caught(self):
        variants = ["FinProxy", "finproxy", "RoundRoute", "roundroute",
                    "HomeStretch", "homestretch", "kiln-firing", "kiln firing",
                    "member-directory-search", "member directory search",
                    "po-held-0"]
        for term in variants:
            row = _row("aaa", 1, "user: brief")
            row["completion"] = f"roadmap mentioning {term} here"
            assert fte.leakage_hits(row), f"variant not caught: {term}"

    def test_hit_in_prompt_also_caught(self):
        row = _row("aaa", 1, "user: extend the FinProxy ledger flows")
        assert "finproxy" in fte.leakage_hits(row)

    def test_uppercase_estate_name_caught(self):
        row = _row("aaa", 1, "user: brief")
        row["completion"] = "the HOMESTRETCH release"
        assert "homestretch" in fte.leakage_hits(row)

    def test_matched_terms_are_reported(self):
        row = _row("aaa", 1, "user: brief")
        row["completion"] = "FinProxy meets RoundRoute during kiln firing"
        hits = fte.leakage_hits(row)
        assert set(hits) >= {"finproxy", "roundroute", "kiln firing"}


# ---------------------------------------------------------------------------
# Stage 7 (light) — stamp is non-destructive
# ---------------------------------------------------------------------------

class TestStampRow:
    def test_stamp_preserves_masking_fields_and_adds_harvest(self):
        row = _row("aaa", 2, BRIEF_A)
        out = fte.stamp_row(row, shape="greenfield", trace_file="-aaa.json",
                            filter_version="abc1234")
        assert out["mask_prompt"] is True
        assert out["prompt_mask_label"] == -100
        assert out["source"] == "harvest"
        assert out["weight"] == 1.0
        assert out["harvest"] == {
            "session_id": "aaa", "trace_file": "-aaa.json",
            "shape": "greenfield", "iteration": 2,
            "export_receipt": "receipt-2026-08-11.json",
            "filter_version": "abc1234",
        }
        # input row untouched
        assert "harvest" not in row and "source" not in row

    def test_existing_source_and_weight_win(self):
        row = _row("aaa", 1, BRIEF_A)
        row["source"] = "flywheel"
        row["weight"] = 0.5
        out = fte.stamp_row(row, shape="other", trace_file="t.json",
                            filter_version="abc1234")
        assert out["source"] == "flywheel"
        assert out["weight"] == 0.5
