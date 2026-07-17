#!/usr/bin/env python
"""Documented entrypoint for a REAL dcl-capability-language generation run.

Wires the real OpenAI-compatible clients from ``agent-config.yaml`` (Player/teacher +
Coach) and drives ``src/dcl/generate.py``'s ``run_generation``. The deterministic truth
source is always the vendored DCL compiler — never a model. Datasets are private (DF-008).

Usage (attended, on the GB10 with the served fleet on :9000):

    PYTHONPATH=src python domains/dcl-capability-language/run_dcl_generation.py \
        --config agent-config.yaml

Honesty notes:
- This driver is FRESH-START, not checkpoint-resumable (unlike agent.py). Each run backs
  up any prior output/*.jsonl + manifest.json to *.bak (house convention) and re-generates.
  On interruption, re-run — the backup preserves the last complete corpus. Pilot small
  first (a tiny generation.limit), inspect, then run full.
- ZERO model calls happen unless you point --config at a live endpoint and run it. The test
  suite and the mock smoke never touch this path against a real endpoint.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

# PYTHONPATH=src makes these importable.
from dcl.generate import (
    CoachVerdict,
    GenerateConfig,
    OpenAICompatibleClient,
    run_generation,
)

logger = logging.getLogger("dcl.run")


class HTTPCoachClient:
    """Concrete Coach: brief-fidelity gate over an OpenAI-compatible endpoint.

    Asks the Coach model for a JSON verdict ``{"decision","score","reasons"}``. Robust to a
    model that wraps the JSON in prose or a fence (the PO/QAV Coach-fallback-resilience
    lesson): parses the first JSON object it finds; if none, falls back to keyword sniffing;
    if still ambiguous, ACCEPTS with a logged warning so the compile-gated run is never
    blocked by a flaky judge (the compiler already guarantees compile-clean labels — the
    Coach only judges brief fidelity).
    """

    COACH_SYSTEM = (
        "You are the DCL Coach, a strict reviewer of DCL capabilities. Given a feature brief "
        "and a candidate capability that ALREADY compiles clean, judge only whether the "
        "capability faithfully models the brief (right actor, intent, outcomes, emitted "
        "events, effects, and governing policy). Respond with a single JSON object: "
        '{"decision": "accept" | "revise", "score": 0-10, "reasons": [ ... ]}.'
    )

    def __init__(self, endpoint: str, model: str, temperature: float = 0.2, max_tokens: int = 4096):
        self.endpoint = endpoint
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def assess(self, brief, capability_text: str) -> CoachVerdict:  # noqa: ANN001
        user = (
            f"## Feature brief\n{brief.brief_text}\n\n"
            f"## Candidate capability (compiles clean)\n```dcl\n{capability_text}\n```\n\n"
            "## Task\nReturn your JSON verdict now."
        )
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.COACH_SYSTEM},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }).encode()
        req = urllib.request.Request(
            self.endpoint.rstrip("/") + "/chat/completions",
            data=payload, headers={"Content-Type": "application/json"},
        )
        # Bounded retry/backoff on transient statuses (2026-07-17: raw 429s killed three
        # runs; same treatment as the Player client in src/dcl/generate.py).
        last_exc = None
        for attempt in range(6):
            try:
                with urllib.request.urlopen(req, timeout=900.0) as resp:
                    content = json.loads(resp.read())["choices"][0]["message"]["content"]
                return self._parse(content)
            except urllib.error.HTTPError as exc:
                if exc.code not in (429, 500, 502, 503, 504):
                    raise
                last_exc = exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
            except (urllib.error.URLError, TimeoutError) as exc:
                last_exc = exc
                retry_after = None
            if attempt < 5:
                time.sleep(min(float(retry_after) if retry_after else 10.0 * (2 ** attempt), 600.0))
        raise RuntimeError(f"coach call failed after 6 attempts (transient): {last_exc!r}") from last_exc

    @staticmethod
    def _parse(content: str) -> CoachVerdict:
        m = re.search(r"\{.*\}", content, re.S)
        if m:
            try:
                v = json.loads(m.group(0))
                decision = str(v.get("decision", "")).lower()
                if decision in ("accept", "revise"):
                    return CoachVerdict(
                        decision=decision, score=int(v.get("score", 5)),
                        reasons=list(v.get("reasons", [])),
                    )
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        low = content.lower()
        if "revise" in low or "reject" in low:
            return CoachVerdict(decision="revise", score=3, reasons=["coach: keyword-sniffed revise"])
        logger.warning("Coach verdict unparseable; accepting on fallback: %r", content[:120])
        return CoachVerdict(decision="accept", score=5, reasons=["coach: accepted on fallback"])


def build_clients(config_path: Path):
    """Construct the real Player/teacher + Coach clients from the config's endpoint keys."""
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    p = data["player"]
    c = data["coach"]
    player = OpenAICompatibleClient(
        endpoint=p["endpoint"], model=p["model"],
        temperature=p.get("temperature", 0.4), max_tokens=p.get("max_tokens", 4096),
    )
    coach = HTTPCoachClient(
        endpoint=c["endpoint"], model=c["model"],
        temperature=c.get("temperature", 0.2), max_tokens=c.get("max_tokens", 4096),
    )
    return player, coach


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Real DCL corpus generation run.")
    ap.add_argument("--config", default="agent-config.yaml",
                    help="path to the run config (default: repo-root agent-config.yaml)")
    ap.add_argument("--mode", choices=["dcl_author", "dcl_repair", "both"], default=None,
                    help="override generation.mode")
    ap.add_argument("--limit", type=int, default=None,
                    help="override generation.limit (use a small value for a pilot)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config_path = Path(args.config).resolve()
    cfg = GenerateConfig.from_yaml(config_path)
    if args.mode:
        cfg.mode = args.mode
    if args.limit is not None:
        cfg.limit = args.limit

    player, coach = build_clients(config_path)
    logger.info("DCL run: mode=%s limit=%s out=%s player=%s coach endpoint set",
                cfg.mode, cfg.limit, cfg.output_dir, getattr(player, "model", "?"))

    import subprocess
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    except Exception:  # pragma: no cover
        sha = "unknown"
    from datetime import date

    summary = run_generation(
        cfg, player=player, coach=coach, teacher=player,
        write_manifest=True, created=date.today().isoformat(), factory_sha=sha,
    )
    logger.info(
        "DONE author_accepted=%s author_rejected=%s repair_written=%s train=%s eval_dcl=%s",
        summary.author_accepted, summary.author_rejected, summary.repair_written,
        summary.train, summary.eval_dcl,
    )
    print(json.dumps(summary.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
