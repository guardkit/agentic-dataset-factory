"""Hermetic wiring tests for the ``seeded_record`` family through ``qav.generate`` end-to-end.

Drives ``run_generation`` against STUB teacher/coach + a record-reflecting regenerator (no guardkit,
no network, no GPU). Proves: the record override reaches the worktree and DRIVES the regenerated
bundle (the seam), record rows bank as ``generation_mode="seeded_code"`` with an ``R-RECORD-*``
``injection_recipe`` + the fixed label, the divergence guard is armed for record rejects, approve
controls bank on the same surface, and an absent anchor / missing record is a LOUD count (never a
silent no-op). Fidelity of the REAL bundle evidence pattern is the micro-spike's job (real bridge).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from qav.contracts import extract_bundle, extract_label, validate_row
from qav.generate import (
    CoachVerdict,
    GenerateConfig,
    SourceTask,
    load_task_work_record,
    run_generation,
)


# --------------------------------------------------------------------------------------
# Stubs.
# --------------------------------------------------------------------------------------
class StubTeacher:
    def complete(self, system: str, user: str) -> str:
        return (
            "<think>\nReading gathering_status and the plan_audit / honesty fields named in the "
            "bundle: the evidence does not support the claim. Per-task green is not feature green.\n"
            "</think>"
        )


class StubCoach:
    def __init__(self, decision: str = "accept"):
        self.decision = decision

    def assess(self, bundle, think, label) -> CoachVerdict:
        return CoachVerdict(decision=self.decision, reasons=["stub"])


class RecordEchoRegenerator:
    """Reflects the materialized ``task_work_results.json`` INTO the bundle: ``plan_audit`` is
    passed through verbatim (as guardkit does), ``gathering_status`` is derived from it, and a hash
    of the whole record rides in ``profile_name`` so ANY record mutation yields a divergent bundle.
    This proves the ``record_override`` flowed record -> worktree -> gather -> bundle without any
    guardkit dependency."""

    def regenerate(self, worktree: Path) -> dict:
        matches = sorted(Path(worktree).glob(".guardkit/autobuild/*/task_work_results.json"))
        record = json.loads(matches[0].read_text()) if matches else {}
        sig = hashlib.sha1(json.dumps(record, sort_keys=True).encode()).hexdigest()[:12]
        pa = record.get("plan_audit")
        status = (
            "partial_gate_abort"
            if isinstance(pa, dict) and pa.get("status") == "violation"
            else "complete"
        )
        return {
            "honesty": {"discrepancies": [], "verified": True},
            "gathering_status": status,
            "plan_audit": pa,
            "quality_gates": record.get("quality_gates") or {"all_passed": True},
            "profile_name": "rec-" + sig,
        }


def _record_fixture():
    return {
        "task_id": "TASK-REC-777",
        "task_type": "feature",
        "plan_audit": {
            "status": "skipped", "severity": None, "violations": 0,
            "missing_files": [], "extra_modifications": [], "loc_variance_pct": None,
            "discrepancies_count": 0, "message": "no implementation plan on disk",
        },
        "quality_gates": {
            "all_passed": True, "coverage": 90.0, "coverage_met": True,
            "tests_failed": 0, "tests_passed": 20, "tests_passing": 20,
        },
        "completion_promises": [
            {"criterion_id": "AC-1", "status": "complete",
             "implementation_files": ["src/svc/retrieval.py"], "test_file": "tests/test_r.py"},
        ],
        "files_created": ["src/svc/retrieval.py", "src/svc/models.py"],
        "files_modified": ["src/svc/app.py"],
        "tests_written": ["tests/test_r.py"],
    }


def _write_record(tmp_path, task="TASK-REC-777") -> str:
    d = tmp_path / "record-store" / "myrepo" / task
    d.mkdir(parents=True)
    (d / "task_work_results.json").write_text(json.dumps(_record_fixture()), encoding="utf-8")
    return str(d)


def _src(tmp_path, task="TASK-REC-777"):
    return SourceTask(
        repo="myrepo", feature="FEAT-REC", task=task, sha="deadbeef",
        files={"src/svc/app.py": "def app():\n    return 1\n"},
        record_dir=_write_record(tmp_path, task),
    )


def _cfg(tmp_path, **over):
    base = dict(
        mode="seeded_defect", holdout_fraction=0.0,
        output_dir=str(tmp_path / "out"),
        manifest_path=str(tmp_path / "manifests" / "train.manifest.json"),
        scratch_dir=str(tmp_path / "scratch"), seed="qav-rec-test",
    )
    base.update(over)
    return GenerateConfig(**base)


def _run(cfg, sources, **kw):
    return run_generation(
        cfg, teacher=StubTeacher(), coach=StubCoach(), regenerator=RecordEchoRegenerator(),
        source_tasks=sources, created="2026-07-23", factory_sha="test",
        emit_gold_negatives=False, **kw,
    )


def _rows(tmp_path, split="train"):
    p = tmp_path / "out" / f"{split}.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


# --------------------------------------------------------------------------------------
# The seam: the record override drives the regenerated bundle.
# --------------------------------------------------------------------------------------
def test_load_task_work_record_reads_the_record(tmp_path):
    rd = _write_record(tmp_path)
    rec = load_task_work_record(rd)
    assert rec is not None and rec["task_id"] == "TASK-REC-777"
    assert load_task_work_record(tmp_path / "nope") is None


def test_record_reject_rows_bank_as_seeded_code_with_record_recipe(tmp_path):
    cfg = _cfg(tmp_path)
    summary = _run(cfg, [_src(tmp_path)])
    assert summary.seeded_record_written > 0
    assert summary.seeded_record_control_written > 0
    rows = _rows(tmp_path)
    record_rows = [r for r in rows if str(r["metadata"].get("injection_recipe", "")).startswith("R-RECORD-")]
    assert record_rows, "no seeded_record rows banked"
    for r in record_rows:
        validate_row(r)
        assert r["metadata"]["generation_mode"] == "seeded_code"  # frozen-schema threading
        label = extract_label(r)
        if label["verdict"] == "reject":
            assert r["metadata"]["dc_class"] in {"DC-12", "DC-14"}
            assert label["findings"][0]["class"] == r["metadata"]["dc_class"]
            assert label["ground_truth_source"] == "seeded"


def test_dc12_reject_bundle_carries_the_plan_audit_violation(tmp_path):
    # The seam proof: the mutated plan_audit flowed into the banked bundle (echo passthrough).
    cfg = _cfg(tmp_path, record_recipes={"R-RECORD-DC12-missingfiles": 1.0})
    _run(cfg, [_src(tmp_path)])
    rows = _rows(tmp_path)
    dc12 = [
        r for r in rows
        if r["metadata"].get("injection_recipe") == "R-RECORD-DC12-missingfiles"
        and extract_label(r)["verdict"] == "reject"
    ]
    assert dc12, "DC-12 record reject not banked"
    bundle = extract_bundle(dc12[0])
    assert bundle["plan_audit"]["status"] == "violation"
    assert bundle["gathering_status"] == "partial_gate_abort"


def test_dc12_control_clean_banks_a_passing_plan_audit_approve(tmp_path):
    cfg = _cfg(tmp_path, record_recipes={"R-RECORD-DC12-control-clean": 1.0})
    _run(cfg, [_src(tmp_path)])
    rows = _rows(tmp_path)
    ctrl = [r for r in rows if r["metadata"].get("injection_recipe") == "R-RECORD-DC12-control-clean"]
    assert ctrl
    assert extract_label(ctrl[0])["verdict"] == "approve"
    assert extract_bundle(ctrl[0])["plan_audit"]["status"] == "passed"


# --------------------------------------------------------------------------------------
# Loudness: absent anchor + missing record are counted, never silent.
# --------------------------------------------------------------------------------------
def test_anchor_absent_is_a_loud_skip(tmp_path):
    # A record already carrying a plan violation -> all DC-12 recipes anchor-skip loudly.
    d = tmp_path / "record-store" / "myrepo" / "TASK-VIO"
    d.mkdir(parents=True)
    rec = _record_fixture()
    rec["plan_audit"] = {"status": "violation", "severity": "high", "violations": 3}
    rec["task_id"] = "TASK-VIO"
    (d / "task_work_results.json").write_text(json.dumps(rec), encoding="utf-8")
    src = SourceTask(
        repo="myrepo", feature="FEAT-REC", task="TASK-VIO", sha="x",
        files={"src/svc/app.py": "def app():\n    return 1\n"}, record_dir=str(d),
    )
    cfg = _cfg(tmp_path, record_recipes={
        "R-RECORD-DC12-missingfiles": 1.0, "R-RECORD-DC12-control-clean": 1.0,
    })
    summary = _run(cfg, [src])
    assert summary.record_anchor_skipped >= 2  # both DC-12 recipes skipped, loud


def test_missing_record_is_a_loud_count_not_a_crash(tmp_path):
    src = SourceTask(
        repo="myrepo", feature="FEAT-REC", task="TASK-NOREC", sha="x",
        files={"src/svc/app.py": "def app():\n    return 1\n"},
        record_dir=str(tmp_path / "empty-record-dir"),  # exists in config but no json on disk
    )
    (tmp_path / "empty-record-dir").mkdir()
    cfg = _cfg(tmp_path)
    summary = _run(cfg, [src])
    assert summary.record_no_record == 1
    assert summary.seeded_record_written == 0


def test_no_record_dir_skips_the_family_cleanly(tmp_path):
    src = SourceTask(
        repo="myrepo", feature="FEAT-REC", task="TASK-NORD", sha="x",
        files={"src/svc/app.py": "def app():\n    return 1\n"},  # record_dir=None
    )
    cfg = _cfg(tmp_path)
    summary = _run(cfg, [src])
    assert summary.seeded_record_written == 0
    assert summary.record_no_record == 0  # no record_dir at all => cleanly inert, not an error


def test_dc05_off_by_default(tmp_path):
    cfg = _cfg(tmp_path)  # default record_recipes weights: DC-05 = 0.0
    _run(cfg, [_src(tmp_path)])
    rows = _rows(tmp_path)
    assert not any(r["metadata"].get("injection_recipe") == "R-RECORD-DC05-skipmask" for r in rows)


# --------------------------------------------------------------------------------------
# Split coherence: record rows never straddle their task's split (family -> seeded_code).
# --------------------------------------------------------------------------------------
def test_record_rows_share_the_task_split_no_straddle(tmp_path):
    cfg = _cfg(tmp_path, holdout_fraction=0.5)
    _run(cfg, [_src(tmp_path)])
    train = {r["metadata"]["provenance"]["task"] for r in _rows(tmp_path, "train")
             if str(r["metadata"].get("injection_recipe", "")).startswith("R-RECORD-")}
    ev = {r["metadata"]["provenance"]["task"] for r in _rows(tmp_path, "eval_qav")
          if str(r["metadata"].get("injection_recipe", "")).startswith("R-RECORD-")}
    assert not (train & ev)  # one task's record rows never on both sides
