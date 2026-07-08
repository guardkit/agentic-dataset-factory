"""Contamination-check tests — the gate must REFUSE a poisoned manifest (PLAN §6)."""

from __future__ import annotations

import json

from qav.contamination import check_contamination
from qav.contracts import build_row
from qav.gold_negatives import GN3, build_gold_negative_row

GREEN = {"honesty": {"discrepancies": []}, "gathering_status": "complete", "tests": {"passed": True}}


def _b(uniq):
    # distinct bundle per row -> distinct content-addressed row_id (real seeded rows differ)
    b = dict(GREEN)
    b["profile_name"] = uniq
    return b


def _seeded_reject(task, recipe, locus="cli/main.py", repo="guardkit"):
    return build_row(
        bundle=_b(f"{repo}-{task}-{recipe}"),
        think="Reading tests/honesty; production construction unwitnessed. Reject DC-03.",
        label={"verdict": "reject", "findings": [{"class": "DC-03", "locus": locus}],
               "ground_truth_source": "seeded"},
        provenance={"repo": repo, "feature": "FEAT-Y", "task": task, "run": "r", "sha": "s"},
        split="train",
        generation_mode="seeded_code",
        dc_class="DC-03",
        injection_recipe=recipe,
    )


def _approve(task, repo="guardkit", split="train"):
    return build_row(
        bundle=_b(f"{repo}-{task}-approve"),
        think="All green, honesty clean, no seam risk. Approve.",
        label={"verdict": "approve", "findings": [], "ground_truth_source": "coach_correct"},
        provenance={"repo": repo, "feature": "FEAT-Y", "task": task, "run": "r", "sha": "s"},
        split=split,
        generation_mode="harvest",
        dc_class=None,
    )


def test_clean_split_passes():
    train = [_seeded_reject("TASK-A", "R-DC03-callsite"), _approve("TASK-B")]
    eval_rows = [_seeded_reject("TASK-C", "R-DC03-producer")]
    eval_rows[0]["metadata"]["split"] = "eval_qav"
    result = check_contamination(train, eval_rows)
    assert result.passed
    assert result.to_dict()["status"] == "pass"


def test_row_id_intersection_fails():
    shared = _seeded_reject("TASK-A", "R-DC03-callsite")
    result = check_contamination([shared], [shared])
    assert not result.passed
    assert len(result.intersection) == 1


def test_sibling_variant_leakage_fails_even_with_different_hashes():
    # same source task + same DC-03 family, different sub-recipes -> straddles the split.
    train = [_seeded_reject("TASK-A", "R-DC03-callsite", locus="cli/main.py:serve")]
    eval_rows = [_seeded_reject("TASK-A", "R-DC03-producer", locus="evidence.py:gather")]
    assert train[0]["metadata"]["row_id"] != eval_rows[0]["metadata"]["row_id"]
    result = check_contamination(train, eval_rows)
    assert not result.passed
    assert result.sibling_violations
    assert result.sibling_violations[0]["family"] == "R-DC03"


def test_gold_negative_source_task_exclusion_fails():
    # a training row harvested from a gold-negative source task (guardkit/TASK-QAV-005).
    train = [_approve("TASK-QAV-005", repo="guardkit")]
    eval_rows = [build_gold_negative_row(GN3)]  # guardkit / TASK-QAV-005
    result = check_contamination(train, eval_rows)
    assert not result.passed
    assert result.gold_source_violations
    assert result.gold_source_violations[0]["task"] == "TASK-QAV-005"


def test_cli_exit_codes(tmp_path):
    import scripts.qav_contamination_check as cli  # noqa: WPS433

    def _write(name, rows):
        p = tmp_path / name
        p.write_text("\n".join(json.dumps(r) for r in rows))
        return str(p)

    train = _write("train.jsonl", [_seeded_reject("TASK-A", "R-DC03-callsite")])
    clean_eval = _write("eval.jsonl", [])
    assert cli.main(["--train", train, "--eval", clean_eval]) == 0

    shared = _seeded_reject("TASK-A", "R-DC03-callsite")
    poisoned_train = _write("ptrain.jsonl", [shared])
    poisoned_eval = _write("peval.jsonl", [shared])
    assert cli.main(["--train", poisoned_train, "--eval", poisoned_eval]) == 1
