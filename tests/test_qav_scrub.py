"""L2 deep-regeneration layer 3 — non-determinism scrub (render-collapse root-cause, 2026-07-21).

Hermetic: pure dict transforms, zero guardkit / model / network. Proves the two properties the
lane needs — (i) two regenerations that differ ONLY in wall-clock jitter / per-run paths scrub to
byte-identical bundles (deterministic row_id + jitter can't defeat the divergence guard), and
(ii) a genuinely-divergent regeneration (a real defect surfacing in a failing test) keeps its
distinguishing evidence (the guard still fires / passes correctly).
"""

from __future__ import annotations

import json

from qav.scrub import (
    CANONICALIZE_LIST_KEYS,
    NONDET_TEXT_SUBS,
    NONDETERMINISTIC_BUNDLE_KEYS,
    scrub_nondeterministic_bundle,
)


def _hash(b: dict) -> str:
    return json.dumps(b, sort_keys=True, ensure_ascii=False)


# --------------------------------------------------------------------------------------
# Documented key drop.
# --------------------------------------------------------------------------------------
def test_duration_seconds_dropped_recursively():
    b = {
        "honesty": {"discrepancies": []},
        "independent_tests": {"duration_seconds": 3.9355, "ran": True, "passed": False},
        "runtime_parity": {"nested": {"duration_seconds": 0.01, "keep": 1}},
    }
    s = scrub_nondeterministic_bundle(b)
    assert "duration_seconds" not in s["independent_tests"]
    assert "duration_seconds" not in s["runtime_parity"]["nested"]
    assert s["independent_tests"] == {"ran": True, "passed": False}
    assert s["runtime_parity"]["nested"]["keep"] == 1
    assert NONDETERMINISTIC_BUNDLE_KEYS == frozenset({"duration_seconds"})


def test_scrub_does_not_mutate_argument():
    b = {"honesty": {}, "independent_tests": {"duration_seconds": 1.0}}
    _ = scrub_nondeterministic_bundle(b)
    assert b["independent_tests"]["duration_seconds"] == 1.0  # original untouched


# --------------------------------------------------------------------------------------
# Documented text normalizations — jitter erased, defect signal preserved.
# --------------------------------------------------------------------------------------
def test_pytest_timing_normalized_defect_names_preserved():
    tail = (
        "FAILED tests/orchestrator/test_wiring_seam_real_factory.py::TestX::test_a\n"
        "assert result.wiring is not None\n"
        "========== 4 failed, 1 passed in 2.73s ==========\n"
        "0.34s call tests/orchestrator/test_wiring_seam_real_factory.py::TestX::test_a\n"
    )
    b = {"honesty": {}, "independent_test_classification": {"raw_output_excerpt": tail}}
    s = scrub_nondeterministic_bundle(b)["independent_test_classification"]["raw_output_excerpt"]
    # jitter gone
    assert "2.73s" not in s and "0.34s" not in s
    assert "in <t>s" in s and "<t>s call" in s
    # defect signal intact — the failing-test node id, the assert message, the counts
    assert "FAILED tests/orchestrator/test_wiring_seam_real_factory.py::TestX::test_a" in s
    assert "assert result.wiring is not None" in s
    assert "4 failed, 1 passed" in s


def test_basetemp_and_tmp_paths_normalized():
    b = {"honesty": {}, "independent_tests": {"raw_output":
        "cmd: python -m pytest tests --basetemp=/tmp/pytest-of-rich/pytest-931/coach-independent0\n"
        "rootdir contents in /tmp/pytest-of-rich/pytest-931\n"}}
    s = scrub_nondeterministic_bundle(b)["independent_tests"]["raw_output"]
    assert "pytest-931" not in s and "pytest-of-rich" not in s
    assert "<tmp>" in s or "<pytest-tmp>" in s


def test_memory_addresses_normalized():
    b = {"honesty": {}, "independent_tests": {"raw_output": "<MagicMock id='0x7f3a9c1d2e40'>"}}
    s = scrub_nondeterministic_bundle(b)["independent_tests"]["raw_output"]
    assert "0x7f3a9c1d2e40" not in s and "0x<addr>" in s


def test_worktree_path_normalized_when_supplied():
    wt = "/home/x/output/qa-verifier/_scratch/guardkit/TASK-A/R-DC03-mockseam"
    b = {"honesty": {}, "independent_tests": {"raw_output": f"rootdir: {wt}\ncollected 5 items"}}
    s = scrub_nondeterministic_bundle(b, worktree_path=wt)["independent_tests"]["raw_output"]
    assert wt not in s and "<worktree>" in s
    # relative node ids (the signal) untouched
    assert "collected 5 items" in s


# --------------------------------------------------------------------------------------
# The two lane-critical properties.
# --------------------------------------------------------------------------------------
def _run_bundle(*, duration, secs, tmp_n, addr, wt):
    """A regenerated bundle whose ONLY per-run-variable surfaces are the jitter args."""
    return {
        "honesty": {"discrepancies": [], "honesty_score": 1.0},
        "gathering_status": "complete",
        "independent_test_classification": {
            "failure_class": "code",
            "raw_output_excerpt": (
                "FAILED tests/orchestrator/test_wiring_seam_real_factory.py::TestX::test_a\n"
                f"========== 4 failed, 1 passed in {secs}s ==========\n"
            ),
        },
        "independent_tests": {
            "duration_seconds": duration,
            "raw_output": (
                f"rootdir: {wt}\n"
                f"--basetemp=/tmp/pytest-of-rich/pytest-{tmp_n}/coach-independent0\n"
                f"<obj at 0x{addr}>\n"
                "FAILED tests/orchestrator/test_wiring_seam_real_factory.py::TestX::test_a\n"
            ),
        },
    }


def test_two_jitter_only_runs_scrub_identical():
    # The DETERMINISM property: two runs of the SAME mutated tree differ ONLY in jitter -> after
    # scrub they are byte-identical (identical row_id; timing can't split a re-run).
    wt = "/s/guardkit/TASK-A/R-DC03-mockseam"
    run1 = _run_bundle(duration=3.9355, secs="2.73", tmp_n=931, addr="7f3a9c1d2e40", wt=wt)
    run2 = _run_bundle(duration=3.7012, secs="2.75", tmp_n=204, addr="7f00aabb1122", wt=wt)
    assert _hash(run1) != _hash(run2)  # raw: divergent by jitter
    s1 = scrub_nondeterministic_bundle(run1, worktree_path=wt)
    s2 = scrub_nondeterministic_bundle(run2, worktree_path=wt)
    assert _hash(s1) == _hash(s2)  # scrubbed: identical


def test_genuine_divergence_survives_scrub():
    # The GUARD property: a bundle whose evidence genuinely differs (different FAILED tests) does
    # NOT scrub equal to a clean control — the divergence the guard relies on is preserved.
    wt = "/s/guardkit/TASK-A/R-DC03-mockseam"
    mutated = _run_bundle(duration=3.9, secs="2.7", tmp_n=1, addr="7f01", wt=wt)
    control = {
        "honesty": {"discrepancies": [], "honesty_score": 1.0},
        "gathering_status": "complete",
        "independent_test_classification": {"failure_class": None, "raw_output_excerpt":
            "========== 5 passed in 2.7s ==========\n"},
        "independent_tests": {"duration_seconds": 3.9,
            "raw_output": f"rootdir: {wt}\n5 passed\n"},
    }
    sm = scrub_nondeterministic_bundle(mutated, worktree_path=wt)
    sc = scrub_nondeterministic_bundle(control, worktree_path=wt)
    assert _hash(sm) != _hash(sc)  # real evidence divergence preserved


def test_scrub_idempotent():
    wt = "/s/guardkit/TASK-A/R"
    b = _run_bundle(duration=1.0, secs="0.5", tmp_n=7, addr="7fabcd", wt=wt)
    once = scrub_nondeterministic_bundle(b, worktree_path=wt)
    twice = scrub_nondeterministic_bundle(once, worktree_path=wt)
    assert _hash(once) == _hash(twice)


def test_text_subs_are_compiled_patterns():
    # Guard the documented list shape (a regression here would silently drop a normalization).
    assert len(NONDET_TEXT_SUBS) >= 5
    for pat, repl in NONDET_TEXT_SUBS:
        assert hasattr(pat, "sub") and isinstance(repl, str)


# --------------------------------------------------------------------------------------
# Documented list-order canonicalization — the 2026-07-22 study_tutor mocked_seam finding.
# guardkit's analyzer returns findings in a NON-DETERMINISTIC ORDER; the set is identical.
# --------------------------------------------------------------------------------------
def test_findings_list_order_canonicalized():
    # Two runs of the SAME tree: identical mocked_seam finding SET, PERMUTED order (the exact shape
    # of the study_tutor two-run bridge diff). After scrub they must hash byte-identical.
    run1 = {
        "gathering_status": "complete",
        "mocked_seam": {"findings": [
            {"symbol": "pipeline_module", "lineno": 1382, "why": "Mock of non-authored target: pipeline_module"},
            {"symbol": "adapter_module", "lineno": 1462, "why": "Mock of non-authored target: adapter_module"},
        ]},
    }
    run2 = {
        "gathering_status": "complete",
        "mocked_seam": {"findings": [
            {"symbol": "adapter_module", "lineno": 1462, "why": "Mock of non-authored target: adapter_module"},
            {"symbol": "pipeline_module", "lineno": 1382, "why": "Mock of non-authored target: pipeline_module"},
        ]},
    }
    assert _hash(run1) != _hash(run2)  # raw: order-split
    s1 = scrub_nondeterministic_bundle(run1)
    s2 = scrub_nondeterministic_bundle(run2)
    assert _hash(s1) == _hash(s2)  # scrubbed: order canonicalized -> identical
    assert "findings" in CANONICALIZE_LIST_KEYS


def test_findings_canonicalization_preserves_a_real_set_difference():
    # A GENUINELY different finding SET (an extra finding — a real defect surfacing) must STILL
    # differ after canonicalization: sorting removes order-noise, never a real divergence.
    control = {"mocked_seam": {"findings": [
        {"symbol": "a", "lineno": 1, "why": "x"},
    ]}}
    reject = {"mocked_seam": {"findings": [
        {"symbol": "a", "lineno": 1, "why": "x"},
        {"symbol": "b", "lineno": 2, "why": "y"},  # the real extra finding
    ]}}
    sc = scrub_nondeterministic_bundle(control)
    sr = scrub_nondeterministic_bundle(reject)
    assert _hash(sc) != _hash(sr)


def test_findings_canonicalization_uses_scrubbed_element_content():
    # The sort key is computed on the SCRUBBED element, so two findings differing only by jitter
    # (duration_seconds / timing) still canonicalize to the same order + content.
    run1 = {"mocked_seam": {"findings": [
        {"symbol": "b", "lineno": 2, "duration_seconds": 0.9, "why": "in 0.34s"},
        {"symbol": "a", "lineno": 1, "duration_seconds": 0.1, "why": "in 0.71s"},
    ]}}
    run2 = {"mocked_seam": {"findings": [
        {"symbol": "a", "lineno": 1, "duration_seconds": 0.4, "why": "in 0.12s"},
        {"symbol": "b", "lineno": 2, "duration_seconds": 0.5, "why": "in 0.88s"},
    ]}}
    s1 = scrub_nondeterministic_bundle(run1)
    s2 = scrub_nondeterministic_bundle(run2)
    assert _hash(s1) == _hash(s2)


def test_non_findings_lists_keep_their_order():
    # Canonicalization is scoped to CANONICALIZE_LIST_KEYS: an ordered list under another key
    # (e.g. a sequence of gate steps) must NOT be re-sorted.
    b = {"gate_history": [{"step": "z"}, {"step": "a"}, {"step": "m"}]}
    s = scrub_nondeterministic_bundle(b)
    assert [d["step"] for d in s["gate_history"]] == ["z", "a", "m"]


def test_findings_list_of_scalars_untouched():
    # A findings list that is NOT all-dicts (order may matter / not comparable) is left as-is.
    b = {"findings": ["c", "a", "b"]}
    s = scrub_nondeterministic_bundle(b)
    assert s["findings"] == ["c", "a", "b"]
