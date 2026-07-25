#!/usr/bin/env python3
"""Merged-gen gate for the coach v4 tune (MANDATORY before any GGUF/serve).

In-container. Loads merged-16bit under plain transformers, generates on 12 rows
sampled from the v4 staged corpus (6 approve incl. traps, 6 reject across guard
classes), and gates on the v4 SERVE CONTRACT, STRICT:

  - the generated text json.loads() DIRECTLY (raw, no fence, no prose) OR parses
    after stripping ONE leading empty/closed thought block (mode recorded — THE
    CATCH: if strip-mode is what passes, the production parser must implement
    the same strip, and the serve gate re-asserts it over the wire);
  - top-level keys exactly {verdict, findings}; findings items exactly {locus};
  - approve => findings == []; reject => >=1 non-empty locus.

Verdict-vs-gold on these train rows is recorded; low agreement on memorized
rows is a loud warning (not the grade — the disjoint fleet-evals v2 exam is).
GATE: PASS only if 12/12 contract-clean. Writes merged-gen-gate.json.
"""
import json
import random
import re
import sys

DATA = "/workspace/data/train-coach-v4.jsonl"
MERGED = "/workspace/output/coach-gemma4-26b-moe-v4/merged-16bit"
OUT = "/workspace/output/coach-gemma4-26b-moe-v4/merged-gen-gate.json"
MAX_NEW = 512

THINK_STRIP = re.compile(r"^\s*<think>\s*</think>\s*", re.DOTALL)


def contract_check(text):
    """Returns (ok, mode, obj_or_error). STRICT raw parse first; then the
    documented single-empty-thought-block strip."""
    for mode, candidate in (("raw", text), ("think-strip", THINK_STRIP.sub("", text, count=1))):
        try:
            obj = json.loads(candidate)
        except Exception as e:
            err = str(e)
            continue
        if set(obj) != {"verdict", "findings"}:
            return False, mode, f"keys {sorted(obj)}"
        if obj["verdict"] not in ("approve", "reject"):
            return False, mode, f"verdict {obj['verdict']!r}"
        if obj["verdict"] == "approve" and obj["findings"] != []:
            return False, mode, "approve with findings"
        if obj["verdict"] == "reject":
            if not obj["findings"]:
                return False, mode, "reject without findings"
            for f in obj["findings"]:
                if set(f) != {"locus"} or not str(f["locus"]).strip():
                    return False, mode, f"bad finding {f}"
        return True, mode, obj
    return False, "none", err


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch

    rows = [json.loads(l) for l in open(DATA)]
    random.seed(3407)
    ap = [r for r in rows if r["metadata"]["decision"] == "approve"]
    rj = [r for r in rows if r["metadata"]["decision"] == "reject"]
    sample = random.sample(ap, 6) + random.sample(rj, 6)

    tok = AutoTokenizer.from_pretrained(MERGED)
    model = AutoModelForCausalLM.from_pretrained(MERGED, torch_dtype=torch.bfloat16, device_map="auto")
    results, n_ok = [], 0
    for r in sample:
        msgs = [m for m in r["messages"] if m["role"] == "user"]
        enc = tok.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True,
                                      return_dict=True, return_tensors="pt").to(model.device)
        out = model.generate(**enc, max_new_tokens=MAX_NEW, do_sample=False,
                             pad_token_id=tok.eos_token_id)
        text = tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        ok, mode, detail = contract_check(text)
        gold = r["metadata"]["decision"]
        agree = ok and isinstance(detail, dict) and detail.get("verdict") == gold
        n_ok += ok
        results.append({
            "gold": gold, "ok": bool(ok), "mode": mode, "agree": bool(agree),
            "raw_head": text[:200],
            "screens": {"fence": "```" in text, "think_tag": "<think>" in text,
                        "turn_tok": "<|turn>" in text},
        })
        print(f"[{'OK' if ok else 'FAIL'}:{mode}] gold={gold} agree={agree} head={text[:80]!r}")

    agree_n = sum(r["agree"] for r in results)
    verdict = "PASS" if n_ok == len(results) else "FAIL"
    report = {"gate": verdict, "contract_clean": f"{n_ok}/{len(results)}",
              "verdict_agree": f"{agree_n}/{len(results)}",
              "modes": sorted({r['mode'] for r in results if r['ok']}),
              "results": results}
    json.dump(report, open(OUT, "w"), indent=2)
    print(f"MERGED-GEN GATE: {verdict} — contract {n_ok}/{len(results)}, "
          f"agree {agree_n}/{len(results)} -> {OUT}")
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
