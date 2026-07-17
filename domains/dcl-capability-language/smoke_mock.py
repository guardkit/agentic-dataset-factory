#!/usr/bin/env python
"""MOCK end-to-end smoke for the dcl-capability-language corpus lane (C2).

Proves the generation lane end-to-end WITHOUT a single real model call. A local
OpenAI-compatible stub server is stood up on an EPHEMERAL port; the real
``OpenAICompatibleClient`` (src/dcl/generate.py) is pointed at it, so the Player/teacher
wire contract is exercised for real while ZERO traffic ever leaves for :9000 or any LLM.
The Coach is an HTTP adapter that also talks only to the stub. The compile gate and the
defect injector are the REAL vendored DCL compiler + recipes — the deterministic truth
source is never mocked.

Run:  PYTHONPATH=src python domains/dcl-capability-language/smoke_mock.py

It drives ``run_generation`` in both modes at small caps (author limit 6, repair limit 6),
merges the two phases into ``output/dcl-capability-language/`` with a manifest, and asserts
the corpus-level guarantees. Prints a machine-checkable summary block for the receipt.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# --- imports from the domain under test (PYTHONPATH=src) -------------------------------
from dcl import checker, contracts
from dcl.briefs import load_briefs, render_reference_capability
from dcl.contamination import load_jsonl
from dcl.generate import (
    CoachVerdict,
    GenerateConfig,
    OpenAICompatibleClient,
    run_generation,
)
from dcl.manifest import build_manifest, validate_manifest

REPO = Path(__file__).resolve().parents[2]
FINAL_DIR = REPO / "output" / "dcl-capability-language"
SCRATCH = Path("/tmp/claude-1000/-home-richardwoollcott-Projects-appmilla-github-ai-transition/"
               "6944e5ab-cd64-4226-a0e7-aee4d542ca6d/scratchpad")

# --- fixtures: 6 briefs, the scripted author outcomes ----------------------------------
BRIEFS = load_briefs()[:6]
DIRTY_IDX = 4          # brief that fails to compile once, then compiles on the retry
COACH_REJECT_IDX = 5   # brief the Coach rejects (never accepted)

# Canned VALID capabilities = the deterministic reference renders (guaranteed to compile).
CANNED_VALID = {b.id: f"```dcl\n{render_reference_capability(b)}\n```" for b in BRIEFS}
# The observed zero-shot failure class (held-004 broken.dcl): an invented actor kind.
INVALID_FENCE = "```dcl\nlanguage dcl 1.0\n\nactor Bad is machine\n```"

COACH_SYSTEM = "You are the DCL Coach. Return a JSON verdict."

_stub_calls = {"player": 0, "coach": 0}


def _brief_for(user_text: str):
    """Identify which of the 6 briefs a request is about (paragraph is unique)."""
    for b in BRIEFS:
        if b.brief_text in user_text:
            return b
    return None


class StubHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence per-request logging
        pass

    def _send(self, content: str):
        body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        assert self.path.endswith("/chat/completions"), self.path
        n = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(n))
        msgs = payload["messages"]
        system = msgs[0]["content"]
        user = msgs[1]["content"]
        brief = _brief_for(user)

        if system.startswith(COACH_SYSTEM):
            _stub_calls["coach"] += 1
            reject = brief is not None and brief.id == BRIEFS[COACH_REJECT_IDX].id
            verdict = {
                "decision": "revise" if reject else "accept",
                "score": 3 if reject else 9,
                "reasons": ["brief asks for an emitted event the capability omits"] if reject else [],
            }
            return self._send(json.dumps(verdict))

        # --- PLAYER / teacher endpoint ---
        _stub_calls["player"] += 1
        if "## Broken DCL capability" in user:
            # REPAIR: teacher authors ONLY the <think> rationale (label is compiler-fixed).
            return self._send(
                "<think>\nThe diagnostics name a single closed-vocabulary violation. I restore the "
                "one compiler-legal literal the diagnostics point at and change nothing else, "
                "preserving every unaffected declaration.\n</think>"
            )
        if "## Compiler feedback (repair)" in user:
            # retry of the dirty brief -> now emit its compiling capability.
            return self._send(CANNED_VALID[BRIEFS[DIRTY_IDX].id])
        if "## Coach feedback (revise)" in user:
            # coach-reject brief revise turn -> emit a (still compiling) capability; coach re-rejects.
            return self._send(CANNED_VALID[BRIEFS[COACH_REJECT_IDX].id])
        # fresh author turn
        if brief is not None and brief.id == BRIEFS[DIRTY_IDX].id:
            return self._send(INVALID_FENCE)          # dirty-then-clean, first pass
        if brief is not None:
            return self._send(CANNED_VALID[brief.id])  # a clean vocab-skeleton variant
        return self._send(INVALID_FENCE)


class HTTPCoach:
    """Coach client that talks ONLY to the local stub server (zero real calls)."""

    def __init__(self, endpoint: str, model: str = "stub-coach"):
        self.endpoint = endpoint
        self.model = model

    def assess(self, brief, capability_text: str) -> CoachVerdict:
        import urllib.request
        user = (f"## Feature brief\n{brief.brief_text}\n\n## Candidate capability\n"
                f"```dcl\n{capability_text}\n```\n\n## Task\nReturn a JSON verdict.")
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": COACH_SYSTEM},
                {"role": "user", "content": user},
            ],
        }).encode()
        req = urllib.request.Request(
            self.endpoint.rstrip("/") + "/chat/completions",
            data=payload, headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            content = json.loads(resp.read())["choices"][0]["message"]["content"]
        v = json.loads(content)
        return CoachVerdict(decision=v["decision"], score=int(v["score"]),
                            reasons=list(v.get("reasons", [])))


def _factory_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO).decode().strip()
    except Exception:  # pragma: no cover
        return "unknown"


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
    port = server.server_address[1]
    assert port != 9000, "stub must NOT bind :9000"
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    endpoint = f"http://127.0.0.1:{port}/v1"
    _log(f"# stub OpenAI-compatible server: {endpoint}  (ephemeral port {port}; :9000 untouched)")

    client = OpenAICompatibleClient(endpoint=endpoint, model="stub-player")
    coach = HTTPCoach(endpoint)
    created, sha = "2026-07-17", _factory_sha()

    tmp_a = SCRATCH / "smoke_author"
    tmp_b = SCRATCH / "smoke_repair"
    tmp_b2 = SCRATCH / "smoke_repair_rerun"

    # ---- PHASE A: AUTHOR (limit 6) --------------------------------------------------
    _log("\n## PHASE A — author (mode=dcl_author, limit=6)")
    cfg_a = GenerateConfig(mode="dcl_author", limit=6, holdout_fraction=0.1,
                           output_dir=str(tmp_a), seed="dcl-phase1")
    sum_a = run_generation(cfg_a, player=client, coach=coach, briefs=BRIEFS,
                           write_manifest=False, created=created, factory_sha=sha)
    _log(f"   author_accepted={sum_a.author_accepted} author_rejected={sum_a.author_rejected} "
         f"train={sum_a.train} eval_dcl={sum_a.eval_dcl}")
    assert sum_a.author_accepted == 5, sum_a
    assert sum_a.author_rejected == 1, sum_a

    # ---- PHASE B: REPAIR (limit 6) --------------------------------------------------
    _log("\n## PHASE B — repair (mode=dcl_repair, limit=6)")
    cfg_b = GenerateConfig(mode="dcl_repair", limit=6, holdout_fraction=0.1,
                           output_dir=str(tmp_b), seed="dcl-phase1")
    sum_b = run_generation(cfg_b, player=client, coach=coach, teacher=client, briefs=BRIEFS,
                           write_manifest=False, created=created, factory_sha=sha)
    _log(f"   repair_written={sum_b.repair_written} skipped_anchor={sum_b.repair_skipped_anchor} "
         f"train={sum_b.train} eval_dcl={sum_b.eval_dcl}")
    assert sum_b.repair_written == 6, sum_b

    # ---- PHASE B2: determinism re-run ----------------------------------------------
    _log("\n## PHASE B2 — repair re-run (same seed/config) for determinism")
    cfg_b2 = GenerateConfig(mode="dcl_repair", limit=6, holdout_fraction=0.1,
                            output_dir=str(tmp_b2), seed="dcl-phase1")
    run_generation(cfg_b2, player=client, coach=coach, teacher=client, briefs=BRIEFS,
                   write_manifest=False, created=created, factory_sha=sha)

    def _ids(d: Path, name: str) -> list[str]:
        p = d / name
        return [r["metadata"]["row_id"] for r in load_jsonl(p)] if p.exists() else []

    ids_b = _ids(tmp_b, "train.jsonl") + _ids(tmp_b, "eval_dcl.jsonl")
    ids_b2 = _ids(tmp_b2, "train.jsonl") + _ids(tmp_b2, "eval_dcl.jsonl")
    assert sorted(ids_b) == sorted(ids_b2), "repair row_ids not deterministic across re-run"
    _log(f"   deterministic repair row_ids: {sorted(ids_b) == sorted(ids_b2)} "
         f"({len(ids_b)} ids identical)")

    # ---- MERGE the two phases into the canonical output dir + manifest --------------
    _log("\n## MERGE -> output/dcl-capability-language/ (+ manifest)")
    a_train = load_jsonl(tmp_a / "train.jsonl") if (tmp_a / "train.jsonl").exists() else []
    a_eval = load_jsonl(tmp_a / "eval_dcl.jsonl") if (tmp_a / "eval_dcl.jsonl").exists() else []
    a_rej = (tmp_a / "rejected.jsonl").read_text(encoding="utf-8") if (tmp_a / "rejected.jsonl").exists() else ""
    b_train = load_jsonl(tmp_b / "train.jsonl") if (tmp_b / "train.jsonl").exists() else []
    b_eval = load_jsonl(tmp_b / "eval_dcl.jsonl") if (tmp_b / "eval_dcl.jsonl").exists() else []

    train_rows = a_train + b_train
    eval_rows = a_eval + b_eval

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("train.jsonl", "eval_dcl.jsonl", "rejected.jsonl", "manifest.json"):
        p = FINAL_DIR / name
        if p.exists():
            p.replace(p.with_suffix(p.suffix + ".bak"))  # house backup convention

    (FINAL_DIR / "train.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in train_rows), encoding="utf-8")
    (FINAL_DIR / "eval_dcl.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in eval_rows), encoding="utf-8")
    (FINAL_DIR / "rejected.jsonl").write_text(a_rej, encoding="utf-8")

    manifest = build_manifest(train_rows, eval_rows, dataset_id="dcl-phase1-smoke-mock",
                              created=created, factory_sha=sha)
    validate_manifest(manifest)
    (FINAL_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                             encoding="utf-8")

    # ================= ASSERTIONS over the FINAL corpus ==============================
    _log("\n## ASSERTIONS (over output/dcl-capability-language/)")
    all_rows = load_jsonl(FINAL_DIR / "train.jsonl") + load_jsonl(FINAL_DIR / "eval_dcl.jsonl")

    # 1) every row parses as a valid ShareGPT row (structure + contract)
    for r in all_rows:
        contracts.validate_row(r)
    _log(f"   [1] ShareGPT parse: all {len(all_rows)} rows validate")

    # 2) corpus-level compile sweep: every accepted/corrected capability compiles ok:true
    compiled_ok = 0
    for r in all_rows:
        cap = contracts.extract_capability(r)
        res = checker.compile(cap)
        assert res.ok, f"row {r['metadata']['row_id']} capability did NOT compile: {res.error_codes}"
        compiled_ok += 1
    _log(f"   [2] compile sweep: {compiled_ok}/{len(all_rows)} accepted capabilities compile ok:true")

    # 3) repair completions byte-equal the pre-injection originals
    originals = {render_reference_capability(b).strip() for b in BRIEFS}
    repair_rows = [r for r in all_rows if r["metadata"]["mode"] == "dcl_repair"]
    for r in repair_rows:
        corrected = contracts.extract_capability(r).strip()
        assert corrected in originals, "repair correction is not a byte-equal pre-injection original"
        # and the broken user-side capability genuinely fails to compile
        user = r["messages"][1]["content"]
        broken = user.split("```dcl\n", 1)[1].split("\n```", 1)[0]
        assert not checker.compile(broken).ok, "repair row's broken input unexpectedly compiled"
    _log(f"   [3] repair byte-equality: all {len(repair_rows)} corrections == a pre-injection original; "
         f"all broken inputs fail the compiler")

    # 4) manifest counts + embedded contamination check
    mtrain = manifest["counts"]["train"]["total"]
    meval = manifest["counts"]["eval_dcl"]["total"]
    assert mtrain == len(train_rows) and meval == len(eval_rows), "manifest counts mismatch"
    assert manifest["contamination_check"]["status"] == "pass", manifest["contamination_check"]
    by_mode = manifest["counts"]["train"]["by_mode"]
    _log(f"   [4] manifest: train.total={mtrain} eval.total={meval} "
         f"by_mode(train)={by_mode} contamination={manifest['contamination_check']['status']} "
         f"visibility={manifest['visibility']!r}")

    # 5) rejected.jsonl carries the reject(s) with reasons
    rej_lines = [json.loads(l) for l in (FINAL_DIR / "rejected.jsonl").read_text().splitlines() if l.strip()]
    assert len(rej_lines) == 1 and rej_lines[0]["reason"] == "coach_rejected", rej_lines
    _log(f"   [5] rejected.jsonl: {len(rej_lines)} row, reason={rej_lines[0]['reason']!r}")

    # 6) zero real calls: all traffic went to the local stub
    _log(f"   [6] stub traffic: player_calls={_stub_calls['player']} coach_calls={_stub_calls['coach']} "
         f"-> ALL local (:{port}); :9000 requests = 0")

    server.shutdown()

    # ------ machine-checkable summary block for the receipt --------------------------
    _log("\n=== SMOKE SUMMARY ===")
    print(json.dumps({
        "stub_endpoint": endpoint,
        "author_accepted": sum_a.author_accepted,
        "author_rejected": sum_a.author_rejected,
        "repair_written": sum_b.repair_written,
        "repair_deterministic": sorted(ids_b) == sorted(ids_b2),
        "corpus_rows": len(all_rows),
        "train_total": mtrain,
        "eval_total": meval,
        "rejected_rows": len(rej_lines),
        "compile_sweep_ok": compiled_ok,
        "repair_byte_equal": True,
        "contamination_check": manifest["contamination_check"]["status"],
        "manifest_visibility": manifest["visibility"],
        "stub_player_calls": _stub_calls["player"],
        "stub_coach_calls": _stub_calls["coach"],
        "real_9000_calls": 0,
    }, indent=2))
    _log("\nOK — mock smoke passed (zero real model calls).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
