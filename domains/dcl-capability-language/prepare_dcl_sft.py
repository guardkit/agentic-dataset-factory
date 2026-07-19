#!/usr/bin/env python3
"""
prepare_dcl_sft.py — Stage the DCL pilot fine-tune corpus (authors + repairs)
=============================================================================
Assembles the DCL SFT training/eval sets for the **pilot fine-tune** (Rich's go,
2026-07-19: "get it done now") from TWO banked, verified corpora and writes them,
plus a staging manifest, OUTSIDE the repo under ``~/fine-tuning/data/`` (nothing under
``~/fine-tuning`` is ever committed; the corpus is private under DF-008 and NEVER committed).

Sources (READ-ONLY — never modified):

  AUTHORS  ``output_backup_dcl-authors87_20260719-040358/``
           train.jsonl  = 77 rows (all metadata.mode == dcl_author)   -> keep ALL
           eval_dcl.jsonl = 10 rows (all dcl_author)                  -> keep ALL
  REPAIRS  ``output_backup_dcl-corpus468_20260718-031402/``
           train.jsonl  = 415 rows (41 dcl_author RETIRED + 374 dcl_repair) -> keep repairs only
           eval_dcl.jsonl = 53 rows (7 dcl_author RETIRED + 46 dcl_repair)  -> keep repairs only

The 48 old author rows in the corpus468 set are RETIRED BY DESIGN (superseded by the
authors87 set under the new row_id scheme): every ``mode == dcl_author`` row from corpus468
is dropped; only its ``dcl_repair`` rows are kept.

Expected staged result: train = 77 authors + 374 repairs = 451 unique rows;
eval = 10 authors + 46 repairs = 56 rows; 507 total unique rows kept.

Author oversampling (``--author-reps``, default 2): the staged *train* file repeats each
author row K times (eval is NEVER oversampled). Rationale (recorded in the manifest + this
help): the ratified corpus target ratio was ~1:2 (author:repair) but authors under-delivered
(87 of 200 briefs; 113 hard-brief rejections). Oversampling K=2 -> 154 author copies : 374
repairs ~= 1:2.4, approximating the ratified mix. K is configurable; K=1 must work.

  DEVIATION FROM OUTPUT-CONTRACT.md (recorded here, contract left unedited): the base model
  changed to **Qwen/Qwen3-4B-Instruct-2507** (Apache-2.0, dense, non-thinking instruct) on
  2026-07-19 probe evidence; the chat template at train time is Qwen3's NATIVE tokenizer
  template (``<|im_start|>role\\n...<|im_end|>``), NOT ``gemma-4`` as the contract line says.
  This staging step is template-agnostic (it writes ShareGPT ``messages``); the template is
  applied by the trainer. The leak gate below screens Qwen3 control tokens accordingly.

Rows are trained AS-IS (verbatim verified rows): repair rows carry a ``<think>...</think>``
prefix in the assistant turn (the reasoning), then the corrected ```` ```dcl ```` fence AFTER
``</think>`` (the post-think law); author rows are direct (no think block).

Usage:
    python3 prepare_dcl_sft.py                       # defaults; writes to ~/fine-tuning/data/
    python3 prepare_dcl_sft.py --author-reps 1       # no oversampling (ablation)
    python3 prepare_dcl_sft.py --date 2026-07-19     # pin the manifest created date

Host-runnable: stdlib + ``src/dcl`` imports only. No heavy ML deps (the trainer imports those).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import random
import re
import sys
from collections import Counter
from pathlib import Path

# --------------------------------------------------------------------------------------
# Paths — resolved relative to the repo root (this file: domains/<domain>/prepare_dcl_sft.py)
# --------------------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]

# The two banked, verified corpora (READ-ONLY; never modified, never committed).
DEFAULT_AUTHORS_DIR = REPO_ROOT / "output_backup_dcl-authors87_20260719-040358"
DEFAULT_REPAIRS_DIR = REPO_ROOT / "output_backup_dcl-corpus468_20260718-031402"

# Frozen-exam tasks (READ-ONLY): the four dcl-held exams are the eval and are NEVER trained.
DEFAULT_FLEET_EVALS_DIR = REPO_ROOT.parent / "fleet-evals"

# Staged output goes OUTSIDE the repo (never committed).
DEFAULT_OUT_DIR = Path(os.path.expanduser("~/fine-tuning/data"))

# Expected counts after filtering (asserted; abort loudly on mismatch).
EXPECTED = {
    "authors_train": 77,
    "authors_eval": 10,
    "repairs_train": 374,
    "repairs_eval": 46,
}

# The deliberate pilot row floor (Rich-approved) and the architect runbook's MIN_ACCEPTED.
PILOT_ROW_FLOOR = 507
ARCHITECT_MIN_ACCEPTED = 1500

# Chat-template control tokens that must NEVER appear inside message content. Any hit teaches
# the model to emit template framing -> fatal. Qwen3 (im_start/im_end) + legacy gemma/harmony
# markers kept as belt-and-suspenders (the corpus predates the base swap).
LEAK_MARKERS = (
    "<|im_start|>", "<|im_end|>",           # Qwen3 native (the train-time template)
    "<|turn>", "<turn|>",                   # gemma-4 turn markers
    "<|channel>", "<channel|>",             # harmony/gemma channel markers
    "<start_of_turn>", "<end_of_turn>",     # gemma start/end-of-turn
)

# Frozen-exam cross-check: distinctive shingle width (consecutive normalized words).
SHINGLE_N = 8

EXPECTED_ROLES = ("system", "user", "assistant")
_DCL_FENCE_RE = re.compile(r"```dcl\s*\n.*?\n```", re.S)
_THINK_END_RE = re.compile(r"</think>", re.I)
_NORM_RE = re.compile(r"[^a-z0-9]+")
_THINK_BLOCK_RE = re.compile(r"^\s*<think>.*?</think>\s*", re.S | re.I)


def strip_think_prefix(content: str) -> str:
    """Remove the leading <think>...</think> block from a repair target (live-catch
    2026-07-19). The verified fix sits AFTER </think> (the post-think law), so stripping
    keeps exactly the compiler-verified answer."""
    return _THINK_BLOCK_RE.sub("", content, count=1)


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Stage the DCL pilot fine-tune corpus (authors + repairs) -> "
                    "~/fine-tuning/data/ + a staging manifest. READ-ONLY on all sources; "
                    "never writes into the repo.")
    p.add_argument("--authors-dir", default=str(DEFAULT_AUTHORS_DIR),
                   help="Banked authors87 corpus dir (keep ALL rows)")
    p.add_argument("--repairs-dir", default=str(DEFAULT_REPAIRS_DIR),
                   help="Banked corpus468 dir (keep ONLY mode==dcl_repair rows; authors RETIRED)")
    p.add_argument("--fleet-evals-dir", default=str(DEFAULT_FLEET_EVALS_DIR),
                   help="fleet-evals repo (READ-ONLY) — source of the frozen dcl-held exams")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR),
                   help="Staged output dir (OUTSIDE the repo; never committed)")
    p.add_argument("--author-reps", type=int, default=2,
                   help="Repeat each author TRAIN row K times to approximate the ratified "
                        "~1:2 author:repair ratio (authors under-delivered). Default 2. "
                        "eval is NEVER oversampled. K=1 disables oversampling.")
    p.add_argument("--seed", type=int, default=3407,
                   help="Deterministic shuffle seed for the staged train order")
    p.add_argument("--est-chars-per-token", type=float, default=3.5,
                   help="Char->token ratio for the seq-length audit (ESTIMATE; the "
                        "in-container real-tokenizer audit is ground truth)")
    p.add_argument("--date", default=None,
                   help="Manifest created date (YYYY-MM-DD). Default: max source-file mtime.")
    p.add_argument("--keep-think", action="store_true",
                   help="Keep the repair rows' leading <think>...</think> block in the STAGED "
                        "assistant targets. DEFAULT IS TO STRIP IT (live-catch 2026-07-19: "
                        "<think>/</think> are near-untrained added tokens in the non-thinking "
                        "Qwen3-4B-Instruct-2507 base; LoRA never touches lm_head, so training "
                        "targets on them collapse onto the confusable <tool_call> row at "
                        "generation — the first pilot run emitted <tool_call> spam. The stock "
                        "base already holds repair 3/3 WITHOUT emitting think, so think-free "
                        "targets are serve-faithful). Banked rows are verified under the "
                        "post-think law BEFORE stripping; sources on disk are never modified.")
    return p.parse_args(argv)


# --------------------------------------------------------------------------------------
# IO helpers
# --------------------------------------------------------------------------------------
def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            sys.exit(f"ERROR: malformed JSON at {path}:{i}: {e}")
    return rows


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------------------
# Row helpers
# --------------------------------------------------------------------------------------
def row_mode(row: dict) -> str:
    return row.get("metadata", {}).get("mode", "")


def row_id(row: dict) -> str | None:
    return row.get("metadata", {}).get("row_id")


def assistant_content(row: dict) -> str:
    return row["messages"][-1]["content"]


def find_leaks(text: str) -> list[str]:
    return [m for m in LEAK_MARKERS if m in text]


def has_post_think_dcl_fence(content: str, *, is_repair: bool) -> bool:
    """A ```dcl fence must be present in the assistant answer. For repair rows the fence
    must sit AFTER </think> (the post-think law) — a fence that only appears inside the
    <think> block quotes the BROKEN capability, not the fix, and must fail this gate."""
    if is_repair:
        m = _THINK_END_RE.search(content)
        answer = content[m.end():] if m else content
    else:
        answer = content
    return _DCL_FENCE_RE.search(answer) is not None


def normalize_words(text: str) -> list[str]:
    return [w for w in _NORM_RE.sub(" ", text.lower()).split() if w]


def shingles(text: str, n: int = SHINGLE_N) -> set[str]:
    words = normalize_words(text)
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


# --------------------------------------------------------------------------------------
# Verification of a kept unique row
# --------------------------------------------------------------------------------------
def verify_row(row: dict, *, source: str, split: str) -> list[str]:
    """Return a list of verification failures for a single kept row (empty = clean)."""
    fails: list[str] = []
    meta = row.get("metadata", {})
    rid = meta.get("row_id")
    if not rid:
        fails.append("metadata.row_id missing")
    if meta.get("compile_verified") is not True:
        fails.append("metadata.compile_verified is not true")
    msgs = row.get("messages", [])
    roles = tuple(m.get("role") for m in msgs)
    if roles != EXPECTED_ROLES:
        fails.append(f"message roles {roles} != {EXPECTED_ROLES}")
        return fails  # downstream checks assume the [system,user,assistant] shape
    is_repair = row_mode(row) == "dcl_repair"
    if not has_post_think_dcl_fence(assistant_content(row), is_repair=is_repair):
        where = "after </think>" if is_repair else "in assistant content"
        fails.append(f"no ```dcl fence {where}")
    return fails


# --------------------------------------------------------------------------------------
# Sequence-length audit (char-based ESTIMATE)
# --------------------------------------------------------------------------------------
def seqlen_audit(rows: list[dict], cpt: float) -> dict:
    """Estimate per-row token length (all message chars / cpt + template overhead) and
    report truncation rates at candidate max_seq_length buckets. cpt=3.5 chars/token is an
    ESTIMATE; the in-container real-tokenizer audit is ground truth."""
    TEMPLATE_OVERHEAD = 16  # role markers / bos / generation prompt, approx
    buckets = (4096, 6144, 8192, 12288)
    lens = sorted(
        sum(len(m["content"]) for m in r["messages"]) / cpt + TEMPLATE_OVERHEAD
        for r in rows
    )
    n = len(lens)

    def pctile(q):
        return lens[min(n - 1, int(q * n))]

    exceed = {thr: sum(1 for x in lens if x > thr) for thr in buckets}
    # Recommend the smallest bucket with ~0% truncation (< 0.5% exceeding).
    recommended = buckets[-1]
    for thr in buckets:
        if 100 * exceed[thr] / n < 0.5:
            recommended = thr
            break
    return {
        "est_chars_per_token": cpt,
        "n": n,
        "p50": round(pctile(0.50)),
        "p95": round(pctile(0.95)),
        "p99": round(pctile(0.99)),
        "max": round(lens[-1]),
        "exceed": {str(thr): {"rows": exceed[thr], "pct": round(100 * exceed[thr] / n, 2)}
                   for thr in buckets},
        "recommended_max_seq_length": recommended,
    }


# --------------------------------------------------------------------------------------
# Frozen-exam cross-check (READ-ONLY over fleet-evals)
# --------------------------------------------------------------------------------------
def load_exam_briefs(fleet_evals_dir: Path) -> dict[str, str]:
    """Read each dcl-held-* exam's brief BODY text (author briefs: feature-brief.md;
    repair exam: broken.dcl + diagnostics.json). Returns {task_name: brief_text}."""
    briefs: dict[str, str] = {}
    tasks_dir = fleet_evals_dir / "tasks"
    if not tasks_dir.is_dir():
        sys.exit(f"ERROR: fleet-evals tasks dir not found: {tasks_dir}")
    for task_dir in sorted(tasks_dir.glob("dcl-held-*")):
        inp = task_dir / "input"
        parts: list[str] = []
        for fname in ("feature-brief.md", "broken.dcl", "diagnostics.json"):
            fp = inp / fname
            if fp.is_file():
                parts.append(fp.read_text(encoding="utf-8"))
        if parts:
            briefs[task_dir.name] = "\n".join(parts)
    return briefs


def frozen_exam_crosscheck(train_rows: list[dict], briefs: dict[str, str]) -> dict:
    """Assert no staged TRAIN row's user content reproduces any exam brief's distinctive
    text. Robust normalized 8-gram shingle overlap over the brief BODY (not filenames)."""
    exam_shingles: dict[str, set[str]] = {name: shingles(body) for name, body in briefs.items()}
    total_shingles = sum(len(s) for s in exam_shingles.values())
    hits: list[dict] = []
    for row in train_rows:
        user = normalize_words(row["messages"][1]["content"])
        user_text = " ".join(user)
        for name, sh in exam_shingles.items():
            for shard in sh:
                if shard in user_text:
                    hits.append({"row_id": row_id(row), "exam": name, "shingle": shard})
                    break
    return {
        "status": "pass" if not hits else "fail",
        "method": f"normalized {SHINGLE_N}-gram shingle substring overlap, exam brief body vs "
                  f"train row user content",
        "exams_compared": sorted(exam_shingles),
        "exam_shingles_total": total_shingles,
        "train_rows_compared": len(train_rows),
        "hits": hits,
    }


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
def main(argv=None) -> int:
    args = parse_args(argv)  # handles --help before any heavy path work

    # dcl.contamination is host-safe (stdlib + subprocess only). Make the script runnable
    # from any cwd by putting the repo's src/ on the path, then import lazily (so --help and
    # py_compile never need it).
    src_path = str(REPO_ROOT / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    try:
        from dcl.contamination import check_contamination
    except ImportError as e:
        sys.exit(f"ERROR: cannot import dcl.contamination (expected src at {src_path}): {e}")

    authors_dir = Path(args.authors_dir)
    repairs_dir = Path(args.repairs_dir)
    fleet_evals_dir = Path(args.fleet_evals_dir)
    out_dir = Path(os.path.expanduser(args.out_dir))

    if args.author_reps < 1:
        sys.exit("ERROR: --author-reps must be >= 1")

    for d in (authors_dir, repairs_dir):
        for f in ("train.jsonl", "eval_dcl.jsonl", "manifest.json"):
            if not (d / f).is_file():
                sys.exit(f"ERROR: expected source file not found: {d / f}")

    # ---- 1. Load ----------------------------------------------------------------------
    authors_train = load_jsonl(authors_dir / "train.jsonl")
    authors_eval = load_jsonl(authors_dir / "eval_dcl.jsonl")
    repairs_train_all = load_jsonl(repairs_dir / "train.jsonl")
    repairs_eval_all = load_jsonl(repairs_dir / "eval_dcl.jsonl")

    # ---- 2. Filter --------------------------------------------------------------------
    # authors87: keep ALL. corpus468: keep ONLY mode==dcl_repair (authors RETIRED by design).
    non_author_in_authors = [r for r in authors_train + authors_eval
                             if row_mode(r) != "dcl_author"]
    if non_author_in_authors:
        sys.exit(f"ERROR: authors87 set contains {len(non_author_in_authors)} non-author "
                 f"row(s) — expected all mode==dcl_author. Abort.")

    repairs_train = [r for r in repairs_train_all if row_mode(r) == "dcl_repair"]
    repairs_eval = [r for r in repairs_eval_all if row_mode(r) == "dcl_repair"]
    retired_train = len(repairs_train_all) - len(repairs_train)
    retired_eval = len(repairs_eval_all) - len(repairs_eval)

    # ---- 2b. Assert expected counts (abort loudly on mismatch) -------------------------
    actual = {
        "authors_train": len(authors_train),
        "authors_eval": len(authors_eval),
        "repairs_train": len(repairs_train),
        "repairs_eval": len(repairs_eval),
    }
    mismatches = {k: (EXPECTED[k], actual[k]) for k in EXPECTED if EXPECTED[k] != actual[k]}
    if mismatches:
        lines = "\n".join(f"    {k}: expected {exp}, got {got}"
                          for k, (exp, got) in mismatches.items())
        sys.exit("ERROR: staged corpus count mismatch (source corpora changed?). Abort.\n"
                 + lines)

    train_kept = authors_train + repairs_train      # 451 unique
    eval_kept = authors_eval + repairs_eval          # 56 unique
    merged = train_kept + eval_kept                  # 507 unique

    # ---- 3. Verify every kept row -----------------------------------------------------
    verify_fails: list[str] = []
    for split, rows in (("train", train_kept), ("eval", eval_kept)):
        for r in rows:
            for f in verify_row(r, source=split, split=split):
                verify_fails.append(f"[{split} row_id={row_id(r)}] {f}")

    # row_id present + unique across the merged set.
    ids = [row_id(r) for r in merged]
    if any(i is None for i in ids):
        verify_fails.append("one or more kept rows missing metadata.row_id")
    dupes = [rid for rid, c in Counter(ids).items() if rid is not None and c > 1]
    if dupes:
        verify_fails.append(f"duplicate row_id across merged set: {dupes[:10]}"
                            + (" ..." if len(dupes) > 10 else ""))

    # ---- 3b. Strip think prefix from repair targets (live-catch 2026-07-19) ------------
    # Banked rows were just verified under the post-think law (step 3, on ORIGINAL
    # content). Staged targets drop the <think> block by default: think tokens are
    # near-untrained in the non-thinking base and training on them collapsed generation
    # onto <tool_call> spam in the first pilot run. Sources on disk are untouched.
    strip_think = not args.keep_think
    if strip_think and verify_fails:
        # Verification already failed on the banked rows — report through the normal gate
        # table (hard_ok=False, nothing written) instead of aborting mid-strip.
        pass
    elif strip_think:
        stripped_count = 0
        for r in repairs_train + repairs_eval:
            content = assistant_content(r)
            new = strip_think_prefix(content)
            if new != content:
                if not _DCL_FENCE_RE.search(new):
                    sys.exit(f"ERROR: strip-think left row {row_id(r)} without a ```dcl "
                             f"fence — refusing to stage a broken target.")
                r["messages"][-1]["content"] = new
                stripped_count += 1
        if stripped_count != len(repairs_train) + len(repairs_eval):
            sys.exit(f"ERROR: strip-think changed {stripped_count} repair rows, expected "
                     f"{len(repairs_train) + len(repairs_eval)} — a repair row lacked its "
                     f"<think> block. Investigate before staging.")

    # ---- 4. Template-token leak gate --------------------------------------------------
    leak_hits: list[dict] = []
    for split, rows in (("train", train_kept), ("eval", eval_kept)):
        for r in rows:
            for msg in r["messages"]:
                hits = find_leaks(msg.get("content", ""))
                if hits:
                    leak_hits.append({"split": split, "row_id": row_id(r),
                                      "role": msg.get("role"), "markers": hits})

    # ---- 5a. Train/eval contamination -------------------------------------------------
    contam = check_contamination(train_kept, eval_kept)

    # ---- 5b. Frozen-exam cross-check --------------------------------------------------
    briefs = load_exam_briefs(fleet_evals_dir)
    exam_check = frozen_exam_crosscheck(train_kept, briefs)

    # ---- think-block coverage by mode -------------------------------------------------
    think_cov = {"author": {"with_think": 0, "total": 0},
                 "repair": {"with_think": 0, "total": 0}}
    for r in merged:
        key = "repair" if row_mode(r) == "dcl_repair" else "author"
        think_cov[key]["total"] += 1
        if "<think>" in assistant_content(r):
            think_cov[key]["with_think"] += 1

    # ---- Hard-gate verdict ------------------------------------------------------------
    hard_ok = (
        not verify_fails
        and not leak_hits
        and contam.passed
        and exam_check["status"] == "pass"
    )

    # ---- 6. Oversample author train rows, deterministic shuffle -----------------------
    staged_train: list[dict] = []
    for r in authors_train:
        staged_train.extend([r] * args.author_reps)
    staged_train.extend(repairs_train)
    random.Random(args.seed).shuffle(staged_train)
    staged_eval = list(eval_kept)  # eval NEVER oversampled

    # ---- 7. Sequence-length audit (over what is actually written) ---------------------
    seq = seqlen_audit(staged_train + staged_eval, args.est_chars_per_token)

    # ---- 8. Write staged files + manifest (only if hard gates pass) -------------------
    train_path = out_dir / "train-dcl.jsonl"
    eval_path = out_dir / "eval-dcl.jsonl"
    manifest_path = out_dir / "dcl-staging-manifest.json"

    if hard_ok:
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(train_path, staged_train)
        _write_jsonl(eval_path, staged_eval)

        created = args.date or _max_mtime_date(
            [authors_dir / "train.jsonl", authors_dir / "eval_dcl.jsonl",
             repairs_dir / "train.jsonl", repairs_dir / "eval_dcl.jsonl"])
        manifest = {
            "manifest_version": 1,
            "dataset_id": "dcl-pilot-finetune-v1",
            "domain": "dcl-capability-language",
            "created": created,
            "base_model": "Qwen/Qwen3-4B-Instruct-2507",
            "chat_template": "qwen3-native (<|im_start|>role\\n...<|im_end|>)",
            "deviation_note": (
                "OUTPUT-CONTRACT.md names chat_template gemma-4; the base changed to "
                "Qwen3-4B-Instruct-2507 on 2026-07-19 probe evidence. Contract left unedited; "
                "template applied by the trainer, not this staging step."),
            "author_reps": args.author_reps,
            "author_reps_rationale": (
                "Ratified corpus target ratio ~1:2 (author:repair); authors under-delivered "
                "(87 of 200 briefs; 113 hard-brief rejections). Oversampling approximates the "
                "ratified mix. K configurable; K=1 disables oversampling."),
            "sources": {
                "authors": {
                    "dir": authors_dir.name,
                    "manifest_sha256": sha256_file(authors_dir / "manifest.json"),
                    "train_rows": len(authors_train),
                    "eval_rows": len(authors_eval),
                },
                "repairs": {
                    "dir": repairs_dir.name,
                    "manifest_sha256": sha256_file(repairs_dir / "manifest.json"),
                    "repair_train_rows": len(repairs_train),
                    "repair_eval_rows": len(repairs_eval),
                    "retired_author_rows": {"train": retired_train, "eval": retired_eval},
                },
            },
            "counts": {
                "unique": {
                    "train": len(train_kept),
                    "eval": len(eval_kept),
                    "total": len(merged),
                    "by_mode": {
                        "train": {"dcl_author": len(authors_train),
                                  "dcl_repair": len(repairs_train)},
                        "eval": {"dcl_author": len(authors_eval),
                                 "dcl_repair": len(repairs_eval)},
                    },
                },
                "staged": {
                    "train_rows_written": len(staged_train),
                    "eval_rows_written": len(staged_eval),
                    "author_copies_in_train": len(authors_train) * args.author_reps,
                    "repair_rows_in_train": len(repairs_train),
                    "author_repair_ratio_staged": (
                        f"1:{len(repairs_train) / (len(authors_train) * args.author_reps):.2f}"),
                },
            },
            "pilot_floor": {
                "unique_rows": len(merged),
                "floor": PILOT_ROW_FLOOR,
                "architect_min_accepted": ARCHITECT_MIN_ACCEPTED,
                "note": (f"{len(merged)} unique rows is BELOW the architect runbook's "
                         f"{ARCHITECT_MIN_ACCEPTED} MIN_ACCEPTED — deliberate, Rich-approved "
                         f"pilot floor. Recorded honestly, not hidden."),
            },
            "strip_think": {
                "enabled": strip_think,
                "rationale": (
                    "Live-catch 2026-07-19 (first pilot run): <think>/</think> are "
                    "near-untrained added tokens in the non-thinking Qwen3-4B-Instruct-2507 "
                    "base; LoRA leaves lm_head frozen, so targets on them collapsed onto the "
                    "confusable <tool_call> row at generation (deterministic spam). The stock "
                    "base holds repair 3/3 WITHOUT emitting think, so think-free targets are "
                    "serve-faithful. Banked rows verified under the post-think law BEFORE "
                    "stripping; sources untouched."),
            },
            "think_coverage_by_mode": think_cov,
            "staged_files": {
                "train": {"path": str(train_path),
                          "rows": len(staged_train),
                          "sha256": sha256_file(train_path)},
                "eval": {"path": str(eval_path),
                         "rows": len(staged_eval),
                         "sha256": sha256_file(eval_path)},
            },
            "contamination": {
                "train_eval": contam.to_dict(),
                "frozen_exam_crosscheck": exam_check,
            },
            "seq_audit": seq,
            "leak_gate": {"markers_screened": list(LEAK_MARKERS), "hits": leak_hits},
            "shuffle_seed": args.seed,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")

    # ---- 9. PHASE-0 GATES table -------------------------------------------------------
    _print_gates(
        merged=merged, train_kept=train_kept, eval_kept=eval_kept,
        authors_train=authors_train, authors_eval=authors_eval,
        repairs_train=repairs_train, repairs_eval=repairs_eval,
        retired_train=retired_train, retired_eval=retired_eval,
        verify_fails=verify_fails, leak_hits=leak_hits, contam=contam,
        exam_check=exam_check, think_cov=think_cov, seq=seq,
        author_reps=args.author_reps, staged_train=staged_train, staged_eval=staged_eval,
        hard_ok=hard_ok, train_path=train_path, eval_path=eval_path,
        manifest_path=manifest_path, briefs=briefs, keep_think=args.keep_think,
    )

    return 0 if hard_ok else 1


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _max_mtime_date(paths: list[Path]) -> str:
    mt = max(p.stat().st_mtime for p in paths if p.exists())
    return datetime.datetime.fromtimestamp(mt).strftime("%Y-%m-%d")


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _print_gates(*, merged, train_kept, eval_kept, authors_train, authors_eval,
                 repairs_train, repairs_eval, retired_train, retired_eval,
                 verify_fails, leak_hits, contam, exam_check, think_cov, seq,
                 author_reps, staged_train, staged_eval, hard_ok,
                 train_path, eval_path, manifest_path, briefs, keep_think=False):
    bar = "=" * 72
    print(f"\n{bar}")
    print("DCL PILOT FINE-TUNE — PHASE-0 STAGING GATES")
    print("(adapted from RUNBOOK-architect-fine-tune.md §0, honestly for a 507-row pilot)")
    print(bar)

    # Row counts vs floor
    print(f"\n[rows] unique kept: train={len(train_kept)} + eval={len(eval_kept)} "
          f"= {len(merged)}")
    print(f"       authors: train={len(authors_train)} eval={len(authors_eval)}   "
          f"repairs: train={len(repairs_train)} eval={len(repairs_eval)} "
          f"(retired authors dropped from repairs set: train={retired_train} eval={retired_eval})")
    print(f"       PILOT FLOOR {len(merged)} rows — BELOW architect MIN_ACCEPTED "
          f"{ARCHITECT_MIN_ACCEPTED} (deliberate, Rich-approved pilot; recorded not hidden) "
          f"[RECORD]")

    # Gate table
    print(f"\n{'GATE':<34}{'STATUS':<8}DETAIL")
    print("-" * 72)
    counts_ok = (len(authors_train) == EXPECTED["authors_train"]
                 and len(authors_eval) == EXPECTED["authors_eval"]
                 and len(repairs_train) == EXPECTED["repairs_train"]
                 and len(repairs_eval) == EXPECTED["repairs_eval"])
    print(f"{'count assertions':<34}{_status(counts_ok):<8}"
          f"77/10 authors, 374/46 repairs")
    print(f"{'row verification':<34}{_status(not verify_fails):<8}"
          f"{len(merged) - len({f.split(']')[0] for f in verify_fails})}/{len(merged)} clean "
          f"(compile_verified, roles, post-think ```dcl fence, unique row_id)"
          if not verify_fails else
          f"{'row verification':<0}{len(verify_fails)} failure(s)")
    print(f"{'template-token leak gate':<34}{_status(not leak_hits):<8}"
          f"{len(leak_hits)} hit(s) (must be 0) — screened {len(LEAK_MARKERS)} markers")
    print(f"{'contamination (train/eval)':<34}{_status(contam.passed):<8}"
          f"verdict={contam.status}; row_id ∩ = {len(contam.intersection)}; "
          f"denylist violations = {len(contam.denylist_violations)}")
    print(f"{'frozen-exam cross-check':<34}{_status(exam_check['status'] == 'pass'):<8}"
          f"verdict={exam_check['status']}; "
          f"{exam_check['train_rows_compared']} train rows vs "
          f"{exam_check['exam_shingles_total']} {SHINGLE_N}-gram shingles from "
          f"{len(briefs)} exams {exam_check['exams_compared']}; hits={len(exam_check['hits'])}")

    # think coverage (record, not a gate). With strip-think (default) staged targets must
    # be think-free; with --keep-think repairs carry their banked <think> block.
    a, rp = think_cov["author"], think_cov["repair"]
    a_pct = 100 * a["with_think"] / max(a["total"], 1)
    r_pct = 100 * rp["with_think"] / max(rp["total"], 1)
    r_expect = "~100%" if keep_think else "0% (stripped — live-catch 2026-07-19)"
    print(f"{'think coverage by mode':<34}{'RECORD':<8}"
          f"authors {a['with_think']}/{a['total']} ({a_pct:.0f}%, expect 0%); "
          f"repairs {rp['with_think']}/{rp['total']} ({r_pct:.0f}%, expect {r_expect})")

    # seq recommendation
    ex = seq["exceed"]
    print(f"{'seq-length audit (est)':<34}{'RECORD':<8}"
          f"p50={seq['p50']} p95={seq['p95']} p99={seq['p99']} max={seq['max']} tok "
          f"@ {seq['est_chars_per_token']} ch/tok")
    print(f"{'':<34}{'':<8}"
          f"exceed: " + "  ".join(f"{k}={ex[k]['rows']}({ex[k]['pct']}%)" for k in ex))
    print(f"{'':<34}{'':<8}RECOMMEND --max-seq-length "
          f"{seq['recommended_max_seq_length']} (smallest bucket with ~0% truncation)")

    # Oversampling
    ratio = f"1:{len(repairs_train) / (len(authors_train) * author_reps):.2f}"
    print(f"{'author oversampling':<34}{'RECORD':<8}"
          f"K={author_reps} -> {len(authors_train) * author_reps} author copies : "
          f"{len(repairs_train)} repairs = {ratio}")

    if verify_fails:
        print("\n  VERIFY FAILURES:")
        for f in verify_fails[:20]:
            print(f"    - {f}")
    if leak_hits:
        print("\n  LEAK HITS:")
        for h in leak_hits[:20]:
            print(f"    - {h}")
    if exam_check["hits"]:
        print("\n  FROZEN-EXAM OVERLAPS:")
        for h in exam_check["hits"][:20]:
            print(f"    - {h}")

    print(f"\n{bar}")
    if hard_ok:
        print(f"PHASE-0 VERDICT: PASS (exit 0) — all hard gates green.")
        print(f"  staged train : {train_path}  ({len(staged_train)} rows)")
        print(f"  staged eval  : {eval_path}  ({len(staged_eval)} rows)")
        print(f"  manifest     : {manifest_path}")
    else:
        print(f"PHASE-0 VERDICT: FAIL (exit 1) — hard gate(s) red; nothing written.")
    print(f"{bar}\n")


if __name__ == "__main__":
    sys.exit(main())
