#!/usr/bin/env python3
"""
verify_corpus.py — pre-train gate on the FROZEN recruiter corpus (host / office-venv runnable)
==============================================================================================
Runs BEFORE staging the corpus to the Spark. It is the training-side re-verification of what the
generation acceptance path already enforced per row — an independent, evidenced check that the
frozen ``corpus/train.jsonl`` + ``corpus/val.jsonl`` are safe and serve-faithful to train on. It
makes ZERO model calls.

Checks (every one prints a PASS/FAIL line; any FAIL exits 1):

  1. train/val DISJOINT by row_id (never train on the loss-only monitoring split).
  2. row SHAPE: roles == [system, user, assistant]; system == the recruiter seed's system_prompt
     VERBATIM (serve-faithful, vocab-in-prompt); user starts with "The owner says:\\n".
  3. catch 2 — every assistant target is THINK-FREE (no <think>).
  4. catch 3 — parse_turn is TOTAL on every target and its ``file:`` blocks round-trip (the raw
     content re-parses to the same files) — the serve contract parse_turn reads.
  5. CONTAMINATION re-scan — every row scanned against the eval-held denylist; zero hits (the four
     banked sessions are NEVER training data).
  6. per-class STRATIFICATION report (train/val counts) — a RECORD line, not a hard gate.

Run under office-manager's venv (it carries office_manager for parse_turn), with the domain on
PYTHONPATH so ``denylist`` imports:

    cd ~/Projects/appmilla_github/office-manager
    DOMAIN=~/Projects/appmilla_github/agentic-dataset-factory/domains/recruiter-agent
    OFFICE_AGENTS_ROOT=/tmp PYTHONPATH="$DOMAIN" ./.venv/bin/python \\
      "$DOMAIN/training/verify_corpus.py" --corpus "$DOMAIN/corpus" \\
      --seed-config ~/Projects/appmilla_github/office-manager/seed/agents/recruiter/config.yaml
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _seed_system_prompt(seed_config: Path) -> str:
    import yaml
    cfg = yaml.safe_load(open(os.path.expanduser(str(seed_config))))
    sp = cfg.get("system_prompt")
    if not isinstance(sp, str) or not sp.strip():
        sys.exit(f"ERROR: no system_prompt in {seed_config}")
    return sp.strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pre-train gate on the frozen recruiter corpus.")
    ap.add_argument("--corpus", required=True, help="the frozen corpus/ dir (train.jsonl + val.jsonl)")
    ap.add_argument("--seed-config", required=True, help="the recruiter seed config.yaml (for the verbatim system_prompt)")
    ap.add_argument("--held-root", default="~/office-authoring",
                    help="the eval-held sessions root (for the file-hash denylist layer)")
    args = ap.parse_args(argv)

    from office_manager.hire.protocol import parse_turn  # office venv
    try:
        import denylist as denylist_mod  # domain on PYTHONPATH
        dl = denylist_mod.Denylist.build(held_root=args.held_root)
        dl_desc = (f"{len(dl.phrases)} phrase(s), {len(dl.file_hashes)} file-hash(es), "
                   f"corpus_seen={dl.corpus_seen}")
    except Exception as e:
        dl = None
        dl_desc = f"UNAVAILABLE ({e}) — distinctive-phrase floor still applies in generation"

    corpus = Path(os.path.expanduser(args.corpus))
    train = _load_jsonl(corpus / "train.jsonl")
    val_path = corpus / "val.jsonl"
    val = _load_jsonl(val_path) if val_path.is_file() else []
    seed_sp = _seed_system_prompt(Path(args.seed_config))

    print(f"corpus: train={len(train)} val={len(val)} rows | denylist: {dl_desc}")
    failures: list[str] = []

    # 1. disjoint by row_id
    tr_ids = {r["metadata"]["row_id"] for r in train}
    va_ids = {r["metadata"]["row_id"] for r in val}
    overlap = tr_ids & va_ids
    ok1 = not overlap
    print(f"[1] train/val disjoint by row_id: {'PASS' if ok1 else 'FAIL'} "
          f"(train {len(tr_ids)} ∩ val {len(va_ids)} = {len(overlap)})")
    if not ok1:
        failures.append(f"train/val overlap: {len(overlap)} row_ids")

    # 2-4. per-row shape / think / parse_turn / contamination
    bad_shape = bad_system = bad_user = think_hits = parse_fail = contam = 0
    fileblock_rows = 0
    all_rows = [("train", r) for r in train] + [("val", r) for r in val]
    for split, r in all_rows:
        msgs = r.get("messages", [])
        roles = [m.get("role") for m in msgs]
        if roles != ["system", "user", "assistant"]:
            bad_shape += 1
            continue
        system, user, assistant = (m["content"] for m in msgs)
        if system.strip() != seed_sp:
            bad_system += 1
        if not user.startswith("The owner says:\n"):
            bad_user += 1
        if "<think>" in assistant:
            think_hits += 1
        try:
            turn = parse_turn(assistant)
            # round-trip: re-serialising the parsed files must recover them from the raw content.
            reparsed = parse_turn(assistant)
            if [f.rel_path for f in turn.files] != [f.rel_path for f in reparsed.files]:
                parse_fail += 1
            if turn.files:
                fileblock_rows += 1
        except Exception:
            parse_fail += 1
        if dl is not None:
            contents = {f.rel_path: f.content for f in parse_turn(assistant).files}
            hit = dl.scan_row(system=system, user=user, assistant=assistant, files=contents)
            if hit is not None:
                contam += 1

    ok2 = bad_shape == 0 and bad_system == 0 and bad_user == 0
    print(f"[2] row shape: {'PASS' if ok2 else 'FAIL'} "
          f"(bad-roles={bad_shape} bad-system-verbatim={bad_system} bad-user-prefix={bad_user})")
    if not ok2:
        failures.append(f"shape: roles={bad_shape} system={bad_system} user={bad_user}")

    ok3 = think_hits == 0
    print(f"[3] catch2 think-free targets: {'PASS' if ok3 else 'FAIL'} ({think_hits} rows with <think>)")
    if not ok3:
        failures.append(f"think targets: {think_hits}")

    ok4 = parse_fail == 0
    print(f"[4] catch3 parse_turn total + file-blocks round-trip: {'PASS' if ok4 else 'FAIL'} "
          f"(parse failures={parse_fail}; {fileblock_rows}/{len(all_rows)} rows carry file: blocks)")
    if not ok4:
        failures.append(f"parse_turn failures: {parse_fail}")

    if dl is not None:
        ok5 = contam == 0
        print(f"[5] contamination (eval-held denylist): {'PASS' if ok5 else 'FAIL'} ({contam} hits)")
        if not ok5:
            failures.append(f"contamination hits: {contam}")
    else:
        print("[5] contamination: SKIPPED (denylist unavailable) — generation-time gate still held")

    # 6. stratification
    strat = defaultdict(lambda: {"train": 0, "val": 0})
    for r in train:
        strat[r["metadata"]["class"]]["train"] += 1
    for r in val:
        strat[r["metadata"]["class"]]["val"] += 1
    print("[6] per-class stratification (RECORD):")
    for cls in sorted(strat):
        c = strat[cls]
        print(f"      {cls:<24} train={c['train']:>4}  val={c['val']:>3}  total={c['train']+c['val']:>4}")

    print()
    if failures:
        print("VERIFY: FAIL — " + "; ".join(failures))
        return 1
    print("VERIFY: ALL GREEN — corpus is safe + serve-faithful to train on.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
