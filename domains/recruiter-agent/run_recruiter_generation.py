#!/usr/bin/env python
"""Driver for a REAL recruiter-agent corpus generation run (attended, against the Spark llama-swap).

Run it under office-manager's own venv (so the office checkers import), pointing --config at this
domain's agent-config.yaml. FRESH-START, not resumable — each run backs up any prior output to *.bak
and regenerates. The teacher is a served seat named in the config; the office's OWN checkers decide
admission (never the model). Datasets are PRIVATE (DF-008).

    # from the office-manager repo root (the venv that carries office_manager + deckhand):
    OFFICE_AGENTS_ROOT=/tmp DOMAIN=$HOME/Projects/appmilla_github/agentic-dataset-factory/domains/recruiter-agent
    PYTHONPATH=$DOMAIN ./.venv/bin/python $DOMAIN/run_recruiter_generation.py \\
        --config $DOMAIN/agent-config.yaml [--limit 20]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# allow running from anywhere: this domain dir is importable for its sibling modules.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate import GenConfig, run_generation  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Real recruiter-agent corpus generation run.")
    ap.add_argument("--config", required=True, help="path to agent-config.yaml")
    ap.add_argument("--limit", type=int, default=None, help="cap the work list (a pilot)")
    ap.add_argument("--sample-per-class", type=int, default=None,
                    help="take the first K briefs from EACH class (a cross-class pilot)")
    ap.add_argument("--author-reps", type=int, default=None, help="override generation.author_reps")
    ap.add_argument("--player-model", default=None,
                    help="override the teacher seat (e.g. gemma4-tutor when gpt-oss-120b is down)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = GenConfig.from_yaml(Path(args.config).resolve())
    if args.player_model is not None:
        cfg.player_model = args.player_model
    if args.limit is not None:
        cfg.limit = args.limit
    if args.sample_per_class is not None:
        cfg.sample_per_class = args.sample_per_class
    if args.author_reps is not None:
        cfg.author_reps = args.author_reps

    logging.getLogger("recruiter.gen").info(
        "run: player=%s@%s reps=%s limit=%s out=%s",
        cfg.player_model, cfg.player_endpoint, cfg.author_reps, cfg.limit, cfg.output_dir,
    )
    summary = run_generation(cfg)
    print(json.dumps(summary.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
