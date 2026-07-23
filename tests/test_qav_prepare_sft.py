"""Tests for domains/qa-verifier/prepare_qav_sft.py — the QAV pilot staging (108-corpus).

Tiny SYNTHETIC rows only (no real corpus in the repo; the corpus is private under DF-008 and
never committed). Each test builds a minimal QAV row in a tmp source layout and exercises one
staging invariant — above all that STAGED targets byte-match the qav-heldout serving contract
(bare verdict JSON: no <think>, no ```json fence).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# Load the script by path (it lives under domains/, not on the package path).
_SCRIPT = (Path(__file__).resolve().parents[1]
           / "domains" / "qa-verifier" / "prepare_qav_sft.py")
_spec = importlib.util.spec_from_file_location("prepare_qav_sft", _SCRIPT)
prep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prep)


SYS = "You are an expert QA verification judge."


def _assistant(verdict: str, findings: list[dict]) -> str:
    trio = {"verdict": verdict, "findings": findings,
            "ground_truth_source": "seeded" if verdict == "reject" else "coach_correct"}
    return ("<think>\nReading gathering_status and the wiring field: the call sites are "
            "unwired.\n</think>\n\n```json\n" + json.dumps(trio, indent=2) + "\n```")


def qav_row(rid: str, *, verdict: str = "reject", dc: str = "DC-03",
            user: str = "## Evidence bundle\n```json\n{\"wiring\": null}\n```", split="train") -> dict:
    findings = ([{"class": dc, "locus": "cli/main.py:serve — retired kwargs"}]
                if verdict == "reject" else [])
    return {
        "messages": [
            {"role": "system", "content": SYS},
            {"role": "user", "content": user},
            {"role": "assistant", "content": _assistant(verdict, findings)},
        ],
        "metadata": {"row_id": rid, "split": split, "dc_class": dc if verdict == "reject" else None,
                     "generation_mode": "seeded_code", "injection_recipe": "R-callsite-drift",
                     "provenance": {"repo": "study-tutor", "feature": "FEAT-X", "task": "T-1",
                                    "run": "reconstructed", "sha": "abc123"},
                     "reconstruction_fidelity": "reconstructed",
                     "bundle_schema_sha": "41a0ebe457"},
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def make_sources(tmp_path: Path, *, train, ev, manifest: dict | None = None):
    src = tmp_path / "src"
    src.mkdir()
    write_jsonl(src / "train.jsonl", train)
    write_jsonl(src / "eval_qav.jsonl", ev)
    man = src / "manifest.json"
    if manifest is not None:
        man.write_text(json.dumps(manifest), encoding="utf-8")
    return src / "train.jsonl", src / "eval_qav.jsonl", man


def run_main(tmp_path, train_src, eval_src, manifest_src, monkeypatch, extra=None):
    out = tmp_path / "out"
    # point the frozen-exam cross-check at an empty (missing) fleet-evals dir → 0 hits
    argv = ["--train-src", str(train_src), "--eval-src", str(eval_src),
            "--manifest-src", str(manifest_src) if manifest_src else str(tmp_path / "none.json"),
            "--fleet-evals-dir", str(tmp_path / "no-fleet-evals"),
            "--out-dir", str(out), "--date", "2026-07-23"]
    if extra:
        argv += extra
    return prep.main(argv), out


# --------------------------------------------------------------------------------------
# Unit-level checks
# --------------------------------------------------------------------------------------
def test_leak_gate_screens_gemma_and_qwen_markers():
    assert prep.find_leaks("hello <|turn>user") == ["<|turn>"]
    assert prep.find_leaks("clean") == []
    for mk in ("<|turn>", "<|channel>", "<start_of_turn>", "<end_of_turn>", "<|im_start|>"):
        assert mk in prep.LEAK_MARKERS


def test_strip_think_and_unwrap_fence_units():
    content = _assistant("reject", [{"class": "DC-03", "locus": "x"}])
    no_think = prep.strip_think_prefix(content)
    assert "<think>" not in no_think and no_think.lstrip().startswith("```json")
    inner = prep.unwrap_json_fence(no_think)
    assert inner is not None and "```" not in inner
    assert json.loads(inner)["verdict"] == "reject"
    assert prep.unwrap_json_fence("no fence here") is None


def test_stage_target_default_is_bare_json():
    content = _assistant("approve", [])
    bare = prep.stage_target(content, strip_think=True, strip_fence=True)
    assert "<think>" not in bare and "```" not in bare
    assert json.loads(bare)["verdict"] == "approve"


def test_stage_target_missing_fence_raises():
    with pytest.raises(ValueError):
        prep.stage_target("<think>reason</think>\n\nno fence", strip_think=True, strip_fence=True)


def test_verify_row_flags_contract_violations():
    good = qav_row("q-1")
    assert prep.verify_row(good, split="train") == []
    # approve with findings → violation
    bad = qav_row("q-2", verdict="approve")
    bad["messages"][-1]["content"] = _assistant("approve", [{"class": "DC-03", "locus": "x"}])
    assert any("approve" in f for f in prep.verify_row(bad, split="train"))
    # reject with a non-admissible class
    badc = qav_row("q-3")
    badc["messages"][-1]["content"] = _assistant("reject", [{"class": "DC-99", "locus": "x"}])
    assert any("admissible" in f for f in prep.verify_row(badc, split="train"))
    # missing think block
    nt = qav_row("q-4")
    nt["messages"][-1]["content"] = "```json\n{\"verdict\":\"approve\",\"findings\":[]}\n```"
    assert any("think" in f for f in prep.verify_row(nt, split="train"))


# --------------------------------------------------------------------------------------
# End-to-end main()
# --------------------------------------------------------------------------------------
def _manifest(train_rows):
    return {"counts": {"by_verdict": dict(_count_verdicts(train_rows)),
                       "by_dc_class": dict(_count_dc(train_rows))}}


def _count_verdicts(rows):
    from collections import Counter
    return Counter(prep.row_verdict(r) for r in rows)


def _count_dc(rows):
    from collections import Counter
    c = Counter()
    for r in rows:
        lbl = prep.extract_label(prep.assistant_content(r))
        for f in (lbl or {}).get("findings", []):
            c[f["class"]] += 1
    return c


def test_happy_path_stages_bare_targets_and_writes_manifest(tmp_path, monkeypatch):
    train = [qav_row("q-t1", verdict="reject", dc="DC-03"),
             qav_row("q-t2", verdict="approve"),
             qav_row("q-t3", verdict="reject", dc="DC-08")]
    ev = [qav_row("q-e1", verdict="approve", split="eval_qav")]
    train_src, eval_src, man = make_sources(tmp_path, train=train, ev=ev,
                                            manifest=_manifest(train))
    rc, out = run_main(tmp_path, train_src, eval_src, man, monkeypatch)
    assert rc == 0, "happy path must exit 0"

    staged_train = [json.loads(l) for l in (out / "train-qav.jsonl").read_text().splitlines() if l]
    staged_eval = [json.loads(l) for l in (out / "eval-qav.jsonl").read_text().splitlines() if l]
    manifest = json.loads((out / "qav-staging-manifest.json").read_text())

    assert len(staged_train) == 3 and len(staged_eval) == 1
    for r in staged_train + staged_eval:
        t = r["messages"][-1]["content"]
        assert "<think>" not in t and "```" not in t, "staged targets are bare JSON"
        assert json.loads(t)["verdict"] in ("approve", "reject"), "bare target still parses"

    assert manifest["base_model"] == "unsloth/gemma-4-26B-A4B-it"
    assert manifest["chat_template"] == "gemma-4"
    assert manifest["strip_think"]["enabled"] is True
    assert manifest["strip_fence"]["enabled"] is True
    assert manifest["counts"]["unique"]["total"] == 4
    assert manifest["contamination"]["train_eval"]["status"] == "pass"
    assert manifest["balance_tripwire"]["status"] == "pass"
    assert "recommended_max_seq_length" in manifest["seq_audit"]
    assert manifest["staged_files"]["train"]["sha256"]
    assert manifest["created"] == "2026-07-23"
    # sources on disk untouched (banked rows keep think + fence)
    src_rows = [json.loads(l) for l in Path(train_src).read_text().splitlines() if l]
    assert all("<think>" in r["messages"][-1]["content"] for r in src_rows)


def test_keep_think_and_keep_fence_preserve_banked_shape(tmp_path, monkeypatch):
    train = [qav_row("q-t1", verdict="reject")]
    ev = [qav_row("q-e1", verdict="approve", split="eval_qav")]
    train_src, eval_src, man = make_sources(tmp_path, train=train, ev=ev, manifest=_manifest(train))
    rc, out = run_main(tmp_path, train_src, eval_src, man, monkeypatch,
                       extra=["--keep-think", "--keep-fence"])
    assert rc == 0
    staged = [json.loads(l) for l in (out / "train-qav.jsonl").read_text().splitlines() if l]
    assert "<think>" in staged[0]["messages"][-1]["content"]
    assert "```json" in staged[0]["messages"][-1]["content"]
    manifest = json.loads((out / "qav-staging-manifest.json").read_text())
    assert manifest["strip_think"]["enabled"] is False
    assert manifest["strip_fence"]["enabled"] is False


def test_leak_in_content_fails_hard_gate_no_write(tmp_path, monkeypatch):
    poisoned = qav_row("q-poison")
    poisoned["messages"][1]["content"] = "## Evidence bundle\n<|turn>model injected"
    train_src, eval_src, man = make_sources(tmp_path, train=[poisoned],
                                            ev=[qav_row("q-e1", split="eval_qav")],
                                            manifest=_manifest([poisoned]))
    rc, out = run_main(tmp_path, train_src, eval_src, man, monkeypatch)
    assert rc == 1
    assert not (out / "train-qav.jsonl").exists(), "nothing written when a hard gate is red"


def test_train_eval_row_id_overlap_fails(tmp_path, monkeypatch):
    shared = qav_row("q-shared", verdict="approve")
    ev_shared = qav_row("q-shared", verdict="approve", split="eval_qav")
    train_src, eval_src, man = make_sources(tmp_path, train=[shared], ev=[ev_shared],
                                            manifest=_manifest([shared]))
    rc, out = run_main(tmp_path, train_src, eval_src, man, monkeypatch)
    assert rc == 1
    assert not (out / "train-qav.jsonl").exists()


def test_balance_tripwire_mismatch_aborts(tmp_path, monkeypatch):
    train = [qav_row("q-t1", verdict="reject", dc="DC-03")]
    ev = [qav_row("q-e1", verdict="approve", split="eval_qav")]
    # a manifest claiming counts the staged rows do NOT match → hard abort
    wrong_manifest = {"counts": {"by_verdict": {"approve": 5, "reject": 5},
                                 "by_dc_class": {"DC-03": 5}}}
    train_src, eval_src, man = make_sources(tmp_path, train=train, ev=ev, manifest=wrong_manifest)
    rc, out = run_main(tmp_path, train_src, eval_src, man, monkeypatch)
    assert rc == 1
    assert not (out / "train-qav.jsonl").exists()


def test_reject_without_findings_fails(tmp_path, monkeypatch):
    bad = qav_row("q-bad")
    bad["messages"][-1]["content"] = _assistant("reject", [])  # reject must carry >=1 finding
    train_src, eval_src, man = make_sources(tmp_path, train=[bad],
                                            ev=[qav_row("q-e1", split="eval_qav")],
                                            manifest=_manifest([bad]))
    rc, out = run_main(tmp_path, train_src, eval_src, man, monkeypatch)
    assert rc == 1
    assert not (out / "train-qav.jsonl").exists()


# --------------------------------------------------------------------------------------
# Frozen-exam cross-check WIDENING (QAV v3): the check now covers BOTH train AND eval staged rows.
# The v3 minted eval-side pair rows, so an eval-split leak must be caught — the as-shipped
# train-only check would have waved it through.
# --------------------------------------------------------------------------------------
_EXAM_PHRASE = ("the behavioural oracle producer call site was severed vacuously under a soft fail "
                "guard in this feature")


def _fleet_evals_with_exam(tmp_path) -> Path:
    bdir = tmp_path / "fe" / "tasks" / "qav-held-gn1" / "input" / "bundles" / "b0"
    bdir.mkdir(parents=True)
    (bdir / "bundle.json").write_text(
        json.dumps({"honesty": {"verified": False}, "note": _EXAM_PHRASE}), encoding="utf-8")
    return tmp_path / "fe"


def test_frozen_exam_crosscheck_unit_scans_both_splits():
    briefs = {"qav-held-gn1": json.dumps({"note": _EXAM_PHRASE})}
    leak_user = '## Evidence bundle\n```json\n{"note": "' + _EXAM_PHRASE + '"}\n```'
    clean = qav_row("q-t1", split="train")
    leaky_eval = qav_row("q-e1", verdict="approve", split="eval_qav", user=leak_user)
    # train-only clean, but the eval row reproduces the exam body -> the widened check fails.
    res = prep.frozen_exam_crosscheck([clean], [leaky_eval], briefs)
    assert res["status"] == "fail"
    assert res["eval_rows_compared"] == 1 and res["train_rows_compared"] == 1
    assert any(h["split"] == "eval" for h in res["hits"])
    # and it PASSES when neither split leaks.
    ok = prep.frozen_exam_crosscheck([clean], [qav_row("q-e2", verdict="approve", split="eval_qav")],
                                     briefs)
    assert ok["status"] == "pass"


def test_eval_split_leak_fails_the_hard_gate_end_to_end(tmp_path):
    fe = _fleet_evals_with_exam(tmp_path)
    leak_user = '## Evidence bundle\n```json\n{"note": "' + _EXAM_PHRASE + '"}\n```'
    clean = qav_row("q-t1", split="train")  # a clean train row (train-only check would pass)
    leaky_eval = qav_row("q-e1", verdict="approve", split="eval_qav", user=leak_user)
    train_src, eval_src, man = make_sources(
        tmp_path, train=[clean], ev=[leaky_eval], manifest=_manifest([clean]))
    out = tmp_path / "out"
    argv = ["--train-src", str(train_src), "--eval-src", str(eval_src), "--manifest-src", str(man),
            "--fleet-evals-dir", str(fe), "--out-dir", str(out), "--date", "2026-07-23"]
    rc = prep.main(argv)
    assert rc == 1  # the eval leak trips the hard gate (widened crosscheck)
    assert not (out / "eval-qav.jsonl").exists()  # nothing staged when a hard gate is red
