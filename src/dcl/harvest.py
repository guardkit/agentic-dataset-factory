"""Harvested-brief loading for the DCL corpus (W2c) — real plan-commit briefs → author rows.

Every factory run's plan-commit leg can append the feature's raw spec inputs to a capture
queue (``.guardkit/dcl-capture/queue.jsonl``), one JSON object per line. This module reads
that queue OFFLINE (in the corpus generator, where the seat is free) and turns the
``kind == "brief"`` rows into author-ready briefs that flow through the EXISTING author+repair
machinery — Rich's "more training data at zero in-run cost."

Two disciplines, both mechanical and non-negotiable (handoff §0 laws 5 + 7):

- **M-22 refuse-on-hit, per brief.** BEFORE a harvested brief can become a training row, the
  frozen-exam contamination denylist (``dcl.contamination.scan``) runs over its natural-language
  request + machine criteria. ANY hit REFUSES that brief loudly (skip-loud): it is recorded in
  the returned rejects list with the hit detail and NEVER yielded — zero rows from a refused
  brief. A refusal never aborts the batch (per-row refuse, not a fatal stop).
- **Malformed is counted, never fatal.** A line that is not JSON, not an object, or a brief
  missing a required field is counted + logged and recorded in the rejects list; the batch
  continues. ``kind == "compile_shadow"`` (and any non-``brief`` kind) is ignored silently — it
  shares the queue but is not the brief harvest's concern.

A :class:`HarvestedBrief` duck-types only the AUTHOR-path surface of :class:`dcl.briefs.Brief`
(``id`` + ``brief_text``). It carries NO structured synthetic fields, so it can drive
author-row minting but NOT repair minting (``render_reference_capability`` needs those fields);
``harvested = True`` marks it for the generator's author-only routing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from dcl import contamination

logger = logging.getLogger(__name__)

# The brief harvest ignores every non-brief queue kind (compile_shadow shares the queue).
BRIEF_KIND = "brief"
_REQUIRED_BRIEF_FIELDS = ("correlation_id", "feature_id", "request_text")


@dataclass(frozen=True)
class HarvestedBrief:
    """A real feature brief harvested from a factory run's plan-commit capture queue.

    Duck-types the AUTHOR-path surface of :class:`dcl.briefs.Brief` (``id`` + ``brief_text``)
    with NO structured synthetic fields. ``harvested`` is the marker the generator routes on
    (author-only — harvested briefs cannot mint repair rows).
    """

    correlation_id: str
    feature_id: str
    request_text: str
    machine_criteria: str = ""
    repo: str = ""
    task_id: str | None = None
    harvested: bool = True

    @property
    def id(self) -> str:  # noqa: A003 - duck-types Brief.id
        return f"harvest-{self.correlation_id}-{self.feature_id}"

    @property
    def brief_text(self) -> str:
        """The AUTHOR user message body: the request + a readable rendering of the criteria."""
        text = self.request_text.strip()
        criteria = self.machine_criteria.strip()
        if criteria:
            text = f"{text}\n\n## Machine acceptance criteria\n{criteria}"
        return text


def load_harvested_briefs(
    queue_path: str | Path,
    *,
    denylist_scan: Callable[[str], list[str]] = contamination.scan,
) -> tuple[list[HarvestedBrief], list[dict[str, Any]]]:
    """Parse a plan-commit capture queue into ``(accepted, rejects)``.

    ``accepted`` are M-22-clean :class:`HarvestedBrief` objects ready for the author path.
    ``rejects`` is a list of dicts, each carrying a ``reason`` discriminator:

    - ``reason == "contaminated"``: a brief that hit the denylist — ``hits`` names the detail.
    - ``reason == "malformed"``: an unparseable / non-object / field-missing line — ``line`` +
      ``error`` name the detail.

    Non-``brief`` kinds (e.g. ``compile_shadow``) are ignored and appear in neither list.
    """
    accepted: list[HarvestedBrief] = []
    rejects: list[dict[str, Any]] = []
    path = Path(queue_path)
    text = path.read_text(encoding="utf-8")

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning("harvest queue %s line %d malformed JSON (skipped): %s", path, lineno, exc)
            rejects.append({"reason": "malformed", "line": lineno, "error": f"json: {exc}"})
            continue
        if not isinstance(obj, dict):
            logger.warning("harvest queue %s line %d is not a JSON object (skipped)", path, lineno)
            rejects.append({"reason": "malformed", "line": lineno, "error": "not a JSON object"})
            continue
        kind = obj.get("kind")
        is_brief = kind == BRIEF_KIND or (
            # forge's plan-commit harvest writer stamps ``source`` but no
            # ``kind`` (first real row 2026-07-18, FEAT-B9AE); accept its
            # rows by the source discriminator so both writers' schemas load.
            kind is None
            and obj.get("source") == "plan-commit-harvest"
        )
        if not is_brief:
            # compile_shadow + any other kind share the queue but are not the brief harvest.
            continue
        missing = [f for f in _REQUIRED_BRIEF_FIELDS if obj.get(f) in (None, "")]
        if missing:
            logger.warning(
                "harvest queue %s line %d brief missing %s (skipped)", path, lineno, missing
            )
            rejects.append({"reason": "malformed", "line": lineno, "error": f"missing fields {missing}"})
            continue

        correlation_id = str(obj["correlation_id"])
        feature_id = str(obj["feature_id"])
        request_text = str(obj["request_text"])
        machine_criteria = str(obj.get("machine_criteria") or "")
        repo = str(obj.get("repo") or "")
        task_id = obj.get("task_id")

        # M-22 GATE — scan the request + machine criteria BEFORE it can become a row.
        hits = denylist_scan(f"{request_text}\n{machine_criteria}")
        if hits:
            logger.warning(
                "harvest brief %s/%s from %s REFUSED (contamination): %s",
                correlation_id, feature_id, repo or "<unknown repo>", "; ".join(hits),
            )
            rejects.append({
                "reason": "contaminated",
                "correlation_id": correlation_id,
                "feature_id": feature_id,
                "repo": repo,
                "hits": hits,
            })
            continue

        accepted.append(HarvestedBrief(
            correlation_id=correlation_id,
            feature_id=feature_id,
            request_text=request_text,
            machine_criteria=machine_criteria,
            repo=repo,
            task_id=str(task_id) if task_id is not None else None,
        ))

    refused = sum(1 for r in rejects if r["reason"] == "contaminated")
    malformed = sum(1 for r in rejects if r["reason"] == "malformed")
    logger.info(
        "harvest queue %s: %d accepted, %d refused (contamination), %d malformed",
        path, len(accepted), refused, malformed,
    )
    return accepted, rejects
