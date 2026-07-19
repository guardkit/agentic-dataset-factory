"""Tests for domains/dcl-capability-language/prepare_dcl_sft.py — the DCL pilot staging.

Tiny SYNTHETIC rows only (no real corpus in the repo; the corpus is private under DF-008 and
never committed). Each test builds a minimal author/repair row in a tmp source layout and
exercises one staging invariant.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# Load the script by path (it lives under domains/, not on the package path).
_SCRIPT = (Path(__file__).resolve().parents[1]
           / "domains" / "dcl-capability-language" / "prepare_dcl_sft.py")
_spec = importlib.util.spec_from_file_location("prepare_dcl_sft", _SCRIPT)
prep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prep)


# --------------------------------------------------------------------------------------
# Row builders
# --------------------------------------------------------------------------------------
SYS = "You are a DCL author."
VOCAB = "## DCL vocabulary reference\nactor person is human\n"
CLEAN_DCL = "```dcl\nlanguage dcl 1.0\n\nactor Person is human\n```"


def author_row(rid: str, brief: str = "Model a widgets capability.") -> dict:
    return {
        "messages": [
            {"role": "system", "content": SYS},
            {"role": "user", "content": f"## Feature brief\n{brief}\n{VOCAB}"},
            {"role": "assistant", "content": CLEAN_DCL},
        ],
        "metadata": {"row_id": rid, "domain": "dcl-capability-language", "layer": "behaviour",
                     "type": "direct", "mode": "dcl_author", "split": "train",
                     "recipe_id": None,
                     "provenance": {"source": "synthetic-brief", "vocab_pin": "4f9fbe56",
                                    "compiler_pin": "4f9fbe56"},
                     "compile_verified": True},
    }


def repair_row(rid: str, *, post_think: bool = True) -> dict:
    # The broken capability is quoted INSIDE the think block; the corrected fence sits AFTER
    # </think> (the post-think law). When post_think=False the ONLY fence is inside <think>.
    think = ("<think>\nThe compiler rejects `machine`; person is the kind.\n"
             "```dcl\nactor Client is machine\n```\n</think>")
    answer = "\n" + CLEAN_DCL if post_think else ""
    return {
        "messages": [
            {"role": "system", "content": SYS},
            {"role": "user", "content": "## Broken DCL capability\n```dcl\nactor Client is machine\n```"},
            {"role": "assistant", "content": think + answer},
        ],
        "metadata": {"row_id": rid, "domain": "dcl-capability-language", "layer": "behaviour",
                     "type": "reasoning", "mode": "dcl_repair", "split": "train",
                     "recipe_id": "R-actor-kind",
                     "provenance": {"source": "derived", "vocab_pin": "4f9fbe56",
                                    "compiler_pin": "4f9fbe56"},
                     "compile_verified": True},
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def make_sources(tmp_path: Path, *, authors_train, authors_eval, repairs_train, repairs_eval):
    """Build a minimal authors/repairs source layout (+ manifest.json stubs) and return dirs."""
    adir = tmp_path / "authors"
    rdir = tmp_path / "repairs"
    adir.mkdir()
    rdir.mkdir()
    write_jsonl(adir / "train.jsonl", authors_train)
    write_jsonl(adir / "eval_dcl.jsonl", authors_eval)
    write_jsonl(rdir / "train.jsonl", repairs_train)
    write_jsonl(rdir / "eval_dcl.jsonl", repairs_eval)
    (adir / "manifest.json").write_text("{}", encoding="utf-8")
    (rdir / "manifest.json").write_text("{}", encoding="utf-8")
    return adir, rdir


# --------------------------------------------------------------------------------------
# Unit-level checks (helpers)
# --------------------------------------------------------------------------------------
def test_leak_gate_catches_planted_control_token():
    assert prep.find_leaks("hello <|im_start|>user") == ["<|im_start|>"]
    assert prep.find_leaks("clean text") == []
    # every documented marker is screened
    for mk in ("<|im_start|>", "<|im_end|>", "<|turn>", "<|channel>",
               "<start_of_turn>", "<end_of_turn>"):
        assert mk in prep.LEAK_MARKERS


def test_post_think_fence_catches_in_think_only_repair():
    good = repair_row("dcl-good", post_think=True)
    bad = repair_row("dcl-bad", post_think=False)
    assert prep.has_post_think_dcl_fence(prep.assistant_content(good), is_repair=True) is True
    # bad: its ONLY ```dcl fence is inside <think> -> must fail the post-think gate
    assert prep.has_post_think_dcl_fence(prep.assistant_content(bad), is_repair=True) is False
    # author rows: fence anywhere in the (think-free) answer is fine
    assert prep.has_post_think_dcl_fence(CLEAN_DCL, is_repair=False) is True


def test_verify_row_flags_unverified_and_bad_roles():
    r = author_row("dcl-x")
    assert prep.verify_row(r, source="train", split="train") == []
    r["metadata"]["compile_verified"] = False
    fails = prep.verify_row(r, source="train", split="train")
    assert any("compile_verified" in f for f in fails)
    # two-message row -> role-shape failure
    bad = author_row("dcl-y")
    bad["messages"] = bad["messages"][:2]
    assert any("roles" in f for f in prep.verify_row(bad, source="train", split="train"))


# --------------------------------------------------------------------------------------
# End-to-end main() behaviour
# --------------------------------------------------------------------------------------
def run_main(tmp_path, adir, rdir, monkeypatch, extra=None):
    out = tmp_path / "out"
    argv = ["--authors-dir", str(adir), "--repairs-dir", str(rdir),
            "--out-dir", str(out), "--date", "2026-07-19"]
    if extra:
        argv += extra
    rc = prep.main(argv)
    return rc, out


def test_full_stage_happy_path_filters_retired_and_oversamples(tmp_path, monkeypatch):
    # 2 authors + 3 repairs kept; corpus468 train also carries 1 RETIRED author (dropped).
    # Adjust EXPECTED to this tiny fixture so the count-assert passes.
    monkeypatch.setattr(prep, "EXPECTED",
                        {"authors_train": 2, "authors_eval": 1,
                         "repairs_train": 3, "repairs_eval": 1})
    authors_train = [author_row("dcl-a1"), author_row("dcl-a2", brief="Model orders.")]
    authors_eval = [author_row("dcl-ae1", brief="Model refunds.")]
    retired = author_row("dcl-retired")  # mode==dcl_author inside the repairs set -> dropped
    repairs_train = [repair_row("dcl-r1"), repair_row("dcl-r2"), repair_row("dcl-r3"), retired]
    repairs_eval = [repair_row("dcl-re1"), author_row("dcl-retired-e")]  # 1 repair + 1 retired
    adir, rdir = make_sources(tmp_path, authors_train=authors_train, authors_eval=authors_eval,
                              repairs_train=repairs_train, repairs_eval=repairs_eval)

    rc, out = run_main(tmp_path, adir, rdir, monkeypatch, extra=["--author-reps", "2"])
    assert rc == 0, "happy path must exit 0"

    train = [json.loads(l) for l in (out / "train-dcl.jsonl").read_text().splitlines() if l]
    ev = [json.loads(l) for l in (out / "eval-dcl.jsonl").read_text().splitlines() if l]
    manifest = json.loads((out / "dcl-staging-manifest.json").read_text())

    # retired author rows dropped from the repairs set (train + eval)
    modes = [r["metadata"]["mode"] for r in train]
    assert modes.count("dcl_author") == 2 * 2, "2 authors x K=2 reps"
    assert modes.count("dcl_repair") == 3, "3 repairs, never oversampled"
    assert "dcl-retired" not in {r["metadata"]["row_id"] for r in train}
    # eval never oversampled and retired-author dropped
    assert len(ev) == 2  # 1 author eval + 1 repair eval (retired-e dropped)
    assert all(r["metadata"]["mode"] in ("dcl_author", "dcl_repair") for r in ev)
    assert "dcl-retired-e" not in {r["metadata"]["row_id"] for r in ev}

    # manifest fields present
    assert manifest["author_reps"] == 2
    assert manifest["base_model"] == "Qwen/Qwen3-4B-Instruct-2507"
    assert manifest["counts"]["unique"]["train"] == 5  # 2 authors + 3 repairs (retired dropped)
    assert manifest["counts"]["staged"]["train_rows_written"] == len(train)
    assert manifest["staged_files"]["train"]["sha256"]
    assert manifest["staged_files"]["eval"]["sha256"]
    assert manifest["contamination"]["train_eval"]["status"] == "pass"
    assert manifest["contamination"]["frozen_exam_crosscheck"]["status"] == "pass"
    assert "recommended_max_seq_length" in manifest["seq_audit"]
    assert manifest["created"] == "2026-07-19"


def test_author_reps_1_no_oversampling(tmp_path, monkeypatch):
    monkeypatch.setattr(prep, "EXPECTED",
                        {"authors_train": 2, "authors_eval": 1,
                         "repairs_train": 2, "repairs_eval": 1})
    adir, rdir = make_sources(
        tmp_path,
        authors_train=[author_row("dcl-a1"), author_row("dcl-a2", brief="b2")],
        authors_eval=[author_row("dcl-ae1", brief="be")],
        repairs_train=[repair_row("dcl-r1"), repair_row("dcl-r2")],
        repairs_eval=[repair_row("dcl-re1")])
    rc, out = run_main(tmp_path, adir, rdir, monkeypatch, extra=["--author-reps", "1"])
    assert rc == 0
    train = [json.loads(l) for l in (out / "train-dcl.jsonl").read_text().splitlines() if l]
    modes = [r["metadata"]["mode"] for r in train]
    assert modes.count("dcl_author") == 2  # K=1 -> no repeats
    assert modes.count("dcl_repair") == 2


def test_count_mismatch_aborts(tmp_path, monkeypatch):
    # Default EXPECTED (77/10/374/46) will not match a tiny fixture -> SystemExit.
    adir, rdir = make_sources(
        tmp_path,
        authors_train=[author_row("dcl-a1")], authors_eval=[author_row("dcl-ae1")],
        repairs_train=[repair_row("dcl-r1")], repairs_eval=[repair_row("dcl-re1")])
    with pytest.raises(SystemExit) as ei:
        run_main(tmp_path, adir, rdir, monkeypatch)
    assert "count mismatch" in str(ei.value)


def test_leak_in_content_fails_hard_gate_no_write(tmp_path, monkeypatch):
    monkeypatch.setattr(prep, "EXPECTED",
                        {"authors_train": 1, "authors_eval": 1,
                         "repairs_train": 1, "repairs_eval": 1})
    poisoned = author_row("dcl-poison")
    poisoned["messages"][2]["content"] = "```dcl\nactor <|im_start|>Person is human\n```"
    adir, rdir = make_sources(
        tmp_path, authors_train=[poisoned], authors_eval=[author_row("dcl-ae1")],
        repairs_train=[repair_row("dcl-r1")], repairs_eval=[repair_row("dcl-re1")])
    rc, out = run_main(tmp_path, adir, rdir, monkeypatch)
    assert rc == 1, "a planted control token must fail the hard gate"
    assert not (out / "train-dcl.jsonl").exists(), "nothing written when a hard gate is red"


def test_in_think_only_repair_fails_verification(tmp_path, monkeypatch):
    monkeypatch.setattr(prep, "EXPECTED",
                        {"authors_train": 1, "authors_eval": 1,
                         "repairs_train": 1, "repairs_eval": 1})
    bad_repair = repair_row("dcl-inthink", post_think=False)
    adir, rdir = make_sources(
        tmp_path, authors_train=[author_row("dcl-a1")], authors_eval=[author_row("dcl-ae1")],
        repairs_train=[bad_repair], repairs_eval=[repair_row("dcl-re1")])
    rc, out = run_main(tmp_path, adir, rdir, monkeypatch)
    assert rc == 1, "a repair row whose only ```dcl fence is inside <think> must fail"
    assert not (out / "train-dcl.jsonl").exists()


def test_duplicate_row_id_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(prep, "EXPECTED",
                        {"authors_train": 2, "authors_eval": 1,
                         "repairs_train": 1, "repairs_eval": 1})
    # two DISTINCT train rows share a row_id -> uniqueness gate fails
    adir, rdir = make_sources(
        tmp_path,
        authors_train=[author_row("dcl-dup", brief="one"), author_row("dcl-dup", brief="two")],
        authors_eval=[author_row("dcl-ae1")],
        repairs_train=[repair_row("dcl-r1")], repairs_eval=[repair_row("dcl-re1")])
    rc, out = run_main(tmp_path, adir, rdir, monkeypatch)
    assert rc == 1
    assert not (out / "train-dcl.jsonl").exists()
