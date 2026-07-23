#!/usr/bin/env python3
"""
prepare_qav_sft.py — Stage the QAV pilot fine-tune corpus (the 108-corpus)
==========================================================================
Assembles the QA-verifier SFT training/eval sets for the **pilot probe fine-tune**
(Rich ruled Option A on plateau card #2, 2026-07-22: the pilot tune fires on the
108-corpus) from the factory's already-split banked corpus and writes them, plus a
staging manifest, OUTSIDE the repo under ``~/fine-tuning/data/`` (nothing under
``~/fine-tuning`` is ever committed; the corpus is private under DF-008 and NEVER
committed — this script emits only SHAs and counts into any committed surface).

Sources (READ-ONLY — never modified):

  ``output/qa-verifier/train.jsonl``      = the 86 TRAIN rows (split already applied)
  ``output/qa-verifier/eval_qav.jsonl``   = the 22 held-out EVAL rows (loss-only; NEVER
                                            oversampled; contamination-checked against train)

108 unique rows total (86 train + 22 eval). This is a **deliberate pilot PROBE floor** —
far below any production adoption bar (FEAT-EVAL-QAV is the deploy gate, not this run) — and
is recorded honestly in the manifest, not hidden. The corpus is balanced AT GENERATION
(SCOPE §3 delta 2: no prepare-time oversampling), so this step CONVERTS and AUDITS; it does
NOT weight or rebalance.

Row envelope on disk (OUTPUT-CONTRACT.md §1), verified as-is:
  {"messages": [system, user, assistant], "metadata": {row_id, split, dc_class,
   generation_mode, injection_recipe, provenance, reconstruction_fidelity,
   bundle_schema_sha}}
  assistant content = "<think>…reasoning…</think>\\n\\n```json\\n<verdict trio>\\n```"
  verdict trio = {"verdict","findings":[{"class","locus"}],"ground_truth_source"} (§3).

STAGING TRANSFORMS (the three DCL-tune catches applied to QAV — see RUNBOOK-qav-fine-tune.md):
  * strip-think (DEFAULT): drop the leading <think>…</think> block from the STAGED target.
  * strip-fence (DEFAULT): unwrap the ```json fence to a BARE verdict JSON object.
  Both default because the **serving contract** (fleet-evals/harness/run_qav_heldout.py) pins
  the system prompt "output ONLY the verdict JSON object — no prose, no explanation, no
  markdown fences" and extracts the verdict via a ```json fence OR the first balanced {...}
  object. The robust extractor path is the balanced-object scanner (the fence regex's
  non-greedy ``\\{.*?\\}`` breaks on the nested findings object), so a BARE JSON verdict
  object with no think prose and no fence is exactly what the served model is asked to emit —
  DCL law #3: staged targets must byte-match the serving contract. Banked rows keep their
  think+fence on disk (verified BEFORE stripping); sources are never modified.
  ``--keep-think`` / ``--keep-fence`` restore the banked shape (ablation levers).

  CHAT-TEMPLATE / BASE (recorded; OUTPUT-CONTRACT.md line honored): base = the coach-ft
  lineage ``unsloth/gemma-4-26B-A4B-it`` (D9 different-family; GOAL.md §"Fine-tune target"),
  chat template ``gemma-4`` (NOT ``gemma-4-thinking`` — the tutor template-leak lesson). This
  staging step is template-agnostic (it writes ShareGPT ``messages``); the template is applied
  by the trainer. The leak gate screens gemma control tokens (belt-and-suspenders + qwen).

Usage:
    python3 prepare_qav_sft.py                    # defaults; writes to ~/fine-tuning/data/
    python3 prepare_qav_sft.py --keep-think       # ablation: keep the teacher reasoning block
    python3 prepare_qav_sft.py --date 2026-07-23  # pin the manifest created date

Host-runnable: stdlib only. No heavy ML deps (the trainer imports those).
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
# Paths — resolved relative to the repo root (this file: domains/<domain>/prepare_qav_sft.py)
# --------------------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TRAIN_SRC = REPO_ROOT / "output" / "qa-verifier" / "train.jsonl"
DEFAULT_EVAL_SRC = REPO_ROOT / "output" / "qa-verifier" / "eval_qav.jsonl"
DEFAULT_MANIFEST_SRC = REPO_ROOT / "output" / "qa-verifier" / "manifest.json"

# Frozen-exam tasks (READ-ONLY): the qav-held exams are the deploy gate and are NEVER trained.
DEFAULT_FLEET_EVALS_DIR = REPO_ROOT.parent / "fleet-evals"

# Staged output goes OUTSIDE the repo (never committed).
DEFAULT_OUT_DIR = Path(os.path.expanduser("~/fine-tuning/data"))

BASE_MODEL = "unsloth/gemma-4-26B-A4B-it"   # coach-ft lineage; D9 different-family (GOAL.md)
CHAT_TEMPLATE = "gemma-4"                    # NON-thinking (tutor template-leak lesson)

# Phase-1 admissible defect classes (OUTPUT-CONTRACT §3 / GOAL.md generation guidelines).
ADMISSIBLE_DC = ("DC-03", "DC-05", "DC-08", "DC-12", "DC-14")
# ground_truth_source enum (scope §5, verbatim).
GROUND_TRUTH_SOURCES = ("coach_correct", "operator_caught", "merge_review_caught",
                        "live_gate_caught", "seeded")

# Chat-template control tokens that must NEVER appear inside message content. Any hit teaches
# the model to emit template framing -> fatal. gemma-4 markers + qwen kept as belt-and-braces.
LEAK_MARKERS = (
    "<|turn>", "<turn|>",                   # gemma-4 turn markers (the train-time template)
    "<|channel>", "<channel|>",             # gemma/harmony channel markers
    "<start_of_turn>", "<end_of_turn>",     # gemma start/end-of-turn
    "<|im_start|>", "<|im_end|>",           # qwen (belt-and-braces)
)

# Frozen-exam cross-check: distinctive shingle width (consecutive normalized words).
SHINGLE_N = 8

EXPECTED_ROLES = ("system", "user", "assistant")
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.S)
_THINK_BLOCK_RE = re.compile(r"^\s*<think>.*?</think>\s*", re.S | re.I)
_THINK_END_RE = re.compile(r"</think>", re.I)
_NORM_RE = re.compile(r"[^a-z0-9]+")


def strip_think_prefix(content: str) -> str:
    """Remove the leading <think>...</think> block from a target (DCL catch #2 kin). The
    verdict trio sits in the fence AFTER </think>, so stripping keeps exactly the label."""
    return _THINK_BLOCK_RE.sub("", content, count=1)


def _post_think_fence(content: str):
    """Locate the ```json verdict fence that sits AFTER </think> (the POST-THINK LAW). A fence
    inside <think> quotes EVIDENCE (broken code, a partial), not the verdict — matching it would
    grade the wrong object. Returns (start, end, inner_bare) or None."""
    ends = list(_THINK_END_RE.finditer(content))
    start_from = ends[-1].end() if ends else 0
    m = _JSON_FENCE_RE.search(content, start_from)
    if not m:
        return None
    return m.start(), m.end(), m.group(1).strip("\n")


def unwrap_json_fence(content: str) -> str | None:
    """Unwrap the POST-THINK ```json verdict fence to the BARE JSON object text (DCL catch #3).
    Returns the inner object text (stripped), or None if no post-think fence is present."""
    found = _post_think_fence(content)
    return found[2] if found else None


def extract_label(content: str) -> dict | None:
    """Parse the verdict object out of a banked assistant turn (its ```json fence). Used by
    verification on the ORIGINAL row. Returns the parsed dict, or None if unparseable."""
    inner = unwrap_json_fence(content)
    if inner is None:
        return None
    try:
        obj = json.loads(inner)
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Stage the QAV pilot fine-tune corpus (the 108-corpus) -> "
                    "~/fine-tuning/data/ + a staging manifest. READ-ONLY on all sources; "
                    "never writes into the repo. Targets byte-match the qav-heldout serving "
                    "contract (bare verdict JSON, no think, no fence).")
    p.add_argument("--train-src", default=str(DEFAULT_TRAIN_SRC),
                   help="Banked train.jsonl (the 86 train rows)")
    p.add_argument("--eval-src", default=str(DEFAULT_EVAL_SRC),
                   help="Banked eval_qav.jsonl (the 22 held-out eval rows; loss-only)")
    p.add_argument("--manifest-src", default=str(DEFAULT_MANIFEST_SRC),
                   help="Corpus manifest.json (class-balance tripwire cross-checks its counts "
                        "block; skipped with a RECORD note if absent)")
    p.add_argument("--fleet-evals-dir", default=str(DEFAULT_FLEET_EVALS_DIR),
                   help="fleet-evals repo (READ-ONLY) — source of the frozen qav-held exams")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR),
                   help="Staged output dir (OUTSIDE the repo; never committed)")
    p.add_argument("--seed", type=int, default=3407,
                   help="Deterministic shuffle seed for the staged train order")
    p.add_argument("--est-chars-per-token", type=float, default=3.5,
                   help="Char->token ratio for the seq-length audit (ESTIMATE; the "
                        "in-container real-tokenizer audit is ground truth — coach measured "
                        "3.50 for the gemma-4 tokenizer)")
    p.add_argument("--date", default=None,
                   help="Manifest created date (YYYY-MM-DD). Default: max source-file mtime.")
    p.add_argument("--keep-think", action="store_true",
                   help="Keep the leading <think>...</think> block in the STAGED target. "
                        "DEFAULT IS TO STRIP IT (the qav-heldout serving prompt demands 'ONLY "
                        "the verdict JSON object — no prose'; a trained-in think block also "
                        "risks the max_tokens=2048 ceiling truncating the END-positioned "
                        "verdict — the SCOPE §3 truncation-eats-the-label lesson). Banked rows "
                        "keep their think blocks on disk.")
    p.add_argument("--keep-fence", action="store_true",
                   help="Keep the ```json markdown fence around the STAGED target. DEFAULT IS "
                        "TO UNWRAP to a bare JSON object (the serving prompt bans markdown "
                        "fences; the extractor's robust path is the balanced-object scanner). "
                        "Banked rows keep their fences on disk.")
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
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------------------
# Row helpers
# --------------------------------------------------------------------------------------
def row_id(row: dict) -> str | None:
    return row.get("metadata", {}).get("row_id")


def assistant_content(row: dict) -> str:
    return row["messages"][-1]["content"]


def user_content(row: dict) -> str:
    return row["messages"][1]["content"]


def find_leaks(text: str) -> list[str]:
    return [m for m in LEAK_MARKERS if m in text]


def normalize_words(text: str) -> list[str]:
    return [w for w in _NORM_RE.sub(" ", text.lower()).split() if w]


def shingles(text: str, n: int = SHINGLE_N) -> set[str]:
    words = normalize_words(text)
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


# --------------------------------------------------------------------------------------
# Verification of a kept row (runs on the ORIGINAL banked row, pre-transform)
# --------------------------------------------------------------------------------------
def verify_row(row: dict, *, split: str) -> list[str]:
    """Return a list of verification failures for a single row (empty = clean). Checks the
    envelope, the label contract (OUTPUT-CONTRACT §3), and the row-shape the transforms need."""
    fails: list[str] = []
    meta = row.get("metadata", {})
    if not meta.get("row_id"):
        fails.append("metadata.row_id missing")
    msgs = row.get("messages", [])
    roles = tuple(m.get("role") for m in msgs)
    if roles != EXPECTED_ROLES:
        fails.append(f"message roles {roles} != {EXPECTED_ROLES}")
        return fails  # downstream checks assume the [system,user,assistant] shape
    content = assistant_content(row)
    if "<think>" not in content or "</think>" not in content:
        fails.append("assistant turn missing <think>…</think> block (OUTPUT-CONTRACT §1)")
    label = extract_label(content)
    if label is None:
        fails.append("assistant turn has no parseable ```json verdict object")
        return fails
    verdict = label.get("verdict")
    if verdict not in ("approve", "reject"):
        fails.append(f"verdict {verdict!r} not in approve|reject")
    findings = label.get("findings")
    if not isinstance(findings, list):
        fails.append("findings is not a list")
        findings = []
    if verdict == "approve" and findings:
        fails.append("approve verdict must carry findings: [] (OUTPUT-CONTRACT §3)")
    if verdict == "reject" and not findings:
        fails.append("reject verdict must carry >=1 finding (OUTPUT-CONTRACT §3)")
    for f in findings:
        if not isinstance(f, dict):
            fails.append("finding is not an object")
            continue
        if f.get("class") not in ADMISSIBLE_DC:
            fails.append(f"finding class {f.get('class')!r} not in admissible {ADMISSIBLE_DC}")
        if not str(f.get("locus", "")).strip():
            fails.append("finding locus is empty (a blanket rejection earns nothing)")
    gts = label.get("ground_truth_source")
    if gts is not None and gts not in GROUND_TRUTH_SOURCES:
        fails.append(f"ground_truth_source {gts!r} not in {GROUND_TRUTH_SOURCES}")
    return fails


def row_verdict(row: dict) -> str | None:
    label = extract_label(assistant_content(row))
    return label.get("verdict") if label else None


# --------------------------------------------------------------------------------------
# Sequence-length audit (char-based ESTIMATE)
# --------------------------------------------------------------------------------------
def seqlen_audit(rows: list[dict], cpt: float) -> dict:
    """Estimate per-row token length and report truncation rates at candidate max_seq_length
    buckets. QAV rows are the LONGEST in the fleet (the user message is a full serialized
    bundle and the verdict sits at the END), so this audit is the critical Phase-0 gate — the
    in-container real-tokenizer audit is ground truth. cpt=3.5 is the coach-measured estimate."""
    TEMPLATE_OVERHEAD = 16
    buckets = (4096, 6144, 8192, 12288)
    lens = sorted(
        sum(len(m["content"]) for m in r["messages"]) / cpt + TEMPLATE_OVERHEAD
        for r in rows
    )
    n = len(lens)

    def pctile(q):
        return lens[min(n - 1, int(q * n))]

    exceed = {thr: sum(1 for x in lens if x > thr) for thr in buckets}
    recommended = buckets[-1]
    for thr in buckets:
        if 100 * exceed[thr] / max(n, 1) < 0.5:
            recommended = thr
            break
    return {
        "est_chars_per_token": cpt,
        "n": n,
        "p50": round(pctile(0.50)),
        "p95": round(pctile(0.95)),
        "p99": round(pctile(0.99)),
        "max": round(lens[-1]) if lens else 0,
        "exceed": {str(thr): {"rows": exceed[thr], "pct": round(100 * exceed[thr] / max(n, 1), 2)}
                   for thr in buckets},
        "recommended_max_seq_length": recommended,
    }


# --------------------------------------------------------------------------------------
# Contamination + frozen-exam cross-check (READ-ONLY over fleet-evals)
# --------------------------------------------------------------------------------------
def train_eval_intersection(train_rows: list[dict], eval_rows: list[dict]) -> dict:
    tids = {row_id(r) for r in train_rows}
    eids = {row_id(r) for r in eval_rows}
    inter = sorted(x for x in (tids & eids) if x is not None)
    return {"status": "pass" if not inter else "fail", "intersection": len(inter),
            "intersection_row_ids": inter[:20]}


def load_exam_bundle_text(fleet_evals_dir: Path) -> dict[str, str]:
    """Read each qav-held-* exam's bundle bodies (the held-out gold-negative + honest-green
    evidence bundles). Returns {task_name: concatenated bundle text}."""
    briefs: dict[str, str] = {}
    tasks_dir = fleet_evals_dir / "tasks"
    if not tasks_dir.is_dir():
        return briefs
    for task_dir in sorted(tasks_dir.glob("qav-held-*")):
        bundles_root = task_dir / "input" / "bundles"
        if not bundles_root.is_dir():
            continue
        parts: list[str] = []
        for bdir in sorted(p for p in bundles_root.iterdir() if p.is_dir()):
            bp = bdir / "bundle.json"
            if bp.is_file():
                parts.append(bp.read_text(encoding="utf-8"))
        if parts:
            briefs[task_dir.name] = "\n".join(parts)
    return briefs


def frozen_exam_crosscheck(train_rows: list[dict], briefs: dict[str, str]) -> dict:
    """Assert no staged TRAIN row's user content reproduces any held-out exam bundle's
    distinctive text (normalized 8-gram shingle overlap). The gold negatives (GN-1..GN-4) and
    honest-green exam bundles are the deploy gate — a train row that reproduces one contaminates
    the A/B. Belt-and-braces over the factory's own contamination_check (SCOPE §3.1 delta 1d)."""
    exam_shingles = {name: shingles(body) for name, body in briefs.items()}
    total = sum(len(s) for s in exam_shingles.values())
    hits: list[dict] = []
    for row in train_rows:
        user_text = " ".join(normalize_words(user_content(row)))
        for name, sh in exam_shingles.items():
            for shard in sh:
                if shard in user_text:
                    hits.append({"row_id": row_id(row), "exam": name, "shingle": shard})
                    break
    return {
        "status": "pass" if not hits else "fail",
        "method": f"normalized {SHINGLE_N}-gram shingle substring overlap, exam bundle body vs "
                  f"train row user content",
        "exams_compared": sorted(exam_shingles),
        "exam_shingles_total": total,
        "train_rows_compared": len(train_rows),
        "hits": hits[:20],
    }


# --------------------------------------------------------------------------------------
# Class-balance tripwire (SCOPE §3 delta 4)
# --------------------------------------------------------------------------------------
def count_by_verdict(rows: list[dict]) -> dict:
    return dict(Counter(row_verdict(r) for r in rows))


def count_by_dc_class(rows: list[dict]) -> dict:
    c: Counter = Counter()
    for r in rows:
        label = extract_label(assistant_content(r))
        for f in (label or {}).get("findings", []) or []:
            if isinstance(f, dict) and f.get("class"):
                c[f["class"]] += 1
    return dict(c)


def balance_tripwire(train_rows: list[dict], manifest_src: Path) -> dict:
    """Cross-check staged TRAIN counts against the corpus manifest's counts block; a mismatch
    aborts (the coach-v2 81/19 -> 87.5% false-approval saga is why this is a hard gate, not an
    eyeball). Skipped-with-RECORD if the manifest is absent."""
    staged = {"by_verdict": count_by_verdict(train_rows),
              "by_dc_class": count_by_dc_class(train_rows)}
    if not manifest_src.is_file():
        return {"status": "record", "note": f"no corpus manifest at {manifest_src} — "
                "counts recorded, not cross-checked", "staged": staged}
    try:
        man = json.loads(manifest_src.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"status": "record", "note": f"corpus manifest unreadable ({e}) — recorded only",
                "staged": staged}
    man_counts = man.get("counts", {})
    mismatches: list[str] = []
    for key, sub in (("by_verdict", staged["by_verdict"]), ("by_dc_class", staged["by_dc_class"])):
        want = {k: v for k, v in (man_counts.get(key, {}) or {}).items() if v}
        got = {k: v for k, v in sub.items() if k is not None and v}
        if want != got:
            mismatches.append(f"{key}: manifest={want} staged={got}")
    return {"status": "pass" if not mismatches else "fail", "staged": staged,
            "manifest_counts": {"by_verdict": man_counts.get("by_verdict"),
                                "by_dc_class": man_counts.get("by_dc_class")},
            "mismatches": mismatches}


# --------------------------------------------------------------------------------------
# Target transform (the three catches)
# --------------------------------------------------------------------------------------
def stage_target(content: str, *, strip_think: bool, strip_fence: bool) -> str:
    """Transform a banked assistant turn into the STAGED target.

    Default (strip_think + strip_fence): bare verdict JSON object — byte-matches the
    qav-heldout serving contract ('ONLY the verdict JSON object — no prose, no fences'). The
    verdict fence is located under the POST-THINK LAW (a fence inside <think> quotes evidence,
    never the verdict). With --keep-think the think block is preserved and only its post-think
    fence is unwrapped. Raises ValueError if strip_fence is requested but no post-think fence is
    present, or the unwrapped body is not parseable JSON (refuse to stage a broken target)."""
    body = content
    if strip_think:
        body = strip_think_prefix(body)
    if strip_fence:
        found = _post_think_fence(body)
        if found is None:
            raise ValueError("no post-think ```json fence to unwrap (row contract requires one)")
        start, end, inner = found
        if "```" in inner:
            raise ValueError("unwrap left backticks in the verdict target")
        try:
            json.loads(inner)
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"unwrapped target is not valid JSON: {e}")
        body = (body[:start] + inner + body[end:]).strip("\n") if not strip_think else inner
    return body


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
def main(argv=None) -> int:
    args = parse_args(argv)

    train_src = Path(args.train_src)
    eval_src = Path(args.eval_src)
    manifest_src = Path(args.manifest_src)
    fleet_evals_dir = Path(args.fleet_evals_dir)
    out_dir = Path(os.path.expanduser(args.out_dir))

    for f in (train_src, eval_src):
        if not f.is_file():
            sys.exit(f"ERROR: expected source file not found: {f}")

    # ---- 1. Load ----------------------------------------------------------------------
    train_rows = load_jsonl(train_src)
    eval_rows = load_jsonl(eval_src)
    merged = train_rows + eval_rows

    # ---- 2. Verify every row (on the ORIGINAL banked shape) ----------------------------
    verify_fails: list[str] = []
    for split, rows in (("train", train_rows), ("eval", eval_rows)):
        for r in rows:
            for f in verify_row(r, split=split):
                verify_fails.append(f"[{split} row_id={row_id(r)}] {f}")
    ids = [row_id(r) for r in merged]
    dupes = [rid for rid, c in Counter(ids).items() if rid is not None and c > 1]
    if any(i is None for i in ids):
        verify_fails.append("one or more rows missing metadata.row_id")
    if dupes:
        verify_fails.append(f"duplicate row_id across corpus: {dupes[:10]}"
                            + (" ..." if len(dupes) > 10 else ""))

    # ---- 3. Template-token leak gate --------------------------------------------------
    leak_hits: list[dict] = []
    for split, rows in (("train", train_rows), ("eval", eval_rows)):
        for r in rows:
            for msg in r["messages"]:
                for mk in find_leaks(msg.get("content", "")):
                    leak_hits.append({"split": split, "row_id": row_id(r),
                                      "role": msg.get("role"), "marker": mk})

    # ---- 4. Contamination (train/eval) + frozen-exam cross-check ------------------------
    contam = train_eval_intersection(train_rows, eval_rows)
    briefs = load_exam_bundle_text(fleet_evals_dir)
    exam_check = frozen_exam_crosscheck(train_rows, briefs)

    # ---- 5. Class-balance tripwire (SCOPE §3 delta 4) ----------------------------------
    balance = balance_tripwire(train_rows, manifest_src)

    # ---- Hard-gate verdict ------------------------------------------------------------
    hard_ok = (
        not verify_fails
        and not leak_hits
        and contam["status"] == "pass"
        and exam_check["status"] == "pass"
        and balance["status"] != "fail"
    )

    # ---- 6. Stage targets (the three catches) -----------------------------------------
    strip_think = not args.keep_think
    strip_fence = not args.keep_fence
    staged_train: list[dict] = []
    staged_eval: list[dict] = []
    if hard_ok:
        try:
            for src_rows, dst in ((train_rows, staged_train), (eval_rows, staged_eval)):
                for r in src_rows:
                    new = json.loads(json.dumps(r))  # deep copy — never mutate the source obj
                    new["messages"][-1]["content"] = stage_target(
                        assistant_content(r), strip_think=strip_think, strip_fence=strip_fence)
                    dst.append(new)
        except ValueError as e:
            sys.exit(f"ERROR: target staging failed — {e}. Refusing to stage a broken target.")
        random.Random(args.seed).shuffle(staged_train)  # eval NEVER shuffled/oversampled

    # ---- 7. Sequence-length audit (over what is actually written) ---------------------
    seq = seqlen_audit((staged_train + staged_eval) if hard_ok else merged,
                       args.est_chars_per_token)

    # ---- 8. Write staged files + manifest (only if hard gates pass) -------------------
    train_path = out_dir / "train-qav.jsonl"
    eval_path = out_dir / "eval-qav.jsonl"
    manifest_path = out_dir / "qav-staging-manifest.json"

    if hard_ok:
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(train_path, staged_train)
        _write_jsonl(eval_path, staged_eval)

        created = args.date or _max_mtime_date([train_src, eval_src])
        manifest = {
            "manifest_version": 1,
            "dataset_id": "qav-pilot-finetune-v1",
            "domain": "qa-verifier",
            "created": created,
            "base_model": BASE_MODEL,
            "base_model_note": (
                "coach-ft lineage; D9 different-family (the judged Player is gpt-oss/frontier "
                "Claude, the judge is gemma). 26B-A4B MoE => 16-bit LoRA, not 4-bit QLoRA "
                "(the coach finding: MoE QLoRA is blocked by 3D fused expert tensors)."),
            "chat_template": CHAT_TEMPLATE,
            "chat_template_note": (
                "gemma-4 (NON-thinking), NOT gemma-4-thinking (the tutor template-leak lesson). "
                "Applied by the trainer via get_chat_template; the trainer's catch-1 guard bans "
                "the thinking variant and the export->serve round-trip verifies train==serve."),
            "pilot_floor": {
                "unique_rows": len(merged),
                "train": len(train_rows),
                "eval": len(eval_rows),
                "note": (f"{len(merged)} unique rows (86 train + 22 eval) is a deliberate PILOT "
                         f"PROBE floor — far below any production adoption bar. FEAT-EVAL-QAV is "
                         f"the deploy gate, NOT this run (probe, not adoption). Recorded, not "
                         f"hidden."),
            },
            "no_oversampling_note": (
                "SCOPE §3 delta 2: NO prepare-time oversampling — QAV balance is enforced at "
                "generation by the manifest bands. This step converts + audits; it never "
                "weights."),
            "strip_think": {
                "enabled": strip_think,
                "rationale": (
                    "DCL catch #2/#3 kin: the qav-heldout serving prompt "
                    "(fleet-evals/harness/run_qav_heldout.py) demands 'ONLY the verdict JSON "
                    "object — no prose, no explanation, no markdown fences'; a trained-in "
                    "<think> block would emit reasoning prose the contract bans AND risk the "
                    "runner's max_tokens=2048 truncating the END-positioned verdict. Banked "
                    "rows keep <think> on disk; verification runs pre-strip."),
            },
            "strip_fence": {
                "enabled": strip_fence,
                "rationale": (
                    "DCL catch #3: staged targets must byte-match the serving contract. The "
                    "qav-heldout extractor takes a ```json fence OR the first balanced {...} "
                    "object; the robust path is the balanced-object scanner (the fence regex's "
                    "non-greedy \\{.*?\\} breaks on the nested findings object). A BARE verdict "
                    "JSON object is exactly what the served model is asked to emit. Banked rows "
                    "keep their fences on disk."),
            },
            "target_format": (
                "bare verdict JSON object: {\"verdict\":..,\"findings\":[{\"class\",\"locus\"}],"
                "\"ground_truth_source\":..} — no <think>, no ```json fence (default staging)."),
            "counts": {
                "unique": {"train": len(train_rows), "eval": len(eval_rows), "total": len(merged)},
                "by_verdict": {"train": count_by_verdict(train_rows),
                               "eval": count_by_verdict(eval_rows)},
                "by_dc_class": {"train": count_by_dc_class(train_rows),
                                "eval": count_by_dc_class(eval_rows)},
                "staged": {"train_rows_written": len(staged_train),
                           "eval_rows_written": len(staged_eval)},
            },
            "source_shas": {
                "train_src": {"path": str(train_src), "rows": len(train_rows),
                              "sha256": sha256_file(train_src)},
                "eval_src": {"path": str(eval_src), "rows": len(eval_rows),
                             "sha256": sha256_file(eval_src)},
                "manifest_src": ({"path": str(manifest_src), "sha256": sha256_file(manifest_src)}
                                 if manifest_src.is_file() else None),
            },
            "staged_files": {
                "train": {"path": str(train_path), "rows": len(staged_train),
                          "sha256": sha256_file(train_path)},
                "eval": {"path": str(eval_path), "rows": len(staged_eval),
                         "sha256": sha256_file(eval_path)},
            },
            "contamination": {"train_eval": contam, "frozen_exam_crosscheck": exam_check},
            "balance_tripwire": balance,
            "seq_audit": seq,
            "leak_gate": {"markers_screened": list(LEAK_MARKERS), "hits": leak_hits},
            "shuffle_seed": args.seed,
            "visibility": "private (DF-008)",
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")

    # ---- 9. PHASE-0 GATES table -------------------------------------------------------
    _print_gates(merged=merged, train_rows=train_rows, eval_rows=eval_rows,
                 verify_fails=verify_fails, leak_hits=leak_hits, contam=contam,
                 exam_check=exam_check, balance=balance, seq=seq, briefs=briefs,
                 hard_ok=hard_ok, strip_think=strip_think, strip_fence=strip_fence,
                 staged_train=staged_train, staged_eval=staged_eval,
                 train_path=train_path, eval_path=eval_path, manifest_path=manifest_path)

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


def _print_gates(*, merged, train_rows, eval_rows, verify_fails, leak_hits, contam, exam_check,
                 balance, seq, briefs, hard_ok, strip_think, strip_fence,
                 staged_train, staged_eval, train_path, eval_path, manifest_path):
    bar = "=" * 72
    print(f"\n{bar}\nQAV PILOT FINE-TUNE — PHASE-0 STAGING GATES (the 108-corpus)")
    print("(probe, not adoption — FEAT-EVAL-QAV is the deploy gate, not this run)")
    print(bar)
    print(f"\n[rows] unique: train={len(train_rows)} + eval={len(eval_rows)} = {len(merged)}   "
          f"PILOT PROBE FLOOR (recorded, not hidden) [RECORD]")

    print(f"\n{'GATE':<32}{'STATUS':<8}DETAIL")
    print("-" * 72)
    print(f"{'row verification':<32}{_status(not verify_fails):<8}"
          f"{len(merged) - len({f.split(']')[0] for f in verify_fails})}/{len(merged)} clean "
          f"(roles, think+```json, verdict/findings/gts contract)")
    print(f"{'template-token leak gate':<32}{_status(not leak_hits):<8}"
          f"{len(leak_hits)} hit(s) (must be 0) — screened {len(LEAK_MARKERS)} markers")
    print(f"{'contamination (train/eval)':<32}{_status(contam['status'] == 'pass'):<8}"
          f"row_id ∩ = {contam['intersection']} (must be 0)")
    print(f"{'frozen-exam cross-check':<32}{_status(exam_check['status'] == 'pass'):<8}"
          f"{exam_check['train_rows_compared']} train rows vs "
          f"{exam_check['exam_shingles_total']} shingles from {len(briefs)} exams "
          f"{exam_check['exams_compared']}; hits={len(exam_check['hits'])}")
    bstat = {"pass": "PASS", "fail": "FAIL", "record": "RECORD"}[balance["status"]]
    print(f"{'class-balance tripwire':<32}{bstat:<8}"
          f"by_verdict={balance['staged']['by_verdict']} "
          f"by_dc_class={balance['staged']['by_dc_class']}"
          + (f"  MISMATCH={balance['mismatches']}" if balance.get("mismatches") else ""))
    print(f"{'target transform':<32}{'RECORD':<8}"
          f"strip_think={strip_think} strip_fence={strip_fence} "
          f"(default => bare verdict JSON; byte-matches the qav-heldout serving contract)")
    ex = seq["exceed"]
    print(f"{'seq-length audit (est)':<32}{'RECORD':<8}"
          f"p50={seq['p50']} p95={seq['p95']} p99={seq['p99']} max={seq['max']} tok "
          f"@ {seq['est_chars_per_token']} ch/tok  (verdict at END — truncation eats the label)")
    print(f"{'':<32}{'':<8}exceed: " + "  ".join(f"{k}={ex[k]['rows']}({ex[k]['pct']}%)" for k in ex))
    print(f"{'':<32}{'':<8}RECOMMEND --max-seq-length {seq['recommended_max_seq_length']} "
          f"(smallest bucket with ~0% truncation; confirm on the real gemma-4 tokenizer)")

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
        print("PHASE-0 VERDICT: PASS (exit 0) — all hard gates green.")
        print(f"  staged train : {train_path}  ({len(staged_train)} rows)")
        print(f"  staged eval  : {eval_path}  ({len(staged_eval)} rows)")
        print(f"  manifest     : {manifest_path}")
    else:
        print("PHASE-0 VERDICT: FAIL (exit 1) — hard gate(s) red; nothing written.")
    print(f"{bar}\n")


if __name__ == "__main__":
    sys.exit(main())
