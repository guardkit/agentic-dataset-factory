"""Source-task discovery + file-map scoping for the QAV ``seeded_code`` pipeline (PLAN §2).

Two of the three generation-run seams the spike receipt
(``domains/qa-verifier/receipts/spike-one-row-2026-07-20.md``) named:

**(a) SOURCE-TASK DISCOVERY.** Walk each corpus repo's ``.guardkit`` records, enumerate the
known-green source tasks, and resolve each one's APPROVED SHA from *real on-disk record
evidence* — the per-feature ``.guardkit/archive/<FEAT>/merge_summary.json``, which records the
commit the feature's approved work landed at. THE APPROVED-SHA HONESTY LAW: a task whose
approved sha cannot be resolved from a record (no merge_summary, no recognised commit key, or a
sha that does not resolve in the repo's git) is EXCLUDED with a logged reason — **never guessed,
never silently defaulted to HEAD**. A spec-only feature (a ``.guardkit/features/<FEAT>.yaml`` with
no archive run record — e.g. study-tutor ``FEAT-SMP-001``) comes out as an excluded row, proving
the law fires.

**(b) FILE-MAP SCOPING.** For each included task, check the repo out at the approved sha into a
read-only scratch git worktree (under ``config.scratch_dir``) and read the recipe-relevant file
map into memory — source/test *text* files only, with a size + binary guard (the injector recipes
in ``qav.recipes`` operate on ``.py`` / test / plan-doc text). The worktree is removed after the
map is read; the corpus repo's live tree is **never** mutated (the read-only venue rule).

The record/pure functions (approved-sha resolution, the exclusion law, the scoping filter) are
unit-tested hermetically. The live-corpus walk + git-worktree checkout is a *generation run*
(real git I/O against the corpus repos) and is exercised only on the attended GB10 run —
``qav.generate._discover_source_tasks`` calls :func:`discover_source_tasks` there.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from qav.gold_negatives import GOLD_NEGATIVES

logger = logging.getLogger(__name__)

# The gold-negative source tasks (repo, task) — excluded from every seeded pipeline by
# construction. Repo names are compared normalised (``study-tutor`` vs ``study_tutor``).
GOLD_SOURCE_TASKS: frozenset[tuple[str, str]] = frozenset(
    (gn.repo, gn.task) for gn in GOLD_NEGATIVES
)

# ---------------------------------------------------------------------------------------------
# The approved-sha source of record (verified on disk 2026-07-20 across the three corpus repos).
# ``merge_summary.json`` records the commit a feature's approved work LANDED at. The key name
# varies by merge strategy / repo; these are the "landed on the integration branch" keys, in
# priority order. base/before/branch-tip keys are deliberately NOT approved shas.
#   - guardkit FEAT-E2CB (fast-forward): merged_commit
#   - guardkit FEAT-C332 (merge-commit): merge_commit
#   - study-tutor FEAT-70A4 (fast-forward): main_head_after
# A merge_summary that carries none of these (e.g. study-tutor FEAT-PO-002) -> EXCLUDED.
# ---------------------------------------------------------------------------------------------
APPROVED_SHA_KEYS: tuple[str, ...] = ("merged_commit", "merge_commit", "main_head_after")
_TASK_LIST_KEYS: tuple[str, ...] = ("tasks", "tasks_merged")
_MERGE_SUMMARY = "merge_summary.json"
_ARCHIVE_REL = Path(".guardkit") / "archive"
_AUTOBUILD_REL = Path(".guardkit") / "autobuild"
_FEATURES_REL = Path(".guardkit") / "features"

# ---------------------------------------------------------------------------------------------
# RUN-RECORD MATERIALIZATION — reconstruct the task's original autobuild record in the worktree.
#
# guardkit ``CoachValidator.gather_evidence`` reads the Player's task-work record from the EXACT
# path (verified in guardkit source 2026-07-20):
#   guardkit/orchestrator/paths.py  TaskArtifactPaths.TASK_WORK_RESULTS
#       = ".guardkit/autobuild/{task_id}/task_work_results.json"
#   coach_validator.py:4203  read_quality_gate_results -> task_work_results_path(task_id, worktree)
#       -> <worktree>/.guardkit/autobuild/<task>/task_work_results.json  (missing -> the
#          ``partial_exception`` / ``missing_results`` evidence-empty bundle the round-3 spike hit).
#
# But ``.guardkit`` is GITIGNORED in the corpus repos, so a ``git worktree add`` at the approved
# sha checks out the tracked source tree ONLY — the run record is absent from the scratch worktree
# even though it exists on disk at the corpus repo's HEAD. gather_evidence then short-circuits to
# an all-null bundle (the round-3 poison). We therefore copy the task's HEAD run-record artifacts
# into the worktree's expected ``.guardkit/autobuild/<task>/`` before regeneration.
#
# HONESTY (reconstruction, NOT fabrication): the HEAD ``.guardkit`` record IS the authentic record
# of that task's original approved autobuild run — the git checkout drops it only because
# ``.guardkit`` is gitignored, never because the run did not happen. We copy the real recorded
# artifacts verbatim; we never synthesise a task_work_results. A task whose record artifacts cannot
# be found at HEAD is EXCLUDED loudly (the discovery exclusion-law pattern) rather than regenerated
# against an empty record — we do not manufacture evidence for a run whose record is gone.
# ---------------------------------------------------------------------------------------------
RUN_RECORD_SENTINEL = "task_work_results.json"  # the artifact gather_evidence hard-requires


def _dedup_preserve(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        key = str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _candidate_record_dirs(corpus_root: Path, feature: Optional[str], task: str) -> list[Path]:
    """Candidate on-disk directories that may hold ``task``'s original run record, in priority
    order: the canonical live autobuild path first (exactly what gather_evidence reads), then the
    archived approved-run artifacts under the resolved feature, then live/foreign run-artifacts
    dirs. Globs are ordered so a deterministic first-hit wins."""
    gk_autobuild = corpus_root / _AUTOBUILD_REL
    gk_archive = corpus_root / _ARCHIVE_REL
    cands: list[Path] = [gk_autobuild / task]  # 1. canonical live autobuild dir
    if feature:
        # 2. archived approved-run artifacts under the resolved feature (e.g.
        #    .guardkit/archive/FEAT-C332/run1-artifacts-TASK-QAWE-001/). Latest run wins.
        cands += sorted(gk_archive.glob(f"{feature}/*-artifacts-{task}"), reverse=True)
        cands.append(gk_archive / feature / task)  # bare archived task dir
    # 3. live autobuild run-artifacts dirs (e.g. .guardkit/autobuild/FEAT-*-run2-artifacts-<task>/).
    cands += sorted(gk_autobuild.glob(f"*-artifacts-{task}"), reverse=True)
    # 4. archived run-artifacts under ANY feature (fallback for a mis-attributed feature key).
    cands += sorted(gk_archive.glob(f"*/*-artifacts-{task}"), reverse=True)
    return _dedup_preserve(cands)


def locate_run_record_dir(
    corpus_root: Path, feature: Optional[str], task: str
) -> Optional[Path]:
    """Return the corpus-HEAD directory holding ``task``'s original run record (the first candidate
    that actually contains ``task_work_results.json``), or ``None`` if no record exists at HEAD.

    Pure filesystem read over the corpus repo's live ``.guardkit`` tree (no git, no model)."""
    corpus_root = Path(corpus_root)
    for cand in _candidate_record_dirs(corpus_root, feature, task):
        if (cand / RUN_RECORD_SENTINEL).is_file():
            return cand
    return None


def materialize_run_record(record_dir: Path, worktree: Path, task: str) -> list[str]:
    """Copy the task's HEAD run-record artifacts into the worktree at the EXACT location
    gather_evidence reads — ``<worktree>/.guardkit/autobuild/<task>/`` (guardkit
    ``TaskArtifactPaths.TASK_WORK_RESULTS``). Copies every regular file in ``record_dir`` verbatim
    (task_work_results.json + player/coach turn records + siblings the honesty/gate reads consume);
    subdirectories are skipped (the record artifacts are flat). Returns the destination paths
    written. Reconstruction of the authentic record, never fabrication (see module note)."""
    record_dir = Path(record_dir)
    dest_dir = Path(worktree) / _AUTOBUILD_REL / task
    dest_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for src in sorted(record_dir.iterdir()):
        if not src.is_file():
            continue
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        written.append(str(dest))
    return written

# ---------------------------------------------------------------------------------------------
# File-map scoping — source/test text files the recipes operate on, size + binary guarded.
# ---------------------------------------------------------------------------------------------
SCOPED_EXTS: frozenset[str] = frozenset(
    {".py", ".md", ".yaml", ".yml", ".txt", ".cfg", ".toml", ".ini", ".json", ".feature", ".rst"}
)
EXCLUDE_DIR_PARTS: frozenset[str] = frozenset(
    {
        ".git", ".venv", "venv", "env", ".env", "node_modules", "__pycache__", ".guardkit",
        ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", "site-packages", "dist", "build",
        ".eggs", ".idea", ".vscode", ".hypothesis",
    }
)
MAX_FILE_BYTES = 512 * 1024


# ---------------------------------------------------------------------------------------------
# Record structures.
# ---------------------------------------------------------------------------------------------
@dataclass
class ResolvedSourceTask:
    """A known-green source task with a record-resolved approved sha (ready to check out)."""

    repo: str
    feature: str
    task: str
    sha: str
    files: dict[str, str] = field(default_factory=dict)
    evidence_paths: list[str] = field(default_factory=list)
    # The corpus-HEAD directory holding this task's original autobuild run record, to be
    # materialized into each per-recipe worktree at .guardkit/autobuild/<task>/ before regeneration
    # (reconstruction of the authentic record — see the RUN-RECORD MATERIALIZATION note).
    record_dir: Optional[str] = None


@dataclass
class SourceTaskRef:
    """A discovered source task before its worktree is read (repo + coordinates + approved sha)."""

    repo: str
    feature: str
    task: str
    sha: str
    evidence_paths: list[str] = field(default_factory=list)


@dataclass
class ExclusionRecord:
    """A candidate turned away by the discovery/approved-sha law, with the reason (logged, never
    silent). ``task`` is ``None`` for a whole-feature exclusion."""

    repo: str
    feature: str
    task: Optional[str]
    reason: str


@dataclass
class DiscoveryResult:
    included: list[SourceTaskRef]
    excluded: list[ExclusionRecord]


# ---------------------------------------------------------------------------------------------
# Approved-sha resolution — the honesty law.
# ---------------------------------------------------------------------------------------------
def _git_sha_resolves(repo_root: Path, sha: str) -> bool:
    """True iff ``sha`` names a commit object in ``repo_root``'s git (``git cat-file -e``)."""
    try:
        proc = subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def resolve_approved_sha(repo_root: Path, merge_summary: dict[str, Any]) -> tuple[Optional[str], str]:
    """Resolve a feature's approved sha from its ``merge_summary.json`` record.

    Returns ``(sha, reason)`` where ``sha`` is ``None`` when unresolvable. The reason names the
    record field used on success, or the specific cause on exclusion. NEVER returns HEAD or a
    guess — an unresolvable record is an exclusion, by law.
    """
    present = [
        (key, str(merge_summary[key]).strip())
        for key in APPROVED_SHA_KEYS
        if merge_summary.get(key)
    ]
    if not present:
        return None, (
            f"no approved-sha key in merge_summary (looked for {list(APPROVED_SHA_KEYS)}) — "
            "excluded, never defaulted to HEAD"
        )
    for key, sha in present:
        if _git_sha_resolves(repo_root, sha):
            return sha, f"merge_summary.{key}={sha}"
    unresolved = ", ".join(f"{k}={v}" for k, v in present)
    return None, (
        f"approved-sha candidate(s) present but unresolvable in {repo_root}/.git: {unresolved} — "
        "excluded, never defaulted to HEAD"
    )


def _normalise_repo(name: str) -> str:
    return name.replace("_", "-").lower()


def _is_gold_source(repo: str, task: str, gold: Iterable[tuple[str, str]]) -> bool:
    nrepo = _normalise_repo(repo)
    return any(_normalise_repo(gr) == nrepo and gt == task for gr, gt in gold)


def _iter_summary_tasks(merge_summary: dict[str, Any]) -> list[dict[str, Any]]:
    for key in _TASK_LIST_KEYS:
        value = merge_summary.get(key)
        if isinstance(value, list):
            return [t for t in value if isinstance(t, dict)]
    return []


def _is_approved(task_entry: dict[str, Any]) -> bool:
    decision = str(task_entry.get("decision", "")).lower()
    return "approved" in decision or "completed" in decision


def _evidence_paths(repo_root: Path, task: str, *, limit: int = 8) -> list[str]:
    """Best-effort: the serialized-bundle records on disk for ``task`` (provenance only — the
    seeded_code pipeline REGENERATES a fresh bundle; these are not read back)."""
    gk = repo_root / ".guardkit"
    if not gk.is_dir():
        return []
    out: list[str] = []
    try:
        for path in gk.rglob("coach_evidence_turn_*.json"):
            if path.parent.name == task:
                out.append(str(path))
                if len(out) >= limit:
                    break
    except OSError:
        return sorted(out)
    return sorted(out)


def discover_source_task_refs(
    corpus_roots: dict[str, Path],
    *,
    gold_source_tasks: Iterable[tuple[str, str]] = GOLD_SOURCE_TASKS,
) -> DiscoveryResult:
    """Walk each corpus repo's ``.guardkit`` records and split candidate source tasks into
    included (approved sha resolved) and excluded (with a logged reason). Pure over the on-disk
    records + the repos' git (no worktree checkout, no model, no network)."""
    included: list[SourceTaskRef] = []
    excluded: list[ExclusionRecord] = []

    for repo, root in sorted(corpus_roots.items()):
        root = Path(root)
        archive = root / _ARCHIVE_REL
        archived_features: set[str] = set()

        for ms_path in sorted(archive.glob(f"*/{_MERGE_SUMMARY}")):
            feature = ms_path.parent.name
            archived_features.add(feature)
            try:
                merge_summary = json.loads(ms_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                excluded.append(ExclusionRecord(repo, feature, None, f"unreadable merge_summary.json: {exc}"))
                continue
            if not isinstance(merge_summary, dict):
                excluded.append(ExclusionRecord(repo, feature, None, "merge_summary.json is not a JSON object"))
                continue

            sha, reason = resolve_approved_sha(root, merge_summary)
            tasks = _iter_summary_tasks(merge_summary)
            if sha is None:
                if tasks:
                    for task_entry in tasks:
                        excluded.append(ExclusionRecord(repo, feature, task_entry.get("id"), reason))
                else:
                    excluded.append(ExclusionRecord(repo, feature, None, reason))
                continue

            for task_entry in tasks:
                task_id = task_entry.get("id")
                if not task_id:
                    continue
                if not _is_approved(task_entry):
                    excluded.append(
                        ExclusionRecord(
                            repo, feature, task_id,
                            f"task decision not approved/completed ({task_entry.get('decision')!r})",
                        )
                    )
                    continue
                if _is_gold_source(repo, task_id, gold_source_tasks):
                    excluded.append(
                        ExclusionRecord(repo, feature, task_id, "gold-negative source task — never seeds a training row")
                    )
                    continue
                included.append(
                    SourceTaskRef(repo, feature, task_id, sha, _evidence_paths(root, task_id))
                )

        # Spec-only features (a features/<FEAT>.yaml with NO archive run record) prove the law:
        # they have no resolvable approved sha, so every one is an excluded row (e.g. FEAT-SMP-001).
        features_dir = root / _FEATURES_REL
        if features_dir.is_dir():
            for feature_path in sorted(features_dir.glob("*.yaml")):
                feature = feature_path.stem
                if feature in archived_features:
                    continue
                excluded.append(
                    ExclusionRecord(
                        repo, feature, None,
                        "spec-only feature — no .guardkit/archive/<feature>/merge_summary.json run "
                        "record; approved sha unresolvable (excluded, never defaulted to HEAD)",
                    )
                )

    included.sort(key=lambda r: (r.repo, r.feature, r.task))
    excluded.sort(key=lambda e: (e.repo, e.feature, e.task or ""))
    return DiscoveryResult(included=included, excluded=excluded)


# ---------------------------------------------------------------------------------------------
# File-map scoping (b).
# ---------------------------------------------------------------------------------------------
def scope_file_map(tree_root: Path) -> dict[str, str]:
    """Read the recipe-relevant file map from a checked-out tree: source/test text files under
    ``SCOPED_EXTS``, excluding vendored/venv/cache/``.guardkit`` dirs, oversized files, symlinks,
    and non-UTF-8/binary blobs (null-byte sniff). Returns ``{relpath -> text}``."""
    tree_root = Path(tree_root)
    file_map: dict[str, str] = {}
    for path in sorted(tree_root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        rel = path.relative_to(tree_root)
        if any(part in EXCLUDE_DIR_PARTS for part in rel.parts[:-1]):
            continue
        if path.suffix.lower() not in SCOPED_EXTS:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in data:  # binary guard
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        file_map[str(rel)] = text
    return file_map


def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", *args], cwd=str(repo_root), capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {repo_root} (rc={proc.returncode}): {proc.stderr.strip()}"
        )
    return proc


def _remove_worktree(repo_root: Path, worktree_path: Path) -> None:
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree_path)],
        cwd=str(repo_root), capture_output=True, text=True,
    )
    if worktree_path.exists():
        shutil.rmtree(worktree_path, ignore_errors=True)
    subprocess.run(["git", "worktree", "prune"], cwd=str(repo_root), capture_output=True, text=True)


def checkout_scoped_file_map(repo_root: Path, sha: str, worktree_path: Path) -> dict[str, str]:
    """Check ``repo_root`` out at ``sha`` into a fresh detached scratch worktree, read the scoped
    file map, and remove the worktree. Read-only-source: the corpus repo's live tree is never
    touched. Raises loudly if the git checkout fails."""
    repo_root = Path(repo_root)
    # Absolute, or git (cwd=repo_root) plants the worktree INSIDE the corpus repo while the
    # factory reads the factory-relative path — the spike round-2 empty-file-map wall.
    worktree_path = Path(worktree_path).resolve()
    if worktree_path.exists():
        _remove_worktree(repo_root, worktree_path)
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    _run_git(repo_root, ["worktree", "add", "--detach", "--force", str(worktree_path), sha])
    try:
        return scope_file_map(worktree_path)
    finally:
        _remove_worktree(repo_root, worktree_path)


# ---------------------------------------------------------------------------------------------
# The generation-run provider — glues (a) + (b). Called by qav.generate._discover_source_tasks.
# ---------------------------------------------------------------------------------------------
def discover_source_tasks(config: Any, *, limit: Optional[int] = None) -> list[ResolvedSourceTask]:  # pragma: no cover - generation run
    """Discover known-green source tasks from ``config.corpus_roots``, resolve each approved sha
    from the on-disk records (the exclusion law logs every turn-away), check each included task
    out at its sha into a scratch worktree under ``config.scratch_dir``, and read its scoped file
    map. Real git + filesystem work against the read-only corpus repos — a generation run, never
    reached by unit tests (they exercise the pure functions above and inject ``source_tasks``)."""
    corpus_roots = {k: Path(v) for k, v in dict(config.corpus_roots).items()}
    result = discover_source_task_refs(corpus_roots)

    for exc in result.excluded:
        logger.info(
            "DISCOVERY EXCLUDE %s/%s task=%s — %s", exc.repo, exc.feature, exc.task, exc.reason
        )
    logger.info(
        "DISCOVERY: %d source task(s) included, %d excluded",
        len(result.included), len(result.excluded),
    )

    src_root = Path(config.scratch_dir) / "_src"
    resolved: list[ResolvedSourceTask] = []
    for ref in result.included:
        worktree = src_root / ref.repo / ref.task
        files = checkout_scoped_file_map(corpus_roots[ref.repo], ref.sha, worktree)
        if not files:
            logger.warning(
                "DISCOVERY SKIP %s/%s — scoped file map empty at %s (nothing to inject)",
                ref.repo, ref.task, ref.sha,
            )
            continue
        # Locate the task's original run record at the corpus HEAD. Its ABSENCE is a loud
        # exclusion (the honesty law): without the authentic record, gather_evidence would emit
        # an evidence-empty ``missing_results`` bundle — we exclude rather than regenerate against
        # nothing (and never fabricate a record). The record is copied into each per-recipe
        # worktree at regeneration time (qav.generate._materialize_worktree).
        record_dir = locate_run_record_dir(corpus_roots[ref.repo], ref.feature, ref.task)
        if record_dir is None:
            logger.warning(
                "DISCOVERY SKIP %s/%s — no autobuild run record at HEAD (looked for "
                "%s under .guardkit/autobuild + .guardkit/archive/%s); cannot reconstruct "
                "authentic evidence, excluded (never fabricated)",
                ref.repo, ref.task, RUN_RECORD_SENTINEL, ref.feature,
            )
            continue
        resolved.append(
            ResolvedSourceTask(
                repo=ref.repo, feature=ref.feature, task=ref.task, sha=ref.sha,
                files=files, evidence_paths=ref.evidence_paths, record_dir=str(record_dir),
            )
        )
        if limit is not None and len(resolved) >= limit:
            break
    return resolved
