#!/usr/bin/env python3
"""build_v3_sft.py — join v3 training prompts with teacher verdicts into a flat
SFT corpus (prompt + fenced COACHSPLIT completion) for prepare_coach_sft.py.

Inputs:
  --eval   v3_train_eval.jsonl   (assemble_step0_synthetic output: scenario_id,
           task_id, turn, decision[gold], prompt, acceptance_criteria, guard...)
  --verdicts  the teacher-verdict workflow run output (.output JSON with logs[]
           VERDICT_JSONL lines) OR a jsonl of {scenario_id, gold, verdict, agree}.

Gate: keep a row only when the teacher's decision == the deterministic gold (the
verdict is the COMPLETION; the deterministic gold + guard-checker already proved
the bundle is consistent, so teacher-agreement is the final realism/soundness
gate — the v2 blind-verify discipline). EVIDENCE lives in the prompt, JUDGMENT
in the completion (no leakage).

Output: v3_sft_raw.jsonl — flat {prompt, completion, decision, weight, source,
task_id, turn, scenario_id, guard_targeted} rows for prepare_coach_sft.py.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

HERE = Path(__file__).resolve().parent

# anti-rubber-stamp weighting (mild; the corpus is already ~50/50). feedback x1.5.
WEIGHT = {"feedback": 1.5, "approve": 1.0}


def load_verdicts(path: Path) -> Dict[str, Dict[str, Any]]:
    text = path.read_text()
    out: Dict[str, Dict[str, Any]] = {}
    # workflow .output JSON with logs[] VERDICT_JSONL lines
    try:
        d = json.loads(text)
        logs = d.get("logs", []) if isinstance(d, dict) else []
        for line in logs:
            if isinstance(line, str) and line.startswith("VERDICT_JSONL "):
                o = json.loads(line[len("VERDICT_JSONL "):])
                out[o["scenario_id"]] = o
    except Exception:
        pass
    if not out:  # fallback: plain jsonl
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
                if o.get("scenario_id"):
                    out[o["scenario_id"]] = o
            except Exception:
                continue
    return out


def build_completion(task_id: str, turn: int, gold: str, verdict: Dict[str, Any]) -> str:
    """Fenced COACHSPLIT JSON leading with task_id, turn, decision."""
    obj: Dict[str, Any] = {"task_id": str(task_id), "turn": int(turn), "decision": gold}
    if gold == "feedback":
        issues = verdict.get("issues") or []
        # guarantee at least one issue for a feedback verdict
        if not issues:
            issues = [{"type": "missing_requirement", "severity": "major",
                       "description": verdict.get("rationale", "evidence indicates the work is not complete")}]
        obj["issues"] = issues
    obj["criteria_verification"] = verdict.get("criteria_verification") or []
    obj["rationale"] = verdict.get("rationale", "")
    return "```json\n" + json.dumps(obj, indent=2) + "\n```"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", default=str(HERE / "v3_train_eval.jsonl"))
    ap.add_argument("--verdicts", required=True, nargs="+",
                    help="one or more verdict sources; later files override earlier (for re-verdict merges)")
    ap.add_argument("--out", default=str(HERE / "v3_sft_raw.jsonl"))
    args = ap.parse_args()

    evalrows = [json.loads(l) for l in Path(args.eval).open() if l.strip()]
    verdicts: Dict[str, Dict[str, Any]] = {}
    for vp in args.verdicts:
        verdicts.update(load_verdicts(Path(vp)))
    print(f"loaded {len(evalrows)} prompts, {len(verdicts)} teacher verdicts (merged from {len(args.verdicts)} sources)")

    rows: List[Dict[str, Any]] = []
    dropped = []
    for e in evalrows:
        sid = e["scenario_id"]
        gold = e["decision"]
        v = verdicts.get(sid)
        if v is None or not v.get("verdict") or not v.get("agree"):
            dropped.append((sid, gold, (v or {}).get("verdict", {}).get("decision") if v else "no-verdict"))
            continue
        completion = build_completion(e.get("task_id", sid), e.get("turn", 1), gold, v["verdict"])
        rows.append({
            "prompt": e["prompt"],
            "completion": completion,
            "decision": gold,
            "weight": WEIGHT.get(gold, 1.0),
            "source": "synthetic_v3",
            "scenario_id": sid,
            "task_id": e.get("task_id", sid),
            "turn": e.get("turn", 1),
            "guard_targeted": e.get("guard_targeted"),
        })

    Path(args.out).write_text("".join(json.dumps(r) + "\n" for r in rows))
    bal = Counter(r["decision"] for r in rows)
    print(f"wrote {len(rows)} SFT rows -> {args.out}   balance={dict(bal)}")
    print(f"dropped {len(dropped)} (teacher disagreed / missing):")
    for d in dropped[:40]:
        print("  ", d)


if __name__ == "__main__":
    main()
