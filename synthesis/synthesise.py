"""Orchestrator for synthesising training examples via the Claude API."""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic
import yaml
from pydantic import ValidationError

from synthesis.templates import select_template
from synthesis.validator import (
    DuplicateDetector,
    GenerationPlan,
    GenerationTarget,
    RejectionRecord,
    SplitTracker,
    TrainingExample,
    validate_example,
)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


class _JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON strings."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload: dict[str, Any] = {
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra"):
            payload.update(record.extra)
        return json.dumps(payload)


def _configure_logging() -> None:
    """Install JSON formatter on the root handler."""
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Plan loading
# ---------------------------------------------------------------------------


def load_plan(plan_path: Path) -> GenerationPlan:
    """Load and validate the generation plan from *plan_path*.

    Raises:
        SystemExit: if the file is missing or YAML/Pydantic validation fails.
    """
    if not plan_path.exists():
        logger.error(json.dumps({"error": "plan_not_found", "path": str(plan_path)}))
        raise FileNotFoundError(f"Generation plan not found: {plan_path}")

    try:
        raw = yaml.safe_load(plan_path.read_text())
    except yaml.YAMLError as exc:
        logger.error(json.dumps({"error": "yaml_parse_error", "detail": str(exc)}))
        raise

    try:
        return GenerationPlan.model_validate(raw)
    except ValidationError as exc:
        logger.error(json.dumps({"error": "plan_validation_error", "detail": str(exc)}))
        raise


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------


def _checkpoint_path(output_dir: Path) -> Path:
    return output_dir / ".checkpoint.json"


def load_checkpoint(output_dir: Path) -> dict[str, int]:
    """Return checkpoint dict or defaults if no checkpoint exists."""
    cp = _checkpoint_path(output_dir)
    if cp.exists():
        return json.loads(cp.read_text())
    return {"last_completed_index": -1, "accepted": 0, "rejected": 0}


def save_checkpoint(output_dir: Path, last_index: int, accepted: int, rejected: int) -> None:
    """Overwrite the checkpoint file atomically."""
    cp = _checkpoint_path(output_dir)
    cp.write_text(
        json.dumps(
            {"last_completed_index": last_index, "accepted": accepted, "rejected": rejected}
        )
    )


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _ensure_output_dirs(output_dir: Path) -> None:
    """Create output directories if they do not exist."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "rag_index").mkdir(parents=True, exist_ok=True)


def _resolve_route(route: str | None, output_dir: Path) -> Path:
    """Turn a route string from ValidationResult into an absolute Path."""
    if route is None:
        return output_dir / "train.jsonl"
    # route is like "output/train.jsonl" or "output/rag_index/knowledge.jsonl"
    parts = Path(route).parts
    # strip leading "output" segment so we can re-root under output_dir
    if parts[0] == "output":
        parts = parts[1:]
    return output_dir.joinpath(*parts)


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Append *record* as a JSON line to *path*, flushing immediately."""
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
        fh.flush()


def _write_rejected(
    output_dir: Path,
    target: GenerationTarget,
    reason: str,
    raw_response: str | None = None,
) -> None:
    record = RejectionRecord(
        target=target,
        reason=reason,
        raw_response=raw_response,
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
    )
    _append_jsonl(output_dir / "rejected.jsonl", record.model_dump())


# ---------------------------------------------------------------------------
# JSON extraction from Claude response
# ---------------------------------------------------------------------------

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object from *text*, handling markdown fences."""
    # Strip markdown code fences if present
    stripped = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    stripped = re.sub(r"```\s*$", "", stripped, flags=re.MULTILINE)
    match = _JSON_RE.search(stripped)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Claude API call with retry
# ---------------------------------------------------------------------------

_MODEL = "claude-sonnet-4-5-20250514"
_MAX_RETRIES = 3
_BACKOFF_SECONDS = [1, 2, 4]


def call_claude(
    client: anthropic.Anthropic,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Call the Claude API with exponential backoff on rate-limit errors.

    Returns the text content of the first message block.
    Raises anthropic.APIError for non-rate-limit errors after logging.
    """
    for attempt in range(_MAX_RETRIES):
        try:
            response = client.messages.create(
                model=_MODEL,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
        except anthropic.RateLimitError:
            if attempt < _MAX_RETRIES - 1:
                sleep_secs = _BACKOFF_SECONDS[attempt]
                logger.warning(
                    json.dumps(
                        {
                            "event": "rate_limit_retry",
                            "attempt": attempt + 1,
                            "sleep_seconds": sleep_secs,
                        }
                    )
                )
                time.sleep(sleep_secs)
            else:
                raise


# ---------------------------------------------------------------------------
# Main orchestration loop
# ---------------------------------------------------------------------------


def run(
    plan_path: Path,
    output_dir: Path,
    client: anthropic.Anthropic | None = None,
) -> None:
    """Run the full synthesis pipeline.

    Args:
        plan_path: Path to the generation-plan.yaml file.
        output_dir: Directory for output JSONL files and checkpoint.
        client: Optional pre-built Anthropic client (used in tests).
    """
    plan = load_plan(plan_path)
    targets = plan.generation_targets

    if not targets:
        logger.info(json.dumps({"event": "no_targets", "total": 0}))
        return

    _ensure_output_dirs(output_dir)
    checkpoint = load_checkpoint(output_dir)
    resume_from = checkpoint["last_completed_index"] + 1
    accepted = checkpoint["accepted"]
    rejected = checkpoint["rejected"]

    if client is None:
        client = anthropic.Anthropic()

    split_tracker = SplitTracker()
    duplicate_detector = DuplicateDetector()

    total_attempted = 0

    for idx, target in enumerate(targets):
        if idx < resume_from:
            continue

        # Build prompt
        template_fn = select_template(target)
        prompt_pair = template_fn(target)

        # Call API
        raw_response: str | None = None
        try:
            raw_response = call_claude(client, prompt_pair.system_prompt, prompt_pair.user_prompt)
        except anthropic.RateLimitError as exc:
            logger.error(
                json.dumps({"event": "rate_limit_exhausted", "target_index": idx, "error": str(exc)})
            )
            _write_rejected(output_dir, target, "api_error", None)
            rejected += 1
            save_checkpoint(output_dir, idx, accepted, rejected)
            total_attempted += 1
            continue
        except anthropic.APIError as exc:
            logger.error(
                json.dumps({"event": "api_error", "target_index": idx, "error": str(exc)})
            )
            _write_rejected(output_dir, target, "api_error", None)
            rejected += 1
            save_checkpoint(output_dir, idx, accepted, rejected)
            total_attempted += 1
            continue

        # Parse JSON
        parsed = extract_json(raw_response)
        if parsed is None:
            _write_rejected(output_dir, target, "malformed_content", raw_response)
            rejected += 1
            save_checkpoint(output_dir, idx, accepted, rejected)
            total_attempted += 1
            continue

        # Construct TrainingExample
        try:
            example = TrainingExample.model_validate(parsed)
        except ValidationError:
            _write_rejected(output_dir, target, "malformed_content", raw_response)
            rejected += 1
            save_checkpoint(output_dir, idx, accepted, rejected)
            total_attempted += 1
            continue

        # Validate
        result = validate_example(example, split_tracker, duplicate_detector)
        if not result.is_valid:
            _write_rejected(output_dir, target, result.reason or "invalid", raw_response)
            rejected += 1
            save_checkpoint(output_dir, idx, accepted, rejected)
            total_attempted += 1
            continue

        # Write to route
        route_path = _resolve_route(result.route, output_dir)
        _append_jsonl(route_path, example.model_dump())
        accepted += 1
        save_checkpoint(output_dir, idx, accepted, rejected)
        total_attempted += 1

        # Progress logging every 10 targets
        if total_attempted % 10 == 0:
            reasoning_pct, direct_pct = split_tracker.ratio()
            logger.info(
                json.dumps(
                    {
                        "event": "progress",
                        "total_attempted": total_attempted,
                        "accepted": accepted,
                        "rejected": rejected,
                        "reasoning_pct": round(reasoning_pct, 4),
                        "direct_pct": round(direct_pct, 4),
                    }
                )
            )

    # Final summary
    reasoning_pct, direct_pct = split_tracker.ratio()
    logger.info(
        json.dumps(
            {
                "event": "complete",
                "total_attempted": total_attempted,
                "accepted": accepted,
                "rejected": rejected,
                "reasoning_pct": round(reasoning_pct, 4),
                "direct_pct": round(direct_pct, 4),
            }
        )
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synthesise GCSE English training examples via the Claude API."
    )
    parser.add_argument(
        "--plan-path",
        type=Path,
        default=Path("domains/gcse-english-tutor/generation-plan.yaml"),
        help="Path to the generation plan YAML file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory for output JSONL files.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    _configure_logging()
    parser = _build_parser()
    args = parser.parse_args(argv)
    run(plan_path=args.plan_path, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
