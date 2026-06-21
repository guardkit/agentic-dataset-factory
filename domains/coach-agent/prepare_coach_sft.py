#!/usr/bin/env python3
"""
prepare_coach_sft.py — Convert the curated Coach corpus into ShareGPT SFT input
===============================================================================
Source : ~/coach-dataset/curated/train_final.jsonl  (flat {prompt, completion, weight,
         source, decision, ...} structured-JSON Coach verdicts)
Target : ~/fine-tuning/data/train-coach.jsonl       (ShareGPT {messages:[...], metadata})

`train_coach_moe.py` (and the shared `train_gemma4_moe.py`) only read ShareGPT-shaped
JSONL — a `messages` list of `{role, content}` pairs. The Coach corpus is flat
prompt/completion, so this script:

  1. Wraps each row as a single user turn (the Coach instruction + ACs + Player report)
     followed by a single assistant turn (the fenced ```json verdict).
  2. **Oversamples by weight** — TRL's SFTTrainer has no per-sample loss weighting, so
     the HANDOFF's anti-rubber-stamp weighting (feedback/corrective x2.0, approve+issues
     x1.5, plain approve x1.0) is realised by duplicating rows `round(weight)` times.
     This is the lever that stops the Coach learning to rubber-stamp `approve`.
  3. Runs the runbook Phase-0.2 **template-token leak gate** (`<|turn>`, `<|channel>`):
     if the Player ever bled chat-template control tokens into content, fine-tuning would
     teach the model to emit them — fatal. Zero tolerance; aborts on any hit.
  4. Keeps `source=synthetic_hardcase` rows **filterable** (`--exclude-source`) — they are
     authored symptom->ideal-catch pairs, not real Claude verdicts.

Usage:
    python prepare_coach_sft.py                       # defaults below
    python prepare_coach_sft.py --weight-mode round   # round(weight) copies (default)
    python prepare_coach_sft.py --weight-mode none    # 1 copy each (ablation: no weighting)
    python prepare_coach_sft.py --weight-mode scale --weight-scale 2  # round(weight*2)
    python prepare_coach_sft.py --exclude-source synthetic_hardcase   # drop authored cases
    python prepare_coach_sft.py --no-fence            # strip ```json fence (serve-contract align)

Notes:
  * Serving alignment: the Coach is served via llama.cpp under a GBNF grammar. If the
    serving grammar emits *raw* JSON (no ```json fence), pass --no-fence so train == serve.
    Verify against the COACHSPLIT serving contract before the full run (see RUNBOOK Phase 0.3).
"""

import argparse
import json
import os
import random
import sys
from collections import Counter
from pathlib import Path

DEFAULT_SRC = os.path.expanduser("~/coach-dataset/curated/train_final.jsonl")
DEFAULT_OUT = os.path.expanduser("~/fine-tuning/data/train-coach.jsonl")
DEFAULT_HOLDOUT = os.path.expanduser("~/coach-dataset/curated/holdout_eval.jsonl")

# Chat-template control tokens that must NEVER appear inside content (runbook Phase 0.2).
LEAK_MARKERS = ["<|turn>", "<turn|>", "<|channel>", "<channel|>"]

# Metadata fields worth carrying through for later filtering / analysis.
META_KEYS = ["source", "decision", "weight", "repo", "task_id", "turn",
             "has_issues", "provenance", "split", "symptom_modelled", "rule",
             "rule_cited", "confidence"]


def parse_args():
    p = argparse.ArgumentParser(description="Convert Coach corpus -> ShareGPT SFT input")
    p.add_argument("--src", default=DEFAULT_SRC, help="Curated flat JSONL (train_final)")
    p.add_argument("--out", default=DEFAULT_OUT, help="ShareGPT JSONL output path")
    p.add_argument("--weight-mode", choices=["round", "none", "scale", "ceil"],
                   default="round",
                   help="round: copies=max(1,round(weight)) [default]; none: 1 copy "
                        "(no weighting ablation); scale: round(weight*scale); ceil: ceil(weight)")
    p.add_argument("--weight-scale", type=float, default=1.0,
                   help="Multiplier used by --weight-mode scale (e.g. 2 -> 1.0/1.5/2.0 "
                        "become 2/3/4 copies, preserving finer weight ratios)")
    p.add_argument("--exclude-source", action="append", default=[],
                   help="Drop rows whose `source` matches (repeatable). "
                        "e.g. --exclude-source synthetic_hardcase")
    p.add_argument("--drop-malformed", action="store_true",
                   help="Drop rows whose verdict JSON does not parse / lacks a valid decision "
                        "(default: keep but WARN — fix the source instead). Catches authored "
                        "hard_case bugs that would teach malformed verdicts.")
    p.add_argument("--coachsplit-schema", dest="coachsplit", action="store_true", default=True,
                   help="Align prompt+verdict to the live COACHSPLIT grammar: inject task_id+turn "
                        "as the leading verdict keys (REQUIRED for the fine-tune to pass the "
                        "coach-verdict.gbnf + parser contract). ON by default.")
    p.add_argument("--no-coachsplit-schema", dest="coachsplit", action="store_false",
                   help="Keep the original decision-first verdict shape (pre-COACHSPLIT contract)")
    p.add_argument("--fence", dest="fence", action="store_true", default=True,
                   help="Keep the ```json fence in completions (default)")
    p.add_argument("--no-fence", dest="fence", action="store_false",
                   help="Strip the ```json ... ``` fence, leaving raw JSON (serve-align)")
    p.add_argument("--system", default=None,
                   help="Optional system message prepended to every example. Omit unless "
                        "the serving contract injects a system turn (default: none — the "
                        "Coach instruction already lives in the user turn).")
    p.add_argument("--holdout", default=DEFAULT_HOLDOUT,
                   help="Holdout file checked for prompt overlap (leakage guard)")
    p.add_argument("--seed", type=int, default=3407, help="Shuffle seed")
    p.add_argument("--no-shuffle", action="store_true",
                   help="Do not shuffle (default shuffles so duplicates aren't adjacent)")
    p.add_argument("--est-chars-per-token", type=float, default=3.5,
                   help="Char->token ratio for the seq-length audit (3.5 is conservative "
                        "for Gemma on JSON; the in-container real-tokenizer audit is ground truth)")
    p.add_argument("--max-completion-tokens", type=int, default=0,
                   help="If >0, JSON-aware-compress verdicts whose est-tokens exceed this by "
                        "trimming verbose `notes`/`rationale`/`detail` prose while preserving "
                        "decision + per-criterion result + issues. Lets seq=4096 fit ~all rows "
                        "(the GB10-memory-safe fallback). OFF by default — changes the training "
                        "target toward tighter verdicts; opt in deliberately.")
    p.add_argument("--note-cap", type=int, default=240,
                   help="Char cap per criterion note / issue detail when compressing")
    p.add_argument("--rationale-cap", type=int, default=700,
                   help="Char cap for the top-level rationale when compressing")
    return p.parse_args()


_TASK_RE = __import__("re").compile(r"TASK-[A-Z0-9]+-[A-Za-z0-9]+")


def extract_task_id(*texts):
    for t in texts:
        if t:
            m = _TASK_RE.search(str(t))
            if m:
                return m.group(0)
    return None


def to_coachsplit_schema(prompt, completion, task_id, turn):
    """Align prompt+completion to the live COACHSPLIT serving grammar
    (/opt/llama-swap/grammars/coach-verdict.gbnf), which REQUIRES the verdict object to
    lead with task_id (string), turn (int), decision (in that order) — the harvested data
    predates this contract and leads with `decision`. We (a) tell the prompt which task_id/turn
    to emit first (so the model echoes, not hallucinates), and (b) reshape the completion JSON to
    {task_id, turn, decision, <rest...>}. Returns (new_prompt, new_completion, changed).

    NOTE: reconcile the injected prompt wording with guardkit's actual COACHSPLIT synthesis
    prompt (HarnessAdapter.invoke_synthesis) if it differs — the grammar only fixes structure,
    the values come from the prompt."""
    tid = task_id or "UNKNOWN"
    trn = turn if isinstance(turn, int) else (int(turn) if str(turn).isdigit() else 1)

    fenced = completion.strip().startswith("```")
    raw = strip_fence(completion) if fenced else completion
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return prompt, completion, False
    if "decision" not in obj:
        return prompt, completion, False
    new = {"task_id": str(tid), "turn": trn, "decision": obj["decision"]}
    for k, v in obj.items():
        if k not in ("task_id", "turn", "decision"):
            new[k] = v
    body = json.dumps(new, ensure_ascii=False, indent=2)
    new_completion = f"```json\n{body}\n```" if fenced else body

    # Prompt: realign the "with keys: decision, ..." instruction + give the values to echo.
    new_prompt = prompt.replace(
        "with keys: decision,", "with keys: task_id, turn, decision,")
    new_prompt += (f'\n\nThe verdict object MUST begin with these two keys, in this order, '
                   f'before `decision`:\n  "task_id": "{tid}", "turn": {trn}')
    return new_prompt, new_completion, True


def _truncate(s, cap):
    s = str(s)
    return s if len(s) <= cap else s[:cap].rstrip() + " …[trimmed]"


def compress_completion(completion, cpt, budget_tokens, note_cap, rationale_cap):
    """JSON-aware compression: trim verbose prose fields, keep judgment structure.
    Returns (new_completion, changed: bool, parse_failed: bool)."""
    if len(completion) / cpt <= budget_tokens:
        return completion, False, False
    fenced = completion.strip().startswith("```")
    raw = strip_fence(completion) if fenced else completion
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return completion, False, True  # never risk corrupting unparseable JSON
    for item in obj.get("criteria_verification", []) or []:
        for k in ("notes", "note"):
            if k in item:
                item[k] = _truncate(item[k], note_cap)
    for issue in obj.get("issues", []) or []:
        for k in ("detail", "note", "notes"):
            if k in issue:
                issue[k] = _truncate(issue[k], note_cap)
    if "rationale" in obj:
        obj["rationale"] = _truncate(obj["rationale"], rationale_cap)
    new_raw = json.dumps(obj, ensure_ascii=False, indent=2)
    new = f"```json\n{new_raw}\n```" if fenced else new_raw
    return new, True, False


def seqlen_audit(records, cpt):
    """Estimate per-example token length (prompt+completion+template overhead) and report
    truncation rates at candidate max_seq_length values. The verdict is at the END, so
    truncation cuts the part we most need to learn — this must never be silent."""
    TEMPLATE_OVERHEAD = 16  # turn markers / bos / generation prompt, approx
    lens = []
    for rec in records:
        chars = sum(len(m["content"]) for m in rec["messages"])
        lens.append(chars / cpt + TEMPLATE_OVERHEAD)
    lens.sort()
    n = len(lens)
    def pctile(q):
        return lens[min(n - 1, int(q * n))]
    print(f"\n--- sequence-length audit (est. tokens @ {cpt} chars/token) ---")
    print(f"  p50={pctile(.5):.0f}  p90={pctile(.9):.0f}  p95={pctile(.95):.0f}  "
          f"p99={pctile(.99):.0f}  max={lens[-1]:.0f}")
    for thr in (2048, 4096, 6144, 8192):
        over = sum(1 for x in lens if x > thr)
        flag = "  <-- verdict truncated on these" if over else ""
        print(f"  max_seq_length={thr:5d}: {over:4d}/{n} ({100*over/n:4.1f}%) exceed{flag}")
    print("  NOTE: completions sit at the END; any example over max_seq_length loses its")
    print("  verdict tail. Pick max_seq_length to cover ~p99, and smoke-test GB10 memory")
    print("  (runbook: seq=4096 ~100GB on the 26B MoE; watch nvidia-smi, abort >100GB).")


def weight_to_copies(weight, mode, scale):
    try:
        w = float(weight)
    except (TypeError, ValueError):
        w = 1.0
    if mode == "none":
        return 1
    if mode == "ceil":
        import math
        return max(1, math.ceil(w))
    if mode == "scale":
        return max(1, round(w * scale))
    return max(1, round(w))  # "round"


def strip_fence(text: str) -> str:
    """Remove a leading ```json (or ```) fence and trailing ``` if present."""
    t = text.strip()
    if t.startswith("```"):
        first_nl = t.find("\n")
        if first_nl != -1:
            t = t[first_nl + 1:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3].rstrip()
    return t


def find_leaks(text: str):
    return [m for m in LEAK_MARKERS if m in text]


def main():
    args = parse_args()

    src = Path(args.src)
    if not src.exists():
        sys.exit(f"ERROR: source not found: {src}")

    rows = []
    leak_hits = []
    with src.open() as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError as e:
                sys.exit(f"ERROR: malformed JSON at {src}:{i}: {e}")
            prompt = (r.get("prompt") or "").strip()
            completion = (r.get("completion") or "").strip()
            if not prompt or not completion:
                sys.exit(f"ERROR: empty prompt/completion at {src}:{i}")
            # Leak gate (runbook Phase 0.2) — scan original content before any reshaping.
            for field, txt in (("prompt", prompt), ("completion", completion)):
                hits = find_leaks(txt)
                if hits:
                    leak_hits.append((i, field, hits))
            rows.append(r)

    if leak_hits:
        print("ABORT: template-token leaks detected (runbook Phase 0.2). Fix the corpus first.")
        for ln, field, hits in leak_hits[:20]:
            print(f"  line {ln} [{field}]: {hits}")
        sys.exit(1)

    # Leakage guard: training prompts must be disjoint from the holdout eval set.
    holdout = Path(args.holdout)
    if holdout.exists():
        ho_prompts = {json.loads(l)["prompt"].strip()
                      for l in holdout.open() if l.strip()}
        overlap = sum(1 for r in rows if (r.get("prompt") or "").strip() in ho_prompts)
        if overlap:
            sys.exit(f"ABORT: {overlap} training prompts overlap the holdout eval set "
                     f"({holdout}). Re-run curation — never train on eval.")
        print(f"Leakage guard: 0 / {len(rows)} training prompts overlap holdout — OK")

    excluded = set(args.exclude_source)
    out_records = []
    src_in = Counter()
    src_out = Counter()
    dec_in = Counter()
    dec_out = Counter()
    copy_hist = Counter()
    n_compressed = 0
    n_compress_parsefail = 0
    n_coachsplit = 0
    n_malformed = 0
    malformed_ids = []

    for r in rows:
        source = r.get("source")
        src_in[source] += 1
        dec_in[r.get("decision")] += 1
        if source in excluded:
            continue

        prompt = (r.get("prompt") or "").strip()
        completion = (r.get("completion") or "").strip()
        if args.coachsplit:
            task_id = r.get("task_id") or extract_task_id(r.get("task_title"), prompt)
            turn = r.get("turn", 1)
            prompt, completion, changed = to_coachsplit_schema(
                prompt, completion, task_id, turn)
            n_coachsplit += int(changed)
        if not args.fence:
            completion = strip_fence(completion)
        if args.max_completion_tokens > 0:
            completion, changed, pf = compress_completion(
                completion, args.est_chars_per_token, args.max_completion_tokens,
                args.note_cap, args.rationale_cap)
            n_compressed += int(changed)
            n_compress_parsefail += int(pf)

        # Verdict-validity gate — a malformed JSON target teaches malformed verdicts and
        # fails the live grammar/parser. Catches authored hard_case bugs (e.g. trailing `}`).
        _vbody = strip_fence(completion) if completion.strip().startswith("```") else completion
        try:
            _vo = json.loads(_vbody)
            _valid = isinstance(_vo, dict) and _vo.get("decision") in ("approve", "feedback")
        except json.JSONDecodeError:
            _valid = False
        if not _valid:
            n_malformed += 1
            malformed_ids.append(r.get("task_id") or r.get("task_title") or source)
            if args.drop_malformed:
                continue

        messages = []
        if args.system:
            messages.append({"role": "system", "content": args.system})
        messages.append({"role": "user", "content": prompt})
        messages.append({"role": "assistant", "content": completion})

        meta = {k: r[k] for k in META_KEYS if k in r}
        record = {"messages": messages, "metadata": meta}

        n_copies = weight_to_copies(r.get("weight"), args.weight_mode, args.weight_scale)
        copy_hist[n_copies] += 1
        for _ in range(n_copies):
            out_records.append(record)
            src_out[source] += 1
            dec_out[r.get("decision")] += 1

    if not out_records:
        sys.exit("ERROR: no records to write (everything excluded?)")

    if not args.no_shuffle:
        random.Random(args.seed).shuffle(out_records)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for rec in out_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---- Report ------------------------------------------------------------
    def pct(c):
        tot = sum(c.values()) or 1
        return ", ".join(f"{k}={v} ({100*v/tot:.0f}%)" for k, v in sorted(c.items(), key=str))

    print(f"\n{'='*64}")
    print(f"Coach SFT prep — {src.name} -> {out}")
    print(f"{'='*64}")
    print(f"weight mode      : {args.weight_mode}"
          + (f" (scale={args.weight_scale})" if args.weight_mode == 'scale' else ""))
    print(f"fence kept       : {args.fence}")
    print(f"system turn      : {args.system!r}")
    print(f"excluded sources : {sorted(excluded) or 'none'}")
    print(f"coachsplit schema: {'ON' if args.coachsplit else 'OFF'}"
          + (f" -> {n_coachsplit} verdict(s) reshaped to task_id+turn+decision "
             f"(matches coach-verdict.gbnf)" if args.coachsplit else
             " (decision-first; will FAIL the live grammar/parser)"))
    if n_malformed:
        verb = "DROPPED (all copies)" if args.drop_malformed else "KEPT (WARNING — fix the source!)"
        print(f"malformed verdict: {n_malformed} source row(s) {verb} — invalid JSON / no decision; "
              f"ids: {sorted(set(map(str, malformed_ids)))}")
    if args.max_completion_tokens > 0:
        print(f"compression      : ON @ {args.max_completion_tokens} tok "
              f"(note_cap={args.note_cap}, rationale_cap={args.rationale_cap}) -> "
              f"{n_compressed} verdict(s) trimmed"
              + (f", {n_compress_parsefail} left intact (unparseable JSON)"
                 if n_compress_parsefail else ""))
    print(f"input rows       : {sum(src_in.values())}")
    print(f"output rows      : {len(out_records)}  (after weight-oversampling)")
    print(f"copies/row       : { {k: copy_hist[k] for k in sorted(copy_hist)} }")
    print(f"source  (in)     : {pct(src_in)}")
    print(f"source  (out)    : {pct(src_out)}")
    print(f"decision (in)    : {pct(dec_in)}")
    print(f"decision (out)   : {pct(dec_out)}   <-- feedback% is the anti-rubber-stamp lever")
    # First record preview
    first = out_records[0]
    roles = [m["role"] for m in first["messages"]]
    print(f"\nfirst record roles: {roles}")
    print(f"first user  [:120]: {first['messages'][-2]['content'][:120]!r}")
    print(f"first asst  [:120]: {first['messages'][-1]['content'][:120]!r}")
    seqlen_audit(out_records, args.est_chars_per_token)
    print(f"{'='*64}\n")


if __name__ == "__main__":
    main()
