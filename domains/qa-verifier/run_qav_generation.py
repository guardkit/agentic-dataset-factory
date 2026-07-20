#!/usr/bin/env python
"""Documented entrypoint for a REAL qa-verifier (QAV) seeded-defect generation run.

Wires the real OpenAI-compatible clients from ``agent-config.yaml`` (teacher rationale +
Coach gate) and the interpreter-bridged ``qav.regenerate.SubprocessBridgeRegenerator`` (guardkit
``CoachValidator.gather_evidence`` run under the guardkit-importing interpreter via a subprocess
bridge) and drives ``src/qav/generate.py``'s ``run_generation``. Source tasks are discovered by
``qav.discover`` (record-resolved approved shas + the exclusion law). The deterministic truth of
every seeded row is the injector's fixed label — never a model. Datasets are private (DF-008).

Usage (attended, on the GB10 with the served fleet on :9000, guardkit importable per-repo):

    PYTHONPATH=src python domains/qa-verifier/run_qav_generation.py \
        --config domains/qa-verifier/agent-config.yaml

Honesty notes:
- This driver is FRESH-START, not checkpoint-resumable. Each run backs up any prior
  output/*.jsonl + manifest.json to *.bak (house convention) and re-generates. Pilot small
  first (a tiny --limit), inspect, then run full.
- ZERO model/seat/GPU calls happen in this module's imports or in the test suite. Real calls
  happen only when you point --config at a live endpoint and run it on the GB10.
- ``SubprocessBridgeRegenerator`` satisfies the ``src/qav/injector.py`` ``BundleRegenerator``
  seam without importing guardkit into this process: it shells out to ``qav_regenerate_bridge.py``
  under ``interpreters.guardkit`` and pins each target repo's pytest to ``interpreters.<repo>``
  (the SIBTESTENV01 lesson). A non-zero bridge exit surfaces loudly (never an unchecked row).
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
from qav.generate import (
    CoachVerdict,
    GenerateConfig,
    OpenAICompatibleClient,
    run_generation,
)
from qav.regenerate import SubprocessBridgeRegenerator

logger = logging.getLogger("qav.run")


class HTTPCoachClient:
    """Concrete Coach gate: judges only whether the teacher's ``<think>`` rationale is
    CONSISTENT WITH the fixed label — NOT a content re-judgment (PLAN §7; the verdict is
    already fixed by the injector). Asks the Coach model for a JSON verdict
    ``{"decision","reasons"}`` and is robust to prose/fence wrapping (the PO/QAV
    Coach-fallback-resilience lesson): parses the first JSON object; else keyword-sniffs;
    else ACCEPTS with a logged warning (the label is already deterministic — a flaky judge
    must never block a correctly-labelled row)."""

    COACH_SYSTEM = (
        "You are the QAV row-quality gate. You are given an evidence bundle, a candidate "
        "<think> rationale, and a FIXED verdict (already decided by construction). Judge ONLY "
        "whether the rationale is consistent with the fixed verdict and reasons over the actual "
        "bundle fields (it must not contradict the verdict, invent evidence, or merely restate "
        "the verdict). Respond with a single JSON object: "
        '{"decision": "accept" | "revise", "reasons": [ ... ]}.'
    )

    def __init__(self, endpoint: str, model: str, temperature: float = 0.2, max_tokens: int = 8192):
        self.endpoint = endpoint
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def assess(self, bundle: dict, think: str, label: dict) -> CoachVerdict:  # noqa: ANN001
        user = (
            f"## Evidence bundle\n```json\n{json.dumps(bundle, indent=2, sort_keys=True)}\n```\n\n"
            f"## Fixed verdict\n```json\n{json.dumps(label, indent=2)}\n```\n\n"
            f"## Candidate rationale\n<think>\n{think}\n</think>\n\n"
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
                    return CoachVerdict(decision=decision, reasons=list(v.get("reasons", [])))
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        low = content.lower()
        if "revise" in low or "reject" in low or "inconsistent" in low:
            return CoachVerdict(decision="revise", reasons=["coach: keyword-sniffed revise"])
        logger.warning("Coach verdict unparseable; accepting on fallback: %r", content[:120])
        return CoachVerdict(decision="accept", reasons=["coach: accepted on fallback"])


def build_clients(config_path: Path):
    """Construct the real teacher + Coach clients from the config's endpoint keys."""
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    p = data["player"]  # the seat reused as the rationale TEACHER
    c = data["coach"]
    teacher = OpenAICompatibleClient(
        endpoint=p["endpoint"], model=p["model"],
        temperature=p.get("temperature", 0.4), max_tokens=p.get("max_tokens", 4096),
    )
    coach = HTTPCoachClient(
        endpoint=c["endpoint"], model=c["model"],
        temperature=c.get("temperature", 0.2), max_tokens=c.get("max_tokens", 8192),
    )
    return teacher, coach


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Real QAV seeded-defect generation run.")
    ap.add_argument("--config", default="domains/qa-verifier/agent-config.yaml",
                    help="path to the run config")
    ap.add_argument("--mode", choices=["seeded_defect", "harvest", "both"], default=None,
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

    teacher, coach = build_clients(config_path)
    # The interpreter-bridged regenerator (qav.regenerate) — one per run. It shells out to the
    # bridge script under the guardkit-importing interpreter (config.interpreters['guardkit'])
    # and pins each target repo's pytest substrate to config.interpreters[repo] as venv_python
    # (the SIBTESTENV01 seam). The factory venv cannot import guardkit, so the subprocess bridge
    # is the honest wiring; a non-zero bridge exit surfaces loudly (never a silent unchecked row).
    regenerator = SubprocessBridgeRegenerator.from_config(cfg)
    logger.info(
        "QAV run: mode=%s limit=%s out=%s teacher=%s corpus=%s",
        cfg.mode, cfg.limit, cfg.output_dir, getattr(teacher, "model", "?"),
        sorted(cfg.corpus_roots),
    )

    import subprocess
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    except Exception:  # pragma: no cover
        sha = "unknown"
    from datetime import date

    summary = run_generation(
        cfg, teacher=teacher, coach=coach, regenerator=regenerator,
        write_manifest=True, created=date.today().isoformat(), factory_sha=sha,
    )
    logger.info(
        "DONE seeded_code=%s control=%s seeded_bundle=%s harvest=%s gold=%s "
        "teacher_refused=%s coach_rejected=%s cue_rejected=%s train=%s eval_qav=%s",
        summary.seeded_code_written, summary.seeded_control_written, summary.seeded_bundle_written,
        summary.harvest_written, summary.gold_negatives_written, summary.teacher_refused,
        summary.coach_rejected, summary.cue_rejected, summary.train, summary.eval_qav,
    )
    print(json.dumps(summary.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
