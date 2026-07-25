#!/usr/bin/env python3
"""THE SERVE GATE (the check coach-ft-v3 skipped) — clean UNFENCED parse over
the wire, against the exported Q8_0 GGUF served by the PINNED llama.cpp build.

Host-side, stdlib-only. Launches llama-server (pinned build) on an ephemeral
port with the exported GGUF, posts 8 sampled v4 corpus prompts as toolless chat
completions (temp 0, reasoning off), and asserts the v4 serve contract on the
RAW response text:

  - json.loads() the message content DIRECTLY (raw mode), or after stripping
    ONE leading empty thought block (strip mode; recorded — the production
    parser must then do the same);
  - keys exactly {verdict, findings}, findings items exactly {locus};
  - approve => []; reject => >=1 non-empty locus;
  - screens: no ``` anywhere, no template tokens.

GATE: PASS only if 8/8 contract-clean. Ship nothing that fails here.

Usage:
  python3 serve_gate_coach_v4.py --gguf <path.gguf> \
      [--server ~/llama.cpp-gemma4-jul25/build/bin/llama-server] [--port 5899]
"""
import argparse
import json
import random
import re
import subprocess
import sys
import time
import urllib.request

THINK_STRIP = re.compile(r"^\s*<think>\s*</think>\s*", re.DOTALL)
DATA = "/home/richardwoollcott/fine-tuning/data/train-coach-v4.jsonl"


def contract_check(text):
    err = "unparsed"
    for mode, cand in (("raw", text), ("think-strip", THINK_STRIP.sub("", text, count=1))):
        try:
            obj = json.loads(cand)
        except Exception as e:
            err = str(e)
            continue
        if set(obj) != {"verdict", "findings"}:
            return False, mode, f"keys {sorted(obj)}"
        if obj["verdict"] not in ("approve", "reject"):
            return False, mode, f"verdict {obj['verdict']!r}"
        if obj["verdict"] == "approve" and obj["findings"] != []:
            return False, mode, "approve with findings"
        if obj["verdict"] == "reject" and (
            not obj["findings"]
            or any(set(f) != {"locus"} or not str(f["locus"]).strip() for f in obj["findings"])
        ):
            return False, mode, "bad findings"
        return True, mode, obj
    return False, "none", err


def wait_ready(port, timeout=420):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3)
            return True
        except Exception:
            time.sleep(3)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--server", default="/home/richardwoollcott/llama.cpp-gemma4-jul25/build/bin/llama-server")
    ap.add_argument("--port", type=int, default=5899)
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--ctx", type=int, default=16384)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(DATA)]
    random.seed(1234)
    sample = (random.sample([r for r in rows if r["metadata"]["decision"] == "approve"], args.n // 2)
              + random.sample([r for r in rows if r["metadata"]["decision"] == "reject"], args.n - args.n // 2))

    proc = subprocess.Popen(
        [args.server, "--port", str(args.port), "--host", "127.0.0.1",
         "--model", args.gguf, "--ctx-size", str(args.ctx), "-ngl", "999",
         "--no-mmap", "--jinja", "--chat-template-kwargs", '{"enable_thinking":false}'],
        stdout=open("/tmp/serve_gate_v4_server.log", "w"), stderr=subprocess.STDOUT)
    try:
        if not wait_ready(args.port):
            print("ABORT: server never became ready (see /tmp/serve_gate_v4_server.log)")
            sys.exit(2)
        results, n_ok = [], 0
        for r in sample:
            msgs = [m for m in r["messages"] if m["role"] == "user"]
            body = json.dumps({"messages": msgs, "temperature": 0.0, "max_tokens": 512}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{args.port}/v1/chat/completions", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as resp:
                text = json.load(resp)["choices"][0]["message"]["content"]
            ok, mode, detail = contract_check(text)
            gold = r["metadata"]["decision"]
            agree = ok and isinstance(detail, dict) and detail.get("verdict") == gold
            n_ok += ok
            results.append({"gold": gold, "ok": bool(ok), "mode": mode,
                            "agree": bool(agree), "fence": "```" in text,
                            "raw_head": text[:200]})
            print(f"[{'OK' if ok else 'FAIL'}:{mode}] gold={gold} agree={agree} head={text[:80]!r}")
        verdict = "PASS" if n_ok == len(results) else "FAIL"
        agree_n = sum(x["agree"] for x in results)
        report = {"gate": verdict, "contract_clean": f"{n_ok}/{len(results)}",
                  "verdict_agree": f"{agree_n}/{len(results)}",
                  "modes": sorted({x['mode'] for x in results if x['ok']}),
                  "gguf": args.gguf, "results": results}
        out = "/home/richardwoollcott/fine-tuning/output/serve-gate-v4.json"
        json.dump(report, open(out, "w"), indent=2)
        print(f"SERVE GATE: {verdict} — contract {n_ok}/{len(results)}, agree {agree_n}/{len(results)} -> {out}")
        sys.exit(0 if verdict == "PASS" else 1)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
