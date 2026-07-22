#!/usr/bin/env python
"""Driver for a REAL recruiter-agent corpus generation run (attended, against the Spark llama-swap).

Run it under office-manager's own venv (so the office checkers import), pointing --config at this
domain's agent-config.yaml. Two phases:

  GENERATE (default) — author + accept rows, STREAMING them (crash-safe, append-per-row) into a
    staging run dir under ``pilot-runs/`` (``--run-dir NAME``; default ``run-<UTC timestamp>``). The
    teacher is a served seat named in the config; the office's OWN checkers decide admission (never
    the model). A re-run against the same ``--run-dir`` resumes and appends without duplicating.

  FREEZE (``--freeze RUNDIR [RUNDIR ...]``) — assemble the frozen ``corpus/`` (train.jsonl +
    val.jsonl + manifest.json) ONCE from one or more staging run dirs: global dedup by row_id and a
    real, per-class-stratified, deterministic-by-row_id ~10% held-out val split.

Generation logs are written under ``<domain>/run_logs/`` (never the repo-root shared run_logs/).
Datasets are PRIVATE (DF-008).

    # from the office-manager repo root (the venv that carries office_manager + deckhand):
    DOMAIN=$HOME/Projects/appmilla_github/agentic-dataset-factory/domains/recruiter-agent
    OFFICE_AGENTS_ROOT=/tmp PYTHONPATH=$DOMAIN ./.venv/bin/python $DOMAIN/run_recruiter_generation.py \\
        --config $DOMAIN/agent-config.yaml --author-reps 12 --run-dir run-full
    # then freeze the frozen corpus:
    OFFICE_AGENTS_ROOT=/tmp PYTHONPATH=$DOMAIN ./.venv/bin/python $DOMAIN/run_recruiter_generation.py \\
        --config $DOMAIN/agent-config.yaml --freeze $DOMAIN/pilot-runs/run-full
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# allow running from anywhere: this domain dir is importable for its sibling modules.
DOMAIN_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DOMAIN_DIR))

from generate import GenConfig, freeze_corpus, run_generation  # noqa: E402


def _setup_logging(tag: str) -> Path:
    """Console + a file log under <domain>/run_logs/ (hardening: never the repo-root run_logs/)."""
    log_dir = DOMAIN_DIR / "run_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    log_path = log_dir / f"recruiter_{tag}_{ts}.log"
    handlers = [logging.StreamHandler(sys.stderr), logging.FileHandler(log_path, encoding="utf-8")]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers)
    return log_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Real recruiter-agent corpus generation / freeze.")
    ap.add_argument("--config", required=True, help="path to agent-config.yaml")
    ap.add_argument("--limit", type=int, default=None, help="cap the work list (a pilot)")
    ap.add_argument("--sample-per-class", type=int, default=None,
                    help="take the first K briefs from EACH class (a cross-class pilot)")
    ap.add_argument("--author-reps", type=int, default=None, help="override generation.author_reps")
    ap.add_argument("--player-model", default=None,
                    help="override the teacher seat (e.g. workhorse)")
    ap.add_argument("--run-dir", default=None,
                    help="staging run dir NAME under pilot-runs/ (default run-<UTC ts>)")
    ap.add_argument("--freeze", nargs="+", default=None, metavar="RUNDIR",
                    help="FREEZE mode: assemble corpus/ from these staging run dirs (paths or names under pilot-runs/)")
    args = ap.parse_args(argv)

    cfg = GenConfig.from_yaml(Path(args.config).resolve())
    pilot_runs = DOMAIN_DIR / "pilot-runs"

    if args.freeze is not None:
        log_path = _setup_logging("freeze")
        run_dirs = [Path(p) if Path(p).is_absolute() or Path(p).exists() else pilot_runs / p for p in args.freeze]
        logging.getLogger("recruiter.gen").info("FREEZE: run_dirs=%s -> %s (log %s)",
                                                 [str(r) for r in run_dirs], cfg.output_dir, log_path)
        manifest = freeze_corpus(run_dirs, cfg.output_dir, cfg.holdout_fraction, seed=cfg.seed)
        print(json.dumps(manifest["counts"], indent=2))
        print("by_class:", json.dumps(manifest["by_class"], indent=2))
        return 0

    # GENERATE mode
    if args.player_model is not None:
        cfg.player_model = args.player_model
    if args.limit is not None:
        cfg.limit = args.limit
    if args.sample_per_class is not None:
        cfg.sample_per_class = args.sample_per_class
    if args.author_reps is not None:
        cfg.author_reps = args.author_reps

    run_name = args.run_dir or ("run-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
    run_dir = Path(run_name) if Path(run_name).is_absolute() else pilot_runs / run_name
    log_path = _setup_logging("gen")
    logging.getLogger("recruiter.gen").info(
        "GENERATE: player=%s@%s reps=%s sample_per_class=%s limit=%s run_dir=%s (log %s)",
        cfg.player_model, cfg.player_endpoint, cfg.author_reps, cfg.sample_per_class,
        cfg.limit, run_dir, log_path,
    )
    summary = run_generation(cfg, run_dir)
    print(json.dumps(summary.__dict__, indent=2))
    print(f"\nstaged in: {run_dir}\nfreeze with: --freeze {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
