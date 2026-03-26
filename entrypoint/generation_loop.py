"""Generation loop — Player-Coach adversarial cycle with DeepAgents SDK.

Implements ``run_generation_loop()``, the core sequential Player-Coach
adversarial loop that processes generation targets. This is the heart of
the pipeline.

The loop uses pre-instantiated DeepAgent instances (created by
``create_player()`` and ``create_coach()`` factories). The entrypoint
orchestrates target iteration, turn management, and resilience mechanisms.
DeepAgents SDK manages the agent's internal tool calling and conversation.

The orchestrator owns all writes — the Player generates content and the
Coach evaluates it, but only the orchestrator calls ``write_output`` after
Coach acceptance (TASK-TRF-005). This prevents the Player from bypassing
evaluation.

Architecture references:
    - ADR-ARCH-006: Sequential generation (one target at a time)
    - ADR-ARCH-007: Structured JSON progress logging
    - ADR-ARCH-010: Overnight run resilience (retry, timeout, checkpoint)
    - DDR-003: 3-turn limit default
    - ``docs/design/contracts/API-generation.md``
    - ``docs/design/contracts/API-entrypoint.md``
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from pydantic import ValidationError

from config.coach_verdict import CoachVerdict

if TYPE_CHECKING:
    from config.models import GenerationConfig
    from domain_config.models import GenerationTarget
    from entrypoint.checkpoint import CheckpointManager
    from entrypoint.output import OutputFileManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class GenerationResult:
    """Statistics returned after the generation loop completes.

    Attributes:
        total_targets: Number of targets actually processed (after start_index).
        accepted: Number of targets accepted by the Coach.
        rejected: Number of targets rejected (exhausted turns, timeout, or LLM failure).
        total_turns: Total Player-Coach cycles executed across all targets.
        elapsed_seconds: Wall-clock time for the entire loop.
    """

    total_targets: int
    accepted: int
    rejected: int
    total_turns: int
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_example_json(raw_content: str) -> str:
    """Extract a JSON example from the Player agent's response content.

    The Player may return the JSON embedded in markdown code fences or
    surrounded by explanatory text. This function extracts the JSON
    object that contains ``"messages"`` and ``"metadata"`` keys.

    Args:
        raw_content: Raw string content from the Player agent response.

    Returns:
        The extracted JSON string.

    Raises:
        ValueError: If no valid JSON object can be extracted.
    """
    content = raw_content.strip()

    # Try 1: Direct parse — content is already valid JSON
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return content
    except (json.JSONDecodeError, TypeError):
        pass

    # Try 2: Extract from markdown code fences (```json ... ``` or ``` ... ```)
    fence_pattern = re.compile(r"```(?:json)?\s*\n(.*?)```", re.DOTALL)
    for match in fence_pattern.finditer(content):
        candidate = match.group(1).strip()
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return candidate
        except (json.JSONDecodeError, TypeError):
            continue

    # Try 3: Find the first { ... } block that parses as valid JSON
    brace_depth = 0
    start_idx = None
    for i, ch in enumerate(content):
        if ch == "{":
            if brace_depth == 0:
                start_idx = i
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
            if brace_depth == 0 and start_idx is not None:
                candidate = content[start_idx : i + 1]
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict):
                        return candidate
                except (json.JSONDecodeError, TypeError):
                    start_idx = None

    raise ValueError(
        f"Failed to extract JSON example from Player response. "
        f"Raw content (first 200 chars): {raw_content[:200]!r}"
    )


def _parse_coach_verdict(raw_content: str) -> CoachVerdict:
    """Parse the Coach agent's response into a structured CoachVerdict.

    Attempts to extract JSON from the response content. The Coach may
    return the JSON embedded in markdown code fences, so we try to
    extract it.

    Args:
        raw_content: Raw string content from the Coach agent response.

    Returns:
        Parsed and validated CoachVerdict.

    Raises:
        ValueError: If the content cannot be parsed as a valid CoachVerdict.
    """
    content = raw_content.strip()

    # Strip markdown code fences if present
    if content.startswith("```"):
        lines = content.split("\n")
        # Remove first and last lines (```json and ```)
        json_lines = []
        in_fence = False
        for line in lines:
            if line.strip().startswith("```") and not in_fence:
                in_fence = True
                continue
            if line.strip() == "```" and in_fence:
                break
            if in_fence:
                json_lines.append(line)
        content = "\n".join(json_lines)

    try:
        return CoachVerdict.model_validate_json(content)
    except (ValidationError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Failed to parse Coach verdict from response: {exc}. "
            f"Raw content (first 200 chars): {raw_content[:200]!r}"
        ) from exc


async def _invoke_with_retry(
    agent: Any,
    input_data: dict[str, Any],
    *,
    max_retries: int,
    backoff_base: float,
) -> dict[str, Any]:
    """Invoke a DeepAgent with retry logic for transient failures.

    Uses exponential backoff between retries. Only retries on
    ``RuntimeError`` and ``OSError`` (typical transient LLM failures).

    Args:
        agent: DeepAgent instance (Player or Coach).
        input_data: Input dict to pass to ``agent.ainvoke()``.
        max_retries: Maximum number of retry attempts (0 = no retries).
        backoff_base: Base delay in seconds for exponential backoff.

    Returns:
        Agent response dict.

    Raises:
        RuntimeError: If all retries are exhausted.
        OSError: If all retries are exhausted.
    """
    last_exc: BaseException | None = None
    total_attempts = 1 + max_retries

    for attempt in range(total_attempts):
        try:
            return await agent.ainvoke(input_data)
        except (RuntimeError, OSError, TimeoutError, ValidationError) as exc:
            last_exc = exc
            if attempt < total_attempts - 1:
                delay = backoff_base ** attempt
                logger.warning(
                    "LLM call failed (attempt %d/%d): %s. Retrying in %.1fs",
                    attempt + 1,
                    total_attempts,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "LLM call failed after %d attempts: %s",
                    total_attempts,
                    exc,
                )

    raise last_exc  # type: ignore[misc]


def _build_rejection_record(
    target: GenerationTarget,
    target_index: int,
    rejection_history: list[dict[str, Any]],
    reason: str,
) -> dict[str, Any]:
    """Build a rejection record for writing to rejected.jsonl.

    Args:
        target: The generation target that was rejected.
        target_index: Zero-based index of the target.
        rejection_history: List of Coach verdict dicts from each turn.
        reason: Reason for rejection (e.g., "max_turns_exhausted",
            "timeout", "llm_failure").

    Returns:
        Dict suitable for JSON serialisation to rejected.jsonl.
    """
    return {
        "target_index": target_index,
        "category": target.category,
        "type": target.type,
        "reason": reason,
        "rejection_history": rejection_history,
    }


# ---------------------------------------------------------------------------
# Core loop
# ---------------------------------------------------------------------------


async def _process_single_target(
    player: Any,
    coach: Any,
    target: GenerationTarget,
    target_index: int,
    total_targets: int,
    config: GenerationConfig,
    output_manager: OutputFileManager,
    write_tool: Callable,
) -> tuple[bool, int, list[dict[str, Any]]]:
    """Process a single generation target through the Player-Coach cycle.

    The orchestrator owns all writes. After the Coach accepts an example,
    the orchestrator extracts the JSON from the Player's response and calls
    ``write_tool`` to persist it. If write validation fails, the example is
    treated as a rejection and the Player is asked to revise (TASK-TRF-005).

    Args:
        player: Player DeepAgent instance.
        coach: Coach DeepAgent instance.
        target: The generation target to process.
        target_index: Zero-based index of this target.
        total_targets: Total number of targets (for logging).
        config: Generation configuration.
        output_manager: Output file manager for writing results.
        write_tool: The ``write_output`` LangChain tool, called by the
            orchestrator after Coach acceptance.

    Returns:
        Tuple of (accepted: bool, turns_used: int, rejection_history: list).
    """
    rejection_history: list[dict[str, Any]] = []
    coach_feedback: str | None = None
    write_attempts = 0

    for turn in range(config.max_turns):
        # Build player input — include Coach feedback for revisions
        player_input: dict[str, Any] = {
            "messages": [
                {
                    "role": "user",
                    "content": _build_player_message(target, coach_feedback),
                }
            ]
        }

        # Player generates example (no write_output — RAG only)
        player_response = await _invoke_with_retry(
            player,
            player_input,
            max_retries=config.llm_retry_attempts,
            backoff_base=config.llm_retry_backoff,
        )
        player_content = player_response["messages"][-1].content

        # Coach evaluates example
        coach_input: dict[str, Any] = {
            "messages": [
                {
                    "role": "user",
                    "content": player_content,
                }
            ]
        }

        coach_response = await _invoke_with_retry(
            coach,
            coach_input,
            max_retries=config.llm_retry_attempts,
            backoff_base=config.llm_retry_backoff,
        )
        coach_content = coach_response["messages"][-1].content

        # Parse Coach verdict
        verdict = _parse_coach_verdict(coach_content)

        logger.info(
            "turn_complete: index=%d, turn=%d, decision=%s, score=%d",
            target_index,
            turn + 1,
            verdict.decision,
            verdict.score,
        )

        if verdict.is_accepted:
            # Extract JSON from Player response
            try:
                example_json = _extract_example_json(player_content)
            except ValueError as exc:
                logger.warning(
                    "JSON extraction failed after Coach acceptance: %s",
                    exc,
                )
                rejection_history.append(
                    {"extraction_error": str(exc), **verdict.model_dump()}
                )
                coach_feedback = (
                    f"Your response could not be parsed as valid JSON. "
                    f"Return the complete training example as a single JSON "
                    f"object with 'messages' and 'metadata' keys."
                )
                continue

            # ORCHESTRATOR writes — not the Player (TASK-TRF-005)
            write_result = write_tool.invoke({"example_json": example_json})
            if isinstance(write_result, str) and write_result.startswith("Error:"):
                # Write validation failed — track attempts (TASK-TRF-006)
                write_attempts += 1
                logger.warning(
                    "Write validation failed (attempt %d/%d): %s",
                    write_attempts,
                    config.max_write_attempts,
                    write_result,
                )
                rejection_history.append(
                    {"write_error": write_result, **verdict.model_dump()}
                )
                if write_attempts >= config.max_write_attempts:
                    logger.warning(
                        "Write failed %d times, rejecting target %d",
                        write_attempts,
                        target_index,
                    )
                    return False, turn + 1, rejection_history
                coach_feedback = (
                    f"Write validation failed: {write_result}. "
                    f"Revise the example to fix the validation error."
                )
                continue

            logger.info(
                "target_accepted: index=%d, turns=%d, score=%d",
                target_index,
                turn + 1,
                verdict.score,
            )
            return True, turn + 1, rejection_history

        # Not accepted — record rejection and prepare feedback for revision
        rejection_history.append(verdict.model_dump())
        coach_feedback = verdict.quality_assessment
        if verdict.issues:
            issue_texts = [
                f"- [{iss.severity}] {iss.criterion}: {iss.description} "
                f"(suggestion: {iss.suggestion})"
                for iss in verdict.issues
            ]
            coach_feedback += "\n\nIssues:\n" + "\n".join(issue_texts)

    # Exhausted all turns — target rejected
    return False, config.max_turns, rejection_history


def _build_player_message(
    target: GenerationTarget,
    coach_feedback: str | None,
) -> str:
    """Build the user message for the Player agent.

    Args:
        target: The generation target to process.
        coach_feedback: Optional Coach feedback from previous turn for revision.

    Returns:
        Formatted message string for the Player.
    """
    msg = (
        f"Generate a training example for:\n"
        f"  Category: {target.category}\n"
        f"  Type: {target.type}\n"
        f"  Count: {target.count}\n"
    )
    if coach_feedback:
        msg += (
            f"\n--- Coach Feedback (revise based on this) ---\n"
            f"{coach_feedback}\n"
            f"--- End Feedback ---\n"
        )
    return msg


async def run_generation_loop(
    player: Any,
    coach: Any,
    targets: list[GenerationTarget],
    config: GenerationConfig,
    checkpoint: CheckpointManager,
    output_manager: OutputFileManager,
    write_tool: Callable,
    start_index: int = 0,
) -> GenerationResult:
    """Run the sequential Player-Coach generation loop.

    Processes each target one at a time (ADR-ARCH-006). For each target:
    1. Player generates an example (DeepAgent handles RAG internally).
    2. Coach evaluates the example (returns structured JSON verdict).
    3. If accepted: orchestrator calls ``write_tool`` to persist.
    4. If rejected and turns remain: Player revises with Coach feedback.
    5. If rejected at max_turns: log to rejected.jsonl.

    The orchestrator owns all writes — the Player never calls
    ``write_output`` directly (TASK-TRF-005).

    After each target, a checkpoint is written for resume support.

    Args:
        player: Pre-instantiated Player DeepAgent.
        coach: Pre-instantiated Coach DeepAgent.
        targets: Full list of generation targets from GOAL.md.
        config: Generation loop configuration (max_turns, timeouts, retry).
        checkpoint: CheckpointManager for saving progress.
        output_manager: OutputFileManager with open file handles.
        write_tool: The ``write_output`` LangChain tool, called by the
            orchestrator after Coach acceptance.
        start_index: Index to start processing from (for resume support).

    Returns:
        GenerationResult with aggregate statistics.
    """
    start_time = time.monotonic()
    accepted_count = 0
    rejected_count = 0
    total_turns = 0

    # Slice targets from start_index for resume support
    targets_to_process = targets[start_index:]
    num_targets = len(targets_to_process)

    for i, target in enumerate(targets_to_process):
        absolute_index = start_index + i

        logger.info(
            "target_start: index=%d, total=%d, category=%s, type=%s",
            absolute_index,
            len(targets),
            target.category,
            target.type,
        )

        try:
            # Wrap target processing in per-target timeout (ADR-ARCH-010)
            target_accepted, turns_used, rejection_history = await asyncio.wait_for(
                _process_single_target(
                    player=player,
                    coach=coach,
                    target=target,
                    target_index=absolute_index,
                    total_targets=len(targets),
                    config=config,
                    output_manager=output_manager,
                    write_tool=write_tool,
                ),
                timeout=config.target_timeout,
            )

            total_turns += turns_used

            if target_accepted:
                accepted_count += 1
            else:
                rejected_count += 1
                # Write rejection record to rejected.jsonl
                record = _build_rejection_record(
                    target=target,
                    target_index=absolute_index,
                    rejection_history=rejection_history,
                    reason="max_turns_exhausted",
                )
                output_manager.rejected_fh.write(json.dumps(record) + "\n")
                output_manager.rejected_fh.flush()

                logger.info(
                    "target_rejected: index=%d, turns=%d",
                    absolute_index,
                    turns_used,
                )

        except asyncio.TimeoutError:
            # Per-target timeout: discard and continue (ADR-ARCH-010)
            rejected_count += 1
            total_turns += 1  # At least one turn was attempted

            record = _build_rejection_record(
                target=target,
                target_index=absolute_index,
                rejection_history=[],
                reason="timeout",
            )
            output_manager.rejected_fh.write(json.dumps(record) + "\n")
            output_manager.rejected_fh.flush()

            logger.warning(
                "target_rejected: index=%d, reason=timeout, timeout=%ds",
                absolute_index,
                config.target_timeout,
            )

        except (RuntimeError, OSError, ValidationError) as exc:
            # All LLM retries exhausted or malformed LLM response: discard
            # target, continue pipeline.  ValidationError catches cases where
            # vLLM returns tool_calls.args as a JSON string instead of a dict
            # (known issue with some model/parser combinations — TASK-REV-FRF2).
            rejected_count += 1
            total_turns += 1

            record = _build_rejection_record(
                target=target,
                target_index=absolute_index,
                rejection_history=[],
                reason=f"llm_failure: {exc}",
            )
            output_manager.rejected_fh.write(json.dumps(record) + "\n")
            output_manager.rejected_fh.flush()

            logger.error(
                "target_rejected: index=%d, reason=llm_failure, error=%s",
                absolute_index,
                exc,
            )

        # Checkpoint after each target (ADR-ARCH-010)
        checkpoint.save(absolute_index)

        # Progress logging every 50 targets
        if (i + 1) % 50 == 0:
            elapsed = time.monotonic() - start_time
            logger.info(
                "progress: accepted=%d, rejected=%d, remaining=%d, "
                "elapsed_hours=%.1f",
                accepted_count,
                rejected_count,
                num_targets - (i + 1),
                elapsed / 3600,
            )

    elapsed_seconds = time.monotonic() - start_time

    logger.info(
        "complete: accepted=%d, rejected=%d, total_turns=%d, "
        "elapsed_seconds=%.1f",
        accepted_count,
        rejected_count,
        total_turns,
        elapsed_seconds,
    )

    return GenerationResult(
        total_targets=num_targets,
        accepted=accepted_count,
        rejected=rejected_count,
        total_turns=total_turns,
        elapsed_seconds=elapsed_seconds,
    )


__all__ = ["GenerationResult", "run_generation_loop"]
