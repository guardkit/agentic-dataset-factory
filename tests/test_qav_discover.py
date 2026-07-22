"""QAV source-task discovery + file-map scoping tests (seams (a) + (b), PLAN §2).

Hermetic: builds fixture ``.guardkit`` record trees in a real temp git repo (git subprocess only —
no model, no seat, no network). Proves the approved-sha honesty law (resolve from record evidence,
exclude with a logged reason otherwise, NEVER default to HEAD — including the FEAT-SMP-001-shaped
spec-only case) and the recipe-relevant file-map scoping (extension / size / binary / vendored-dir
guards + the read-only git-worktree checkout).
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import yaml

from qav.discover import (
    APPROVE_GROUND_TRUTH_SOURCE,
    APPROVED_SHA_KEYS,
    MAX_FILE_BYTES,
    RUN_RECORD_SENTINEL,
    checkout_scoped_file_map,
    consumable_source_task_refs,
    discover_source_task_refs,
    discover_source_tasks,
    locate_run_record_dir,
    materialize_run_record,
    resolve_approved_sha,
    resolve_tracker_approved_sha,
    scope_file_map,
)


# --------------------------------------------------------------------------------------
# git fixture helpers.
# --------------------------------------------------------------------------------------
def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
             "GIT_COMMITTER_EMAIL": "t@t", "HOME": str(repo), "PATH": _path()},
    )
    return proc.stdout.strip()


def _path() -> str:
    import os
    return os.environ.get("PATH", "/usr/bin:/bin")


def _init_repo(root: Path, files: dict[str, str]) -> str:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "seed")
    return _git(root, "rev-parse", "HEAD")


def _write_merge_summary(root: Path, feature: str, payload: dict) -> None:
    d = root / ".guardkit" / "archive" / feature
    d.mkdir(parents=True, exist_ok=True)
    (d / "merge_summary.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_feature_spec(root: Path, feature: str) -> None:
    d = root / ".guardkit" / "features"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{feature}.yaml").write_text(f"id: {feature}\nname: spec only\n", encoding="utf-8")


# --------------------------------------------------------------------------------------
# resolve_approved_sha — the honesty law's core.
# --------------------------------------------------------------------------------------
def test_resolve_approved_sha_from_merged_commit(tmp_path):
    repo = tmp_path / "repo"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n"})
    got, reason = resolve_approved_sha(repo, {"merged_commit": sha})
    assert got == sha
    assert "merged_commit" in reason


def test_resolve_approved_sha_key_priority(tmp_path):
    repo = tmp_path / "repo"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n"})
    # merged_commit wins over merge_commit / main_head_after when several are present + resolvable.
    got, reason = resolve_approved_sha(
        repo, {"main_head_after": sha, "merge_commit": sha, "merged_commit": sha}
    )
    assert got == sha and "merged_commit" in reason
    assert APPROVED_SHA_KEYS[0] == "merged_commit"


def test_resolve_approved_sha_excludes_when_no_key(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo, {"src/a.py": "x = 1\n"})
    got, reason = resolve_approved_sha(repo, {"base_commit": "abc", "branch_tip": "def"})
    assert got is None
    assert "no approved-sha key" in reason and "HEAD" in reason


def test_resolve_approved_sha_excludes_unresolvable_never_head(tmp_path):
    repo = tmp_path / "repo"
    head = _init_repo(repo, {"src/a.py": "x = 1\n"})
    got, reason = resolve_approved_sha(repo, {"merged_commit": "deadbeefdeadbeef"})
    assert got is None  # NEVER falls back to HEAD
    assert got != head
    assert "unresolvable" in reason and "HEAD" in reason


# --------------------------------------------------------------------------------------
# discover_source_task_refs — the walk + the exclusion law end to end.
# --------------------------------------------------------------------------------------
def test_discover_includes_approved_tasks_with_resolved_sha(tmp_path):
    repo = tmp_path / "guardkit"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n"})
    _write_merge_summary(repo, "FEAT-AAA", {
        "merged_commit": sha,
        "tasks": [{"id": "TASK-1", "decision": "approved"}, {"id": "TASK-2", "decision": "approved"}],
    })
    result = discover_source_task_refs({"guardkit": repo})
    included = {(r.task, r.sha) for r in result.included}
    assert included == {("TASK-1", sha), ("TASK-2", sha)}
    assert all(r.feature == "FEAT-AAA" for r in result.included)


def test_discover_excludes_feat_smp_001_spec_only_proving_the_law(tmp_path):
    # FEAT-SMP-001 shape: a feature spec with NO archive run record -> excluded (the law fires).
    repo = tmp_path / "study_tutor"
    _init_repo(repo, {"src/a.py": "x = 1\n"})
    _write_feature_spec(repo, "FEAT-SMP-001")
    result = discover_source_task_refs({"study_tutor": repo})
    assert result.included == []
    smp = [e for e in result.excluded if e.feature == "FEAT-SMP-001"]
    assert len(smp) == 1
    assert "spec-only" in smp[0].reason and "never defaulted to HEAD" in smp[0].reason


def test_discover_excludes_unresolvable_sha_tasks(tmp_path):
    repo = tmp_path / "guardkit"
    _init_repo(repo, {"src/a.py": "x = 1\n"})
    _write_merge_summary(repo, "FEAT-BBB", {
        "merge_commit": "0000000000",  # not a real commit in this repo
        "tasks": [{"id": "TASK-9", "decision": "approved"}],
    })
    result = discover_source_task_refs({"guardkit": repo})
    assert result.included == []
    bbb = [e for e in result.excluded if e.task == "TASK-9"]
    assert len(bbb) == 1 and "unresolvable" in bbb[0].reason


def test_discover_excludes_no_commit_key_record(tmp_path):
    # study-tutor FEAT-PO-002 real shape: a merge_summary with no approved-sha key.
    repo = tmp_path / "study_tutor"
    _init_repo(repo, {"src/a.py": "x = 1\n"})
    _write_merge_summary(repo, "FEAT-PO-002", {
        "feature_id": "FEAT-PO-002",
        "merge_strategy": "fast-forward",
        "tasks_merged": [{"id": "TASK-PO-1", "decision": "approved"}],
    })
    result = discover_source_task_refs({"study_tutor": repo})
    assert result.included == []
    assert any("no approved-sha key" in e.reason for e in result.excluded)


def test_discover_excludes_unapproved_task(tmp_path):
    repo = tmp_path / "guardkit"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n"})
    _write_merge_summary(repo, "FEAT-CCC", {
        "merged_commit": sha,
        "tasks": [{"id": "TASK-OK", "decision": "approved"}, {"id": "TASK-NO", "decision": "deferred"}],
    })
    result = discover_source_task_refs({"guardkit": repo})
    assert [r.task for r in result.included] == ["TASK-OK"]
    assert any(e.task == "TASK-NO" and "not approved" in e.reason for e in result.excluded)


def test_discover_excludes_gold_negative_source_task(tmp_path):
    # guardkit / TASK-QAV-005 is a gold-negative source (GN-3) — must never seed a training row.
    repo = tmp_path / "guardkit"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n"})
    _write_merge_summary(repo, "FEAT-10AC", {
        "merged_commit": sha,
        "tasks": [{"id": "TASK-QAV-005", "decision": "approved"}, {"id": "TASK-QAV-004", "decision": "approved"}],
    })
    result = discover_source_task_refs({"guardkit": repo})
    assert [r.task for r in result.included] == ["TASK-QAV-004"]
    assert any(e.task == "TASK-QAV-005" and "gold-negative" in e.reason for e in result.excluded)


def test_discover_gold_source_repo_name_normalised(tmp_path):
    # study-tutor / TASK-SMP2-07 is GN-1; the config repo key is "study_tutor" (underscore) but the
    # gold table uses "study-tutor" (hyphen) — the exclusion must fire across the naming skew.
    repo = tmp_path / "study_tutor"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n"})
    _write_merge_summary(repo, "FEAT-SMP-002", {
        "merged_commit": sha,
        "tasks": [{"id": "TASK-SMP2-07", "decision": "approved"}],
    })
    result = discover_source_task_refs({"study_tutor": repo})
    assert result.included == []
    assert any(e.task == "TASK-SMP2-07" and "gold-negative" in e.reason for e in result.excluded)


# --------------------------------------------------------------------------------------
# File-map scoping (b).
# --------------------------------------------------------------------------------------
def test_scope_file_map_filters_by_extension_and_dirs(tmp_path):
    tree = tmp_path / "tree"
    (tree / "src").mkdir(parents=True)
    (tree / "src" / "keep.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (tree / "tests").mkdir()
    (tree / "tests" / "test_keep.py").write_text("def test_f():\n    assert True\n", encoding="utf-8")
    (tree / "README.md").write_text("# doc\n", encoding="utf-8")
    (tree / "image.png").write_bytes(b"\x89PNG\r\n\x00binary")          # wrong ext + binary
    (tree / ".venv").mkdir()
    (tree / ".venv" / "vendored.py").write_text("import x\n", encoding="utf-8")  # excluded dir
    (tree / ".guardkit").mkdir()
    (tree / ".guardkit" / "record.json").write_text("{}", encoding="utf-8")      # excluded dir
    fm = scope_file_map(tree)
    assert set(fm) == {"src/keep.py", "tests/test_keep.py", "README.md"}


def test_scope_file_map_binary_and_oversize_guard(tmp_path):
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "nul.py").write_bytes(b"x = 1\x00\n")                # null byte -> binary
    (tree / "big.py").write_text("# " + "a" * (MAX_FILE_BYTES + 10), encoding="utf-8")  # oversize
    (tree / "ok.py").write_text("x = 1\n", encoding="utf-8")
    fm = scope_file_map(tree)
    assert set(fm) == {"ok.py"}


def test_checkout_scoped_file_map_reads_at_sha_and_cleans_up(tmp_path):
    repo = tmp_path / "repo"
    sha = _init_repo(repo, {
        "src/a.py": "x = 1\n",
        "tests/test_a.py": "def test(): assert True\n",
        "assets/logo.png": "PNGDATA",  # .png -> scoped out
    })
    worktree = tmp_path / "scratch" / "repo" / "TASK-1"
    fm = checkout_scoped_file_map(repo, sha, worktree)
    assert set(fm) == {"src/a.py", "tests/test_a.py"}
    assert fm["src/a.py"] == "x = 1\n"
    # worktree removed; the corpus repo's live tree untouched.
    assert not worktree.exists()
    listing = subprocess.run(
        ["git", "worktree", "list"], cwd=str(repo), capture_output=True, text=True
    ).stdout
    assert "TASK-1" not in listing


def test_checkout_raises_on_bad_sha(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo, {"src/a.py": "x = 1\n"})
    with pytest.raises(RuntimeError):
        checkout_scoped_file_map(repo, "deadbeefdeadbeef", tmp_path / "scratch" / "r" / "t")


# --------------------------------------------------------------------------------------
# Run-record materialization (finding 1) — reconstruct the HEAD autobuild record in the worktree.
#
# guardkit gather_evidence reads <worktree>/.guardkit/autobuild/<task>/task_work_results.json
# (verified in guardkit paths.py TaskArtifactPaths.TASK_WORK_RESULTS). ``.guardkit`` is gitignored
# in the corpus so a worktree checkout at the approved sha omits it — the record must be copied in.
# --------------------------------------------------------------------------------------
def _write_record(root: Path, rel_dir: str, task: str, *, extra: bool = True) -> Path:
    d = root / rel_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / RUN_RECORD_SENTINEL).write_text(
        json.dumps({"task_id": task, "files_authored": ["src/a.py"], "tests_passed": True}),
        encoding="utf-8",
    )
    if extra:
        (d / "player_turn_1.json").write_text(json.dumps({"turn": 1}), encoding="utf-8")
        (d / "coach_turn_1.json").write_text(json.dumps({"decision": "approve"}), encoding="utf-8")
    return d


def test_locate_run_record_dir_finds_archive_run_artifacts(tmp_path):
    # The FEAT-C332 shape: record lives at .guardkit/archive/<feature>/run1-artifacts-<task>/.
    repo = tmp_path / "guardkit"
    rec = _write_record(repo, ".guardkit/archive/FEAT-C332/run1-artifacts-TASK-QAWE-001", "TASK-QAWE-001")
    got = locate_run_record_dir(repo, "FEAT-C332", "TASK-QAWE-001")
    assert got == rec


def test_locate_run_record_dir_prefers_canonical_autobuild(tmp_path):
    # When both the canonical live autobuild dir AND an archived one exist, the canonical
    # .guardkit/autobuild/<task>/ (exactly what gather_evidence reads) wins.
    repo = tmp_path / "guardkit"
    _write_record(repo, ".guardkit/archive/FEAT-C332/run1-artifacts-TASK-QAWE-001", "TASK-QAWE-001")
    canonical = _write_record(repo, ".guardkit/autobuild/TASK-QAWE-001", "TASK-QAWE-001")
    assert locate_run_record_dir(repo, "FEAT-C332", "TASK-QAWE-001") == canonical


def test_locate_run_record_dir_absent_returns_none(tmp_path):
    # A bare task dir with NO task_work_results.json (the .guardkit/archive/<feat>/<task>/ that
    # holds only progress.log) is not a record — absence returns None (drives the loud exclusion).
    repo = tmp_path / "guardkit"
    bare = repo / ".guardkit" / "archive" / "FEAT-C332" / "TASK-QAWE-001"
    bare.mkdir(parents=True)
    (bare / "progress.log").write_text("started\n", encoding="utf-8")
    assert locate_run_record_dir(repo, "FEAT-C332", "TASK-QAWE-001") is None


# --------------------------------------------------------------------------------------
# Factory-side record store — the HEAD-missing recovery path (S-B, 2026-07-21).
# --------------------------------------------------------------------------------------
def _write_store_record(store_root: Path, repo: str, task: str) -> Path:
    """A recovered record laid out as <store_root>/<repo>/<task>/ (the store contract)."""
    return _write_record(store_root, f"{repo}/{task}", task)


def test_record_store_root_recovers_a_head_missing_record(tmp_path):
    # The task's record is ABSENT from the corpus tree but PRESENT in the factory store — the
    # exact shape of the 10 recovered tasks (worktree-artifacts / live-worktree / git-blob source
    # copied into domains/qa-verifier/record-store/<repo>/<task>/).
    repo = tmp_path / "guardkit"  # no .guardkit record for the task
    store = tmp_path / "record-store"
    rec = _write_store_record(store, "guardkit", "TASK-QAWE-003")

    # Without the store root: absent (reproduces the round-4 SKIP).
    assert locate_run_record_dir(repo, "FEAT-C332", "TASK-QAWE-003") is None
    # With the store root + repo: the recovered record is found.
    got = locate_run_record_dir(
        repo, "FEAT-C332", "TASK-QAWE-003",
        repo="guardkit", record_store_roots=[store],
    )
    assert got == rec
    assert json.loads((got / RUN_RECORD_SENTINEL).read_text())["task_id"] == "TASK-QAWE-003"


def test_record_store_is_additive_corpus_wins(tmp_path):
    # An already-materializable task keeps its LIVE corpus source; the store never shadows it.
    repo = tmp_path / "guardkit"
    canonical = _write_record(repo, ".guardkit/autobuild/TASK-QAWE-001", "TASK-QAWE-001")
    store = tmp_path / "record-store"
    _write_store_record(store, "guardkit", "TASK-QAWE-001")
    got = locate_run_record_dir(
        repo, "FEAT-C332", "TASK-QAWE-001",
        repo="guardkit", record_store_roots=[store],
    )
    assert got == canonical  # corpus candidate ordered before the store


def test_record_store_ignored_without_repo(tmp_path):
    # The store is keyed by repo; with no repo name it is not consulted (backward-compatible with
    # the 3-arg call sites).
    repo = tmp_path / "guardkit"
    store = tmp_path / "record-store"
    _write_store_record(store, "guardkit", "TASK-QAWE-003")
    assert locate_run_record_dir(repo, "FEAT-C332", "TASK-QAWE-003") is None
    assert locate_run_record_dir(
        repo, "FEAT-C332", "TASK-QAWE-003", record_store_roots=[store]
    ) is None  # repo omitted -> store skipped


def test_record_store_absent_everywhere_still_excludes(tmp_path):
    # THE EXCLUSION LAW under recovery: a task with no authentic record in the corpus AND none in
    # any store root still returns None -> the loud exclusion fires (never fabricated).
    repo = tmp_path / "guardkit"
    store = tmp_path / "record-store"
    store.mkdir()  # empty store
    assert locate_run_record_dir(
        repo, "FEAT-C332", "TASK-GHOST-001",
        repo="guardkit", record_store_roots=[store],
    ) is None


def test_materialize_run_record_writes_at_exact_gather_read_path(tmp_path):
    repo = tmp_path / "guardkit"
    rec = _write_record(repo, ".guardkit/archive/FEAT-C332/run1-artifacts-TASK-QAWE-001", "TASK-QAWE-001")
    worktree = tmp_path / "scratch" / "guardkit" / "TASK-QAWE-001" / "R-CONTROL-noop"
    (worktree / "src").mkdir(parents=True)
    (worktree / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")  # the scoped-map tree

    written = materialize_run_record(rec, worktree, "TASK-QAWE-001")

    # THE EXACT path guardkit gather_evidence reads (TaskArtifactPaths.TASK_WORK_RESULTS).
    gather_read = worktree / ".guardkit" / "autobuild" / "TASK-QAWE-001" / "task_work_results.json"
    assert gather_read.is_file()
    assert json.loads(gather_read.read_text())["task_id"] == "TASK-QAWE-001"
    # siblings the honesty / gate reads consume come across too; the scoped tree is untouched.
    assert (gather_read.parent / "player_turn_1.json").is_file()
    assert (gather_read.parent / "coach_turn_1.json").is_file()
    assert str(gather_read) in written
    assert (worktree / "src" / "a.py").read_text() == "x = 1\n"


def test_discover_source_tasks_materializes_present_record_and_excludes_absent(tmp_path, caplog):
    # End-to-end wiring on a temp git repo: a task WITH a HEAD record is included and carries its
    # record_dir; a task with NO record is EXCLUDED loudly (the discovery exclusion-law pattern).
    repo = tmp_path / "guardkit"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n", "tests/test_a.py": "def test(): assert True\n"})
    # .guardkit written AFTER the commit -> untracked (mirrors the gitignored corpus reality).
    _write_merge_summary(repo, "FEAT-C332", {
        "merged_commit": sha,
        "tasks": [
            {"id": "TASK-HAS-REC", "decision": "approved"},
            {"id": "TASK-NO-REC", "decision": "approved"},
        ],
    })
    rec = _write_record(repo, ".guardkit/archive/FEAT-C332/run1-artifacts-TASK-HAS-REC", "TASK-HAS-REC")

    config = SimpleNamespace(
        corpus_roots={"guardkit": str(repo)},
        scratch_dir=str(tmp_path / "scratch"),
    )
    with caplog.at_level(logging.WARNING, logger="qav.discover"):
        resolved = discover_source_tasks(config)

    tasks = {r.task: r for r in resolved}
    assert set(tasks) == {"TASK-HAS-REC"}  # the recordless task never becomes a source task
    assert tasks["TASK-HAS-REC"].record_dir == str(rec)
    loud = "\n".join(r.getMessage() for r in caplog.records)
    assert "no autobuild run record found" in loud and "TASK-NO-REC" in loud


def test_discover_source_tasks_recovers_record_from_factory_store(tmp_path):
    # End-to-end recovery: a task with NO corpus record but a record in the factory store is
    # INCLUDED (the 10 HEAD-missing tasks' path). The record_dir points at the store, not the repo.
    repo = tmp_path / "guardkit"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n", "tests/test_a.py": "def test(): assert True\n"})
    _write_merge_summary(repo, "FEAT-C332", {
        "merged_commit": sha,
        "tasks": [{"id": "TASK-QAWE-003", "decision": "approved"}],
    })
    store = tmp_path / "record-store"
    rec = _write_store_record(store, "guardkit", "TASK-QAWE-003")

    config = SimpleNamespace(
        corpus_roots={"guardkit": str(repo)},
        scratch_dir=str(tmp_path / "scratch"),
        record_store_roots=[str(store)],
    )
    resolved = discover_source_tasks(config)
    tasks = {r.task: r for r in resolved}
    assert set(tasks) == {"TASK-QAWE-003"}
    assert tasks["TASK-QAWE-003"].record_dir == str(rec)  # recovered from the store


# --------------------------------------------------------------------------------------
# Feature-tracker reader (G1, 2026-07-21) — the .guardkit/features/*.yaml +
# archive/*/feature_state.yaml shape. The honesty law: a tracker NEVER *includes* a seeded source
# task (inclusion stays merge_summary-gated); it turns every candidate away with a PRECISE reason,
# resolving the committed merge sha from the record's prose where one exists.
# --------------------------------------------------------------------------------------
def _write_feature_tracker(root: Path, feature: str, record: dict) -> Path:
    d = root / ".guardkit" / "features"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{feature}.yaml"
    p.write_text(yaml.safe_dump({"id": feature, **record}), encoding="utf-8")
    return p


def _approved_task(task_id: str, decision: str = "approved") -> dict:
    return {"id": task_id, "status": "completed", "result": {"final_decision": decision}}


def test_resolve_tracker_sha_from_completed_evidence(tmp_path):
    # specialist-agent FEAT-32E7 shape: completed_evidence prose carries "merged to main <sha>".
    repo = tmp_path / "specialist_agent"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n"})
    got, reason = resolve_tracker_approved_sha(
        repo, {"completed_evidence": f"WS3 sweep: merged to main {sha} (Merge FEAT-32E7); waves..."}
    )
    assert got == sha and "completed_evidence" in reason


def test_resolve_tracker_sha_salvaged_to_main_commit_phrasing(tmp_path):
    repo = tmp_path / "forge"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n"})
    got, _ = resolve_tracker_approved_sha(
        repo, {"execution": {"note": f"manually salvaged to main commit {sha}"}}
    )
    assert got == sha


def test_resolve_tracker_sha_unresolvable_never_head(tmp_path):
    repo = tmp_path / "repo"
    head = _init_repo(repo, {"src/a.py": "x = 1\n"})
    got, reason = resolve_tracker_approved_sha(
        repo, {"completed_evidence": "merged to main deadbeefdeadbeef"}
    )
    assert got is None and got != head
    assert "unresolvable" in reason and "HEAD" in reason


def test_resolve_tracker_sha_absent_returns_none(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo, {"src/a.py": "x = 1\n"})
    got, reason = resolve_tracker_approved_sha(repo, {"completed_evidence": "done, all green"})
    assert got is None and "no committed merge-sha" in reason


def test_tracker_approved_task_excluded_never_included(tmp_path):
    # jarvis FEAT-28FF shape: completed tracker, tasks final_decision=approved, NO committed sha ->
    # per-task exclusion, and NOTHING included (inclusion stays merge_summary-gated).
    repo = tmp_path / "jarvis"
    _init_repo(repo, {"src/a.py": "x = 1\n"})
    _write_feature_tracker(repo, "FEAT-28FF", {
        "status": "completed",
        "tasks": [_approved_task("TASK-JNB-001"), _approved_task("TASK-JNB-002")],
    })
    result = discover_source_task_refs({"jarvis": repo})
    assert result.included == []  # THE LAW: a tracker never seeds an approve
    turned = {e.task: e for e in result.excluded if e.task}
    assert set(turned) == {"TASK-JNB-001", "TASK-JNB-002"}
    assert "feature-tracker record" in turned["TASK-JNB-001"].reason
    assert "no committed merge-sha" in turned["TASK-JNB-001"].reason
    assert "never guessed/HEAD" in turned["TASK-JNB-001"].reason


def test_tracker_false_green_with_resolvable_sha_still_excluded(tmp_path):
    # forge FEAT-FMDR trap: a tracker task reads final_decision=approved AND a real merge sha
    # resolves — but a tracker approve is NOT an autobuild coach-approve (documented false-green).
    # It must be turned away, with the resolvable sha NAMED as insufficient.
    repo = tmp_path / "forge"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n"})
    _write_feature_tracker(repo, "FEAT-FMDR", {
        "status": "completed",
        "completed_evidence": f"salvaged to main commit {sha} (autobuild-false-green-analysis)",
        "tasks": [_approved_task("TASK-FMDR-003"), _approved_task("TASK-FMDR-004")],
    })
    result = discover_source_task_refs({"forge": repo})
    assert result.included == []
    fmdr = [e for e in result.excluded if e.task == "TASK-FMDR-004"]
    assert len(fmdr) == 1
    assert sha in fmdr[0].reason and "resolvable" in fmdr[0].reason
    assert "autobuild" in fmdr[0].reason.lower() and "never guessed/HEAD" in fmdr[0].reason


def test_tracker_merged_but_stale_pending_tasks_named(tmp_path):
    # specialist-agent FEAT-32E7/8060: feature merged (sha resolves) but every per-task decision is
    # still 'pending' (result: None) -> a merged-but-stale exclusion that NAMES the sha, distinct
    # from an empty spec-only stub, and never inferred into an approve.
    repo = tmp_path / "specialist_agent"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n"})
    _write_feature_tracker(repo, "FEAT-32E7", {
        "status": "completed",
        "completed_evidence": f"merged to main {sha}; Stale planned->completed.",
        "tasks": [{"id": "TASK-SPL7-001", "status": "pending", "result": None}],
    })
    result = discover_source_task_refs({"specialist_agent": repo})
    assert result.included == []
    stale = [e for e in result.excluded if e.feature == "FEAT-32E7"]
    assert len(stale) == 1 and stale[0].task is None
    assert sha in stale[0].reason and "no approvable task" in stale[0].reason


def test_tracker_gold_source_task_excluded_with_gold_reason(tmp_path):
    # A gold-negative task appearing as a tracker record keeps the gold-negative reason (never a
    # training row), same as the merge_summary path.
    repo = tmp_path / "study_tutor"
    _init_repo(repo, {"src/a.py": "x = 1\n"})
    _write_feature_tracker(repo, "FEAT-SMP-002", {
        "status": "completed",
        "tasks": [_approved_task("TASK-SMP2-07")],  # GN-1
    })
    result = discover_source_task_refs({"study_tutor": repo})
    assert result.included == []
    assert any(e.task == "TASK-SMP2-07" and "gold-negative" in e.reason for e in result.excluded)


def test_tracker_spec_only_stub_keeps_spec_only_reason(tmp_path):
    # A genuinely planned stub (no task results) keeps the pre-existing whole-feature spec-only
    # reason — the refined reader must not regress the FEAT-SMP-001 case.
    repo = tmp_path / "guardkit"
    _init_repo(repo, {"src/a.py": "x = 1\n"})
    _write_feature_tracker(repo, "FEAT-0D1C", {
        "status": "planned",
        "tasks": [{"id": "T-1", "status": "pending", "result": None}],
    })
    result = discover_source_task_refs({"guardkit": repo})
    stub = [e for e in result.excluded if e.feature == "FEAT-0D1C"]
    assert len(stub) == 1 and stub[0].task is None
    assert "spec-only" in stub[0].reason and "never defaulted to HEAD" in stub[0].reason


def test_tracker_does_not_double_count_merge_summary_feature(tmp_path):
    # A feature present as BOTH a merge_summary (archive) and a tracker (features/<FEAT>.yaml) is
    # handled ONLY by the merge_summary path — the tracker walk must skip it (merge_summary wins).
    repo = tmp_path / "guardkit"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n"})
    _write_merge_summary(repo, "FEAT-E2CB", {
        "merged_commit": sha,
        "tasks": [{"id": "TASK-BDDW-001", "decision": "approved"}],
    })
    _write_feature_tracker(repo, "FEAT-E2CB", {
        "status": "completed", "tasks": [_approved_task("TASK-BDDW-001")],
    })
    result = discover_source_task_refs({"guardkit": repo})
    assert [r.task for r in result.included] == ["TASK-BDDW-001"]  # included via merge_summary
    # no tracker exclusion for the same feature (not turned away twice)
    assert not any(e.feature == "FEAT-E2CB" and "feature-tracker record" in e.reason
                   for e in result.excluded)


def test_tracker_walks_archived_feature_state(tmp_path):
    # The archived tracker shape (.guardkit/archive/<FEAT>/feature_state.yaml) with no
    # merge_summary is walked too (jarvis FEAT-J005-946D shape) — its approved tasks are recorded
    # turn-aways, not silent.
    repo = tmp_path / "jarvis"
    _init_repo(repo, {"src/a.py": "x = 1\n"})
    d = repo / ".guardkit" / "archive" / "FEAT-J005-946D"
    d.mkdir(parents=True)
    (d / "feature_state.yaml").write_text(
        yaml.safe_dump({"id": "FEAT-J005-946D", "status": "completed",
                        "tasks": [_approved_task("TASK-J005-001")]}),
        encoding="utf-8",
    )
    result = discover_source_task_refs({"jarvis": repo})
    assert result.included == []
    assert any(e.task == "TASK-J005-001" and "feature-tracker record" in e.reason
               for e in result.excluded)


def test_checkout_with_relative_worktree_path_never_plants_inside_corpus(tmp_path, monkeypatch):
    # The spike round-2 wall: a factory-RELATIVE worktree path is resolved by git against the
    # CORPUS repo (its cwd), planting the worktree inside the corpus tree while the factory
    # reads the nonexistent factory-relative path -> empty file map, silent skip.
    repo = tmp_path / "corpus" / "repo"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n", "tests/test_a.py": "def test(): assert True\n"})
    factory_cwd = tmp_path / "factory"
    factory_cwd.mkdir()
    monkeypatch.chdir(factory_cwd)
    fm = checkout_scoped_file_map(repo, sha, Path("scratch/repo/TASK-REL"))
    assert set(fm) == {"src/a.py", "tests/test_a.py"}  # round 2 read {} here
    # nothing planted inside the corpus repo, scratch cleaned from the factory side
    assert not (repo / "scratch").exists()
    assert not (factory_cwd / "scratch" / "repo" / "TASK-REL").exists()
    listing = subprocess.run(
        ["git", "worktree", "list"], cwd=str(repo), capture_output=True, text=True
    ).stdout
    assert "TASK-REL" not in listing


# --------------------------------------------------------------------------------------
# RATIFIED-CONSUMABLES AS SEEDED SOURCES (SB, 2026-07-22) — approve-only law, sha-resolution,
# run-record existence, gold exclusion, dedupe. Hermetic: real temp git repo + fixture records
# + duck-typed outcome objects (mirrors qav.harvest.Outcome's .ground_truth_source/.feature/.sha).
# --------------------------------------------------------------------------------------
def _oc(ground_truth_source: str, feature: str, sha: str):
    """A duck-typed consumable outcome (the fields consumable_source_task_refs reads)."""
    return SimpleNamespace(ground_truth_source=ground_truth_source, feature=feature, sha=sha)


def _consumable_repo(tmp_path, task="TASK-MP-001", feature="FEAT-SPL-002"):
    """A corpus repo with NO merge_summary for the task (the consumable-only shape) but a live
    ``.guardkit/autobuild/<task>/`` run record at HEAD, returning (repo, resolved_sha)."""
    repo = tmp_path / "forge"
    sha = _init_repo(repo, {"src/mp.py": "x = 1\n", "tests/test_mp.py": "def test(): assert True\n"})
    _write_record(repo, f".guardkit/autobuild/{task}", task)
    return repo, sha


def test_consumable_approve_with_resolvable_sha_and_record_is_included(tmp_path):
    repo, sha = _consumable_repo(tmp_path)
    result = consumable_source_task_refs(
        {"forge": repo}, {("forge", "TASK-MP-001"): _oc("coach_correct", "FEAT-SPL-002", sha)}
    )
    assert [(r.repo, r.task, r.feature, r.sha) for r in result.included] == [
        ("forge", "TASK-MP-001", "FEAT-SPL-002", sha)
    ]
    assert result.excluded == []


def test_consumable_reject_labeled_is_excluded_approve_only_law(tmp_path):
    # THE APPROVE-ONLY LAW: a reject-labeled consumable is NOT a green seeding base — never seeded.
    repo, sha = _consumable_repo(tmp_path)
    for reject_src in ("merge_review_caught", "operator_caught", "live_gate_caught"):
        result = consumable_source_task_refs(
            {"forge": repo}, {("forge", "TASK-MP-001"): _oc(reject_src, "FEAT-SPL-002", sha)}
        )
        assert result.included == []
        assert len(result.excluded) == 1
        assert result.excluded[0].task == "TASK-MP-001"
        assert "not a known-green seeding base" in result.excluded[0].reason
        assert reject_src in result.excluded[0].reason
    # sanity: the constant is the one approve source, not a reject one.
    assert APPROVE_GROUND_TRUTH_SOURCE == "coach_correct"


def test_consumable_unresolvable_sha_excluded_never_head(tmp_path):
    repo, head = _consumable_repo(tmp_path)
    result = consumable_source_task_refs(
        {"forge": repo},
        {("forge", "TASK-MP-001"): _oc("coach_correct", "FEAT-SPL-002", "deadbeefdeadbeef")},
    )
    assert result.included == []  # NEVER falls back to HEAD
    assert len(result.excluded) == 1
    reason = result.excluded[0].reason
    assert "does not resolve" in reason and "HEAD" in reason
    assert head not in reason


def test_consumable_no_run_record_excluded_never_fabricated(tmp_path):
    # sha resolves but NO task_work_results.json anywhere -> excluded (never fabricated).
    repo = tmp_path / "forge"
    sha = _init_repo(repo, {"src/mp.py": "x = 1\n"})  # no .guardkit record written
    result = consumable_source_task_refs(
        {"forge": repo}, {("forge", "TASK-MP-001"): _oc("coach_correct", "FEAT-SPL-002", sha)}
    )
    assert result.included == []
    assert "no autobuild run record" in result.excluded[0].reason


def test_consumable_record_recovered_from_factory_store(tmp_path):
    # Record ABSENT from the corpus but PRESENT in the factory record store -> INCLUDED.
    repo = tmp_path / "guardkit"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n"})
    store = tmp_path / "record-store"
    _write_record(store, "guardkit/TASK-QAWE-003", "TASK-QAWE-003")
    # Without the store: no record -> excluded.
    without = consumable_source_task_refs(
        {"guardkit": repo}, {("guardkit", "TASK-QAWE-003"): _oc("coach_correct", "FEAT-C332", sha)}
    )
    assert without.included == []
    # With the store root: recovered -> included.
    got = consumable_source_task_refs(
        {"guardkit": repo}, {("guardkit", "TASK-QAWE-003"): _oc("coach_correct", "FEAT-C332", sha)},
        record_store_roots=[store],
    )
    assert [(r.repo, r.task) for r in got.included] == [("guardkit", "TASK-QAWE-003")]


def test_consumable_gold_source_task_excluded(tmp_path):
    # A gold-negative source task never seeds a training row, even as a ratified approve consumable.
    repo, sha = _consumable_repo(tmp_path)
    gold = {("forge", "TASK-MP-001")}
    result = consumable_source_task_refs(
        {"forge": repo}, {("forge", "TASK-MP-001"): _oc("coach_correct", "FEAT-SPL-002", sha)},
        gold_source_tasks=gold,
    )
    assert result.included == []
    assert "gold-negative source task" in result.excluded[0].reason


def test_consumable_deduped_against_merge_summary(tmp_path):
    # A consumable whose (repo, task) is ALREADY discovered from a merge_summary is NOT re-added
    # (the base walk owns it) and is not a turn-away (no exclusion emitted).
    repo, sha = _consumable_repo(tmp_path)
    result = consumable_source_task_refs(
        {"forge": repo}, {("forge", "TASK-MP-001"): _oc("coach_correct", "FEAT-SPL-002", sha)},
        already_included={("forge", "TASK-MP-001")},
    )
    assert result.included == []
    assert result.excluded == []  # deduped, not excluded


def test_consumable_dedupe_normalises_repo_name(tmp_path):
    # already_included may spell the repo study-tutor while the outcome spells study_tutor.
    repo = tmp_path / "study-tutor"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n"})
    _write_record(repo, ".guardkit/autobuild/TASK-VOX-002", "TASK-VOX-002")
    result = consumable_source_task_refs(
        {"study_tutor": repo},
        {("study_tutor", "TASK-VOX-002"): _oc("coach_correct", "FEAT-VOICE-001", sha)},
        already_included={("study-tutor", "TASK-VOX-002")},
    )
    assert result.included == [] and result.excluded == []


def test_consumable_no_corpus_root_for_repo_excluded(tmp_path):
    result = consumable_source_task_refs(
        {"forge": tmp_path / "forge"},
        {("ghost_repo", "TASK-X"): _oc("coach_correct", "FEAT-Y", "abc1234")},
    )
    assert result.included == []
    assert "no corpus root configured" in result.excluded[0].reason


def test_discover_source_task_refs_admits_consumable_and_dedupes(tmp_path):
    # End to end through discover_source_task_refs: a merge_summary task AND a consumable-only task
    # in the same repo. The merge_summary task is included by the base walk; the consumable that
    # shares its coordinates dedupes out; a distinct consumable is admitted.
    repo = tmp_path / "guardkit"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n"})
    _write_merge_summary(repo, "FEAT-E2CB", {
        "merged_commit": sha,
        "tasks": [{"id": "TASK-BDDW-001", "decision": "approved"}],
    })
    _write_record(repo, ".guardkit/autobuild/TASK-BDDW-001", "TASK-BDDW-001")
    _write_record(repo, ".guardkit/autobuild/TASK-QAV-006", "TASK-QAV-006")
    outcomes = {
        ("guardkit", "TASK-BDDW-001"): _oc("coach_correct", "FEAT-E2CB", sha),   # dedupes out
        ("guardkit", "TASK-QAV-006"): _oc("coach_correct", "FEAT-0E6D", sha),    # NEW seeded source
        ("guardkit", "TASK-REJ-001"): _oc("merge_review_caught", "FEAT-R", sha),  # reject -> excluded
    }
    base = discover_source_task_refs({"guardkit": repo})
    withc = discover_source_task_refs({"guardkit": repo}, consumable_outcomes=outcomes)
    assert {(r.task) for r in base.included} == {"TASK-BDDW-001"}
    # after: the base task + the one distinct approve consumable, no double-count of BDDW-001.
    assert {r.task for r in withc.included} == {"TASK-BDDW-001", "TASK-QAV-006"}
    assert sum(r.task == "TASK-BDDW-001" for r in withc.included) == 1
    assert any(e.task == "TASK-REJ-001" and "not a known-green" in e.reason for e in withc.excluded)


def test_discover_source_task_refs_no_outcomes_is_byte_identical(tmp_path):
    # Backward-compat: None/absent outcomes => the pre-lever merge_summary-only result unchanged.
    repo = tmp_path / "guardkit"
    sha = _init_repo(repo, {"src/a.py": "x = 1\n"})
    _write_merge_summary(repo, "FEAT-AAA", {
        "merged_commit": sha, "tasks": [{"id": "TASK-1", "decision": "approved"}],
    })
    a = discover_source_task_refs({"guardkit": repo})
    b = discover_source_task_refs({"guardkit": repo}, consumable_outcomes=None)
    c = discover_source_task_refs({"guardkit": repo}, consumable_outcomes={})
    assert [(r.repo, r.task, r.sha) for r in a.included] == [(r.repo, r.task, r.sha) for r in b.included]
    assert [(r.repo, r.task, r.sha) for r in c.included] == [(r.repo, r.task, r.sha) for r in b.included]
