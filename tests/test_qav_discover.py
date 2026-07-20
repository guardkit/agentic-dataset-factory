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

from qav.discover import (
    APPROVED_SHA_KEYS,
    MAX_FILE_BYTES,
    RUN_RECORD_SENTINEL,
    checkout_scoped_file_map,
    discover_source_task_refs,
    discover_source_tasks,
    locate_run_record_dir,
    materialize_run_record,
    resolve_approved_sha,
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
    assert "no autobuild run record at HEAD" in loud and "TASK-NO-REC" in loud


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
