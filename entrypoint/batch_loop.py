"""Two-window batched-legs generation loop (batch mode).

Additive alternative driver to ``run_generation_loop()`` (which stays the
default — ADR-ARCH-006).  Batch mode exists because the Player/teacher and
Coach serving states can be MUTUALLY EXCLUSIVE: a large teacher (e.g. a
two-node tensor-parallel session) drains the llama-swap Coach fleet while
it serves, so per-row seat alternation is impossible, not merely slow.
The run is therefore split into two windows at the orchestration level:

- **Window 1** — ALL Player/teacher legs for the pending rows, each row's
  output checkpointed as it lands (append-only ``.batch_state.jsonl``).
  The pre-Coach format gate runs here too (it needs only the Player, and
  format retries want the teacher live).
- **Window boundary** — the run STOPS and prints an operator instruction.
  Serving posture changes (drain the teacher, revive the Coach fleet — or
  the reverse) are OPERATOR acts per the serving runbooks; this repo never
  edits serving config.
- **Window 2** — ALL Coach legs over the checkpointed outputs, then the
  existing acceptance path per row: verdict → think-tag normalisation →
  JSON extraction → ``validate_post_generation`` → orchestrator write.
  Rows the Coach sends back for revision become the next pass's window 1
  (bounded by ``max_turns`` passes, matching sequential semantics).

Each process invocation executes exactly ONE window then exits; the
operator resumes into the next window with ``--batch --resume`` (the
existing ``--resume`` flag, extended).  A crash mid-window loses at most
the in-flight row: resume replays the event log and redoes only rows
without a recorded leg.

The Player/teacher seat is a plain ``ModelConfig`` (``batch.teacher`` in
``agent-config.yaml``, falling back to ``player``) — no code here assumes
model names or endpoints.

References:
    - ADR-ARCH-006 (dated note 2026-08-14: the v2 revisit condition)
    - ADR-ARCH-010 (resilience mechanisms, reused per leg)
    - ``entrypoint/batch_state.py`` (event log / replay)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Literal

import httpx
from pydantic import ValidationError

from config.coach_verdict import CoachVerdict
from entrypoint.batch_state import (
    BatchRunState,
    BatchStateError,
    BatchStateManager,
)
from entrypoint.generation_loop import (
    CoachRefusalError,
    GenerationResult,
    TokenUsage,
    _assistant_fenced_json_valid,
    _build_player_message,
    _build_rejection_record,
    _extract_coach_content,
    _extract_example_json,
    _extract_json_object,
    _extract_player_content,
    _extract_token_usage,
    _invoke_coach_fallback,
    _invoke_with_retry,
    _parse_coach_verdict,
)
from synthesis.validator import normalise_think_closing_tags, validate_post_generation

if TYPE_CHECKING:
    from pathlib import Path

    from config.models import AgentConfig, GenerationConfig, ModelConfig
    from domain_config.models import GenerationTarget
    from entrypoint.output import OutputFileManager

logger = logging.getLogger(__name__)

RESUME_COMMAND = "python agent.py --batch --resume"


# ---------------------------------------------------------------------------
# Target collection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BatchRow:
    """One collected generation row with its deterministic assignments.

    Mode and grade round-robin use the absolute row index, exactly as the
    sequential loop assigns them, so a target produces the same prompt in
    either mode.

    Attributes:
        index: Absolute row index (stable across windows and resumes).
        target: The expanded generation target.
        mode: Round-robined generation mode, or None (Player's choice).
        grade_target: Round-robined grade target for this row.
    """

    index: int
    target: GenerationTarget
    mode: str | None
    grade_target: int | None


def collect_generation_targets(
    targets: list[GenerationTarget],
    config: GenerationConfig,
) -> list[BatchRow]:
    """Collect the run's generation rows with sequential-parity semantics.

    Mirrors ``run_generation_loop()`` exactly: expand each target by its
    ``count``; when ``config.limit`` caps the run, round-robin interleave
    across categories first so a small cap spans all categories; then
    assign mode (``config.modes`` round-robin by absolute index) and grade
    (``grade_targets`` round-robin by absolute index) per row.

    Args:
        targets: Generation targets from GOAL.md.
        config: Generation loop configuration.

    Returns:
        Ordered list of :class:`BatchRow`.
    """
    expanded = [target for target in targets for _ in range(target.count)]

    if getattr(config, "limit", None) is not None and config.limit < len(expanded):
        by_category: dict[str, list] = {}
        for t in expanded:
            by_category.setdefault(t.category, []).append(t)
        interleaved: list = []
        groups = list(by_category.values())
        idx = 0
        while len(interleaved) < len(expanded):
            group = groups[idx % len(groups)]
            offset = idx // len(groups)
            if offset < len(group):
                interleaved.append(group[offset])
            idx += 1
        logger.info(
            "targets_limited: cap=%d, from=%d, category_interleaved (pilot run)",
            config.limit,
            len(expanded),
        )
        expanded = interleaved[: config.limit]

    rows: list[BatchRow] = []
    for i, target in enumerate(expanded):
        mode = (
            config.modes[i % len(config.modes)]
            if getattr(config, "modes", None)
            else None
        )
        grade = target.grade_targets[i % len(target.grade_targets)]
        rows.append(BatchRow(index=i, target=target, mode=mode, grade_target=grade))

    logger.info(
        "targets_collected: categories=%d, total=%d (batch mode)",
        len({r.target.category for r in rows}),
        len(rows),
    )
    return rows


def target_fingerprint(rows: list[BatchRow]) -> str:
    """Deterministic identity of a collected target list.

    Recorded at run start and verified on resume, so a config change
    mid-run (different counts, limit, modes, or grades) is caught instead
    of silently mispairing checkpointed outputs with different targets.

    Args:
        rows: Collected batch rows.

    Returns:
        Hex digest string (16 chars).
    """
    payload = json.dumps(
        [
            [r.target.category, r.target.type, r.target.layer, r.mode, r.grade_target]
            for r in rows
        ],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def select_window1_model_config(config: AgentConfig) -> ModelConfig:
    """Resolve the window-1 Player/teacher seat's model configuration.

    The teacher seat rides the same ``ModelConfig`` seam as every agent:
    ``batch.teacher`` when set, else the ordinary ``player`` block.  No
    code assumes model names or endpoints.

    Args:
        config: Top-level agent configuration.

    Returns:
        The ``ModelConfig`` for the window-1 seat.
    """
    if config.batch.teacher is not None:
        return config.batch.teacher
    return config.player


# ---------------------------------------------------------------------------
# Outcome dataclass + operator instructions
# ---------------------------------------------------------------------------


@dataclass
class BatchWindowOutcome:
    """Result of one batch-mode process invocation (one window).

    Attributes:
        status: ``"paused"`` at a window boundary (operator acts next) or
            ``"complete"`` when the run has finished.
        window: The window that just ran (1 or 2).
        pass_number: The pass that window belonged to (1-based).
        operator_instruction: Human instruction printed at the boundary
            (empty when complete).
        result: Aggregate statistics, populated only when complete.
    """

    status: Literal["paused", "complete"]
    window: int
    pass_number: int
    operator_instruction: str = ""
    result: GenerationResult | None = None


def _window1_instruction(
    pass_number: int,
    checkpointed: int,
    failed: int,
    accepted_so_far: int,
    operator_note: str,
) -> str:
    """Operator instruction printed at the window-1 → window-2 boundary."""
    note = f"\nOperator note (from agent-config.yaml): {operator_note}" if operator_note else ""
    return (
        "=== BATCH WINDOW BOUNDARY ===\n"
        f"Window 1 (pass {pass_number}) COMPLETE: {checkpointed} Player/teacher "
        f"leg(s) checkpointed, {failed} row(s) failed (already in rejected.jsonl), "
        f"{accepted_so_far} accepted in earlier passes.\n"
        "The run has stopped cleanly at the window boundary.\n"
        "OPERATOR: switch the serving posture now — stop the window-1 teacher "
        "session and revive the Coach fleet, per the teacher's serving runbook "
        "(drain/revive acts are yours, never this repo's).\n"
        f"Then run window 2 (Coach legs) with:\n    {RESUME_COMMAND}"
        f"{note}"
    )


def _window2_instruction(
    pass_number: int,
    accepted: int,
    pending: int,
    operator_note: str,
) -> str:
    """Operator instruction printed at the window-2 → next-pass boundary."""
    note = f"\nOperator note (from agent-config.yaml): {operator_note}" if operator_note else ""
    return (
        "=== BATCH WINDOW BOUNDARY ===\n"
        f"Window 2 (pass {pass_number}) COMPLETE: {accepted} row(s) accepted so far, "
        f"{pending} row(s) pending revision.\n"
        "The run has stopped cleanly at the window boundary.\n"
        "OPERATOR: switch the serving posture now — drain the Coach fleet and "
        "start the teacher session, per the teacher's serving runbook "
        "(drain/revive acts are yours, never this repo's).\n"
        f"Then run window 1 of pass {pass_number + 1} (revision legs) with:\n"
        f"    {RESUME_COMMAND}"
        f"{note}"
    )


# ---------------------------------------------------------------------------
# Window 1 — Player/teacher legs
# ---------------------------------------------------------------------------


async def _player_leg(
    player: Any,
    row: BatchRow,
    config: GenerationConfig,
    coach_feedback: str | None,
    rag_tool: Callable | None,
    token_usage: TokenUsage,
) -> tuple[str | None, list[dict[str, Any]], str | None]:
    """Run one Player/teacher leg (with the pre-Coach format gate).

    Mirrors the sequential loop's Player side: orchestrator RAG pre-fetch,
    prompt build (mode/grade/feedback), invoke with retry, then the format
    gate with up to ``max_format_retries`` immediate re-prompts (the
    Player is live in this window; format repair needs no Coach).

    Args:
        player: Player/teacher DeepAgent instance.
        row: The batch row to generate.
        config: Generation configuration.
        coach_feedback: Feedback from the previous pass's Coach leg, if any.
        rag_tool: Optional ``rag_retrieval`` tool for context pre-fetch.
        token_usage: Cumulative token accumulator.

    Returns:
        ``(player_content, history, fail_reason)`` — content is ``None``
        with a reason when the leg failed terminally.
    """
    rag_context: str | None = None
    if rag_tool is not None:
        rag_query = f"{row.target.category} {row.target.type}"
        try:
            rag_context = rag_tool.invoke({"query": rag_query, "n_results": 5})
            if isinstance(rag_context, str) and rag_context.startswith("Error:"):
                logger.warning(
                    "RAG pre-fetch failed for index=%d: %s", row.index, rag_context
                )
                rag_context = None
        except Exception as exc:
            logger.warning("RAG pre-fetch exception for index=%d: %s", row.index, exc)
            rag_context = None

    history: list[dict[str, Any]] = []
    feedback = coach_feedback
    format_retries = 0
    attempt = 0

    while True:
        attempt += 1
        player_input: dict[str, Any] = {
            "messages": [
                {
                    "role": "user",
                    "content": _build_player_message(
                        row.target, feedback, rag_context, row.grade_target, row.mode
                    ),
                }
            ]
        }
        player_response = await _invoke_with_retry(
            player,
            player_input,
            max_retries=config.llm_retry_attempts,
            backoff_base=config.llm_retry_backoff,
        )
        player_content = _extract_player_content(player_response)
        p_prompt, p_completion = _extract_token_usage(player_response)
        if p_prompt or p_completion:
            token_usage.add(p_prompt, p_completion)
            logger.info(
                "LLM usage: agent=player, index=%d, attempt=%d, "
                "prompt_tokens=%d, completion_tokens=%d",
                row.index,
                attempt,
                p_prompt,
                p_completion,
            )

        # Pre-Coach format gate (same checks as the sequential loop).
        format_gate: str | None = None
        format_reason = ""
        format_feedback = ""
        try:
            extracted = _extract_json_object(player_content)
            data = json.loads(extracted)
            if "messages" not in data or "metadata" not in data:
                raise ValueError(
                    f"JSON missing required top-level keys (has: {sorted(data.keys())})"
                )
        except ValueError as exc:
            format_gate = "player_output_not_json"
            format_reason = str(exc)
            format_feedback = (
                "FORMAT ERROR: Your previous response could not be parsed "
                "as a valid JSON object with both 'messages' and 'metadata' "
                "top-level keys. You MUST respond with ONLY a raw JSON object "
                "containing both 'messages' (array) and 'metadata' (object). "
                "Start your response with { and end with }. "
                "Do NOT include any text before or after the JSON. "
                "Do NOT output messages and metadata as separate JSON objects."
            )

        if format_gate is None and getattr(config, "require_fenced_json", False):
            inner_ok, inner_reason = _assistant_fenced_json_valid(data)
            if not inner_ok:
                format_gate = "assistant_fenced_json_invalid"
                format_reason = inner_reason
                format_feedback = (
                    "FORMAT ERROR: The JSON object inside your assistant "
                    "message's ```json fenced block is not valid JSON "
                    f"({inner_reason}). Keep the same <think> block and the "
                    "same content, but emit the fenced object as STRICT JSON: "
                    "escape every newline/tab inside string values (\\n, \\t), "
                    "quote all keys, and add any missing commas. It must parse "
                    "with a strict JSON parser."
                )

        if format_gate is None:
            return player_content, history, None

        format_retries += 1
        logger.warning(
            "Pre-Coach format gate (%s): Player output rejected "
            "(index=%d, attempt=%d, reason=%s).",
            format_gate,
            row.index,
            attempt,
            format_reason,
        )
        history.append(
            {"format_gate": format_gate, "turn": attempt, "reason": format_reason}
        )
        if format_retries > config.max_format_retries:
            return None, history, "format_retries_exhausted"
        feedback = format_feedback


async def _run_window1(
    player: Any,
    rows: list[BatchRow],
    state: BatchRunState,
    config: GenerationConfig,
    mgr: BatchStateManager,
    output_manager: OutputFileManager,
    rag_tool: Callable | None,
    token_usage: TokenUsage,
) -> tuple[int, int]:
    """Run window 1: Player/teacher legs for every pending row.

    Each row's outcome is recorded (and fsynced) before the next row
    starts, so a crash loses at most the in-flight row.

    Returns:
        ``(checkpointed, failed)`` row counts for this window.
    """
    pending = state.pending_player_indices()
    row_by_index = {r.index: r for r in rows}
    checkpointed = 0
    failed = 0

    logger.info(
        "window1_start: pass=%d, pending_rows=%d", state.pass_number, len(pending)
    )

    for idx in pending:
        row = row_by_index[idx]
        feedback = state.rows[idx].coach_feedback
        logger.info(
            "window1_row_start: index=%d, category=%s, type=%s, mode=%s, pass=%d",
            idx,
            row.target.category,
            row.target.type,
            row.mode or "player-choice",
            state.pass_number,
        )
        content: str | None = None
        history: list[dict[str, Any]] = []
        fail_reason: str | None = None
        try:
            content, history, fail_reason = await asyncio.wait_for(
                _player_leg(player, row, config, feedback, rag_tool, token_usage),
                timeout=config.target_timeout,
            )
        except asyncio.TimeoutError:
            fail_reason = "timeout"
        except (
            RuntimeError,
            OSError,
            ValidationError,
            ValueError,
            httpx.HTTPStatusError,
        ) as exc:
            fail_reason = f"llm_failure: {exc}"

        if content is not None:
            checkpointed += 1
            mgr.record(
                "player_done",
                index=idx,
                **{"pass": state.pass_number},
                status="ok",
                player_content=content,
            )
        else:
            failed += 1
            record = _build_rejection_record(
                target=row.target,
                target_index=idx,
                rejection_history=history,
                reason=fail_reason or "unknown",
            )
            output_manager.rejected_fh.write(json.dumps(record) + "\n")
            output_manager.rejected_fh.flush()
            mgr.record(
                "player_done",
                index=idx,
                **{"pass": state.pass_number},
                status="failed",
                reason=fail_reason or "unknown",
            )
            logger.warning(
                "window1_row_failed: index=%d, reason=%s", idx, fail_reason
            )

    mgr.record("window1_complete", **{"pass": state.pass_number})
    logger.info(
        "window1_complete: pass=%d, checkpointed=%d, failed=%d",
        state.pass_number,
        checkpointed,
        failed,
    )
    return checkpointed, failed


# ---------------------------------------------------------------------------
# Window 2 — Coach legs + acceptance path
# ---------------------------------------------------------------------------


def _select_for_layer(agent: Any, target: GenerationTarget) -> Any:
    """Resolve a layer-keyed Coach dict to the agent for *target*'s layer."""
    if isinstance(agent, dict):
        layer = getattr(target, "layer", "behaviour")
        return agent.get(layer, agent.get("behaviour"))
    return agent


async def _coach_leg(
    coach: Any,
    coach_fallback: Any | None,
    row: BatchRow,
    player_content: str,
    config: GenerationConfig,
    token_usage: TokenUsage,
) -> CoachVerdict:
    """Run one Coach evaluation over a checkpointed Player output.

    Mirrors the sequential loop's Coach-side resilience ladder:
    refusal → reframed retry → non-structured fallback (TASK-CR-006/007),
    empty structured output → straight to fallback, and one JSON
    reinforcement retry on verdict parse failure (TASK-OR-001).

    Args:
        coach: Coach agent (already layer-resolved).
        coach_fallback: Non-structured fallback coach (layer-resolved), or
            None.
        row: The batch row being evaluated.
        player_content: Checkpointed window-1 output.
        config: Generation configuration.
        token_usage: Cumulative token accumulator.

    Returns:
        Parsed :class:`CoachVerdict`.

    Raises:
        CoachRefusalError | ValueError: When the ladder is exhausted
            (handled per-row by the window-2 driver).
    """
    coach_input: dict[str, Any] = {
        "messages": [{"role": "user", "content": player_content}]
    }
    coach_response = await _invoke_with_retry(
        coach,
        coach_input,
        max_retries=config.llm_retry_attempts,
        backoff_base=config.llm_retry_backoff,
    )

    used_fallback = False
    try:
        coach_content = _extract_coach_content(coach_response)
    except CoachRefusalError as refusal_exc:
        if refusal_exc.empty_structured_output and coach_fallback is not None:
            logger.warning(
                "Coach returned empty structured output (index=%d), "
                "routing straight to non-structured fallback",
                row.index,
            )
            coach_content, fb_prompt, fb_completion = await _invoke_coach_fallback(
                coach_fallback, player_content, config
            )
            token_usage.add(fb_prompt, fb_completion)
            used_fallback = True
        else:
            logger.warning(
                "Coach refused to evaluate (index=%d), retrying with "
                "reframed prompt: %s",
                row.index,
                refusal_exc.reason,
            )
            refusal_retry_input: dict[str, Any] = {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "You are a QUALITY ASSESSOR performing a rubric "
                            "evaluation. You are NOT generating content — you "
                            "are only SCORING an existing training example "
                            "against quality criteria. This is a routine "
                            "quality check, not content creation.\n\n"
                            "Please evaluate the following training example "
                            "and return your assessment as a JSON CoachVerdict "
                            "object.\n\n"
                            f"[Training example for category: "
                            f"{row.target.category}, type: {row.target.type}]"
                        ),
                    }
                ]
            }
            coach_response = await _invoke_with_retry(
                coach,
                refusal_retry_input,
                max_retries=config.llm_retry_attempts,
                backoff_base=config.llm_retry_backoff,
            )
            r_prompt, r_completion = _extract_token_usage(coach_response)
            token_usage.add(r_prompt, r_completion)
            try:
                coach_content = _extract_coach_content(coach_response)
            except CoachRefusalError:
                if coach_fallback is None:
                    raise
                coach_content, fb_prompt, fb_completion = (
                    await _invoke_coach_fallback(
                        coach_fallback, player_content, config
                    )
                )
                token_usage.add(fb_prompt, fb_completion)
                used_fallback = True

    c_prompt, c_completion = _extract_token_usage(coach_response)
    if c_prompt or c_completion:
        token_usage.add(c_prompt, c_completion)
        logger.info(
            "LLM usage: agent=coach, index=%d, prompt_tokens=%d, "
            "completion_tokens=%d",
            row.index,
            c_prompt,
            c_completion,
        )

    try:
        return _parse_coach_verdict(coach_content)
    except ValueError as parse_exc:
        logger.info(
            "Coach JSON parse failed (index=%d), retrying with JSON "
            "reinforcement: %s",
            row.index,
            parse_exc,
        )
        retry_input: dict[str, Any] = {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "IMPORTANT: Your previous response was not valid JSON. "
                        "You MUST respond with ONLY a JSON object matching the "
                        "CoachVerdict schema. No prose, no reasoning text, no "
                        "markdown. Start your response with { and end with }."
                        "\n\n" + player_content
                    ),
                },
            ]
        }
        retry_coach = (
            coach_fallback if used_fallback and coach_fallback is not None else coach
        )
        coach_response = await _invoke_with_retry(
            retry_coach,
            retry_input,
            max_retries=config.llm_retry_attempts,
            backoff_base=config.llm_retry_backoff,
        )
        r_prompt, r_completion = _extract_token_usage(coach_response)
        token_usage.add(r_prompt, r_completion)
        coach_content = _extract_coach_content(coach_response)
        return _parse_coach_verdict(coach_content)


async def _run_window2(
    coach: Any,
    coach_fallback: Any | None,
    rows: list[BatchRow],
    state: BatchRunState,
    config: GenerationConfig,
    mgr: BatchStateManager,
    output_manager: OutputFileManager,
    write_tool: Callable,
    token_usage: TokenUsage,
) -> tuple[int, int, int]:
    """Run window 2: Coach legs + acceptance path over checkpointed rows.

    Each row's verdict outcome is recorded (and fsynced) before the next
    row starts.  Accepted rows go through the existing acceptance path
    (think-tag normalisation → JSON extraction → post-generation
    validation → orchestrator write); any failure in that path routes the
    row back to revision with the same feedback strings the sequential
    loop uses.  The accepting verdict is pinned to the log
    (``accept_pending``) BEFORE the write, so a crash in the write gap
    resumes as a redo of only the write — the Coach is never re-consulted
    for a row whose verdict already landed.

    Returns:
        ``(accepted, revise, rejected)`` row counts for this window.
    """
    awaiting = state.awaiting_coach_indices()
    row_by_index = {r.index: r for r in rows}
    accepted = 0
    revise = 0
    rejected = 0

    logger.info(
        "window2_start: pass=%d, awaiting_rows=%d", state.pass_number, len(awaiting)
    )

    # Finish rows whose accepting verdict was recorded but whose write was
    # interrupted (crash between ``accept_pending`` and ``coach_done``):
    # redo ONLY the write from the checkpointed content.  Extraction and
    # validation are deterministic over that content, so the redo reaches
    # the same example JSON the pre-crash invocation validated.
    for idx in state.accept_pending_indices():
        player_content = state.rows[idx].player_content or ""
        example_json, feedback = _validate_accepted_row(player_content, idx)
        if example_json is not None:
            feedback = _write_accepted_row(write_tool, example_json, idx)
        if feedback is None:
            accepted += 1
            mgr.record(
                "coach_done",
                index=idx,
                **{"pass": state.pass_number},
                status="accepted",
            )
        else:
            revise += 1
            mgr.record(
                "coach_done",
                index=idx,
                **{"pass": state.pass_number},
                status="revise",
                coach_feedback=feedback,
            )

    for idx in awaiting:
        row = row_by_index[idx]
        player_content = state.rows[idx].player_content or ""
        row_coach = _select_for_layer(coach, row.target)
        row_fallback = _select_for_layer(coach_fallback, row.target)

        try:
            verdict = await asyncio.wait_for(
                _coach_leg(
                    row_coach, row_fallback, row, player_content, config, token_usage
                ),
                timeout=config.target_timeout,
            )
        except asyncio.TimeoutError:
            rejected += 1
            _reject_row(mgr, output_manager, row, state.pass_number, "timeout", [])
            continue
        except CoachRefusalError as exc:
            rejected += 1
            _reject_row(
                mgr,
                output_manager,
                row,
                state.pass_number,
                f"coach_refusal: {exc.reason}",
                [],
            )
            continue
        except (
            RuntimeError,
            OSError,
            ValidationError,
            ValueError,
            httpx.HTTPStatusError,
        ) as exc:
            rejected += 1
            _reject_row(
                mgr,
                output_manager,
                row,
                state.pass_number,
                f"llm_failure: {exc}",
                [],
            )
            continue

        logger.info(
            "window2_verdict: index=%d, pass=%d, decision=%s, score=%d",
            idx,
            state.pass_number,
            verdict.decision,
            verdict.score,
        )

        if verdict.is_accepted:
            example_json, feedback = _validate_accepted_row(player_content, idx)
            if example_json is not None:
                # Pin the verdict BEFORE the write: a crash in the write
                # gap resumes as a write-only redo (see the loop above),
                # matching sequential's write-then-checkpoint at-least-once
                # semantics (ADR-ARCH-010) without a Coach re-evaluation.
                mgr.record(
                    "accept_pending", index=idx, **{"pass": state.pass_number}
                )
                feedback = _write_accepted_row(
                    write_tool, example_json, idx, score=verdict.score
                )
            if feedback is None:
                accepted += 1
                mgr.record(
                    "coach_done",
                    index=idx,
                    **{"pass": state.pass_number},
                    status="accepted",
                )
                continue
            # Acceptance-path failure — route to revision (next pass).
            revise += 1
            mgr.record(
                "coach_done",
                index=idx,
                **{"pass": state.pass_number},
                status="revise",
                coach_feedback=feedback,
            )
            continue

        # Coach sent the row back for revision.
        feedback = verdict.quality_assessment
        if verdict.issues:
            issue_texts = [
                f"- [{iss.severity}] {iss.criterion}: {iss.description} "
                f"(suggestion: {iss.suggestion})"
                for iss in verdict.issues
            ]
            feedback += "\n\nIssues:\n" + "\n".join(issue_texts)
        revise += 1
        mgr.record(
            "coach_done",
            index=idx,
            **{"pass": state.pass_number},
            status="revise",
            coach_feedback=feedback,
        )

    logger.info(
        "window2_complete: pass=%d, accepted=%d, revise=%d, rejected=%d",
        state.pass_number,
        accepted,
        revise,
        rejected,
    )
    return accepted, revise, rejected


def _validate_accepted_row(
    player_content: str,
    index: int,
) -> tuple[str | None, str | None]:
    """Extract and validate a Coach-accepted row's example JSON.

    Side-effect free and deterministic over the checkpointed content, so
    a crash-resume redo reaches exactly the JSON the pre-crash invocation
    validated.

    Args:
        player_content: Checkpointed Player output.
        index: Row index (for logging).

    Returns:
        ``(example_json, None)`` when valid, or ``(None, feedback)`` with
        a revision-feedback string when extraction / validation failed.
    """
    player_content = normalise_think_closing_tags(player_content)
    try:
        example_json = _extract_example_json(player_content)
    except ValueError as exc:
        logger.warning(
            "JSON extraction failed after Coach acceptance (index=%d): %s",
            index,
            exc,
        )
        return None, (
            "Your response could not be parsed as valid JSON. "
            "Return the complete training example as a single JSON "
            "object with 'messages' and 'metadata' keys."
        )

    post_gen_result = validate_post_generation(example_json)
    if not post_gen_result.is_valid:
        logger.warning(
            "Post-generation validation failed (index=%d): %s",
            index,
            post_gen_result.reason,
        )
        return None, (
            f"Post-generation validation failed: {post_gen_result.reason}. "
            f"Revise the example to fix this defect."
        )

    return example_json, None


def _write_accepted_row(
    write_tool: Callable,
    example_json: str,
    index: int,
    score: int | None = None,
) -> str | None:
    """Invoke the orchestrator write for a validated accepted row.

    Args:
        write_tool: The ``write_output`` tool (orchestrator-owned writes).
        example_json: The validated example JSON to write.
        index: Row index (for logging).
        score: Verdict score for logging; None on a crash-resume write
            redo (the verdict lives in the pre-crash log).

    Returns:
        ``None`` on success (row written), or a revision-feedback string
        when write validation failed.
    """
    write_result = write_tool.invoke({"example_json": example_json})
    if isinstance(write_result, str) and write_result.startswith("Error:"):
        logger.warning(
            "Write validation failed (index=%d): %s", index, write_result
        )
        return (
            f"Write validation failed: {write_result}. "
            f"Revise the example to fix the validation error."
        )

    logger.info(
        "target_accepted: index=%d, score=%s (batch window 2)",
        index,
        "redo" if score is None else score,
    )
    return None


def _reject_row(
    mgr: BatchStateManager,
    output_manager: OutputFileManager,
    row: BatchRow,
    pass_number: int,
    reason: str,
    history: list[dict[str, Any]],
) -> None:
    """Terminally reject a row: rejected.jsonl record + state event."""
    record = _build_rejection_record(
        target=row.target,
        target_index=row.index,
        rejection_history=history,
        reason=reason,
    )
    output_manager.rejected_fh.write(json.dumps(record) + "\n")
    output_manager.rejected_fh.flush()
    mgr.record(
        "coach_done",
        index=row.index,
        **{"pass": pass_number},
        status="rejected",
        reason=reason,
    )
    logger.warning(
        "target_rejected: index=%d, reason=%s (batch window 2)", row.index, reason
    )


# ---------------------------------------------------------------------------
# Driver — one window per invocation
# ---------------------------------------------------------------------------


async def run_batch_generation_loop(
    player: Any,
    coach: Any | dict[str, Any],
    targets: list[GenerationTarget],
    config: GenerationConfig,
    batch: Any,
    output_dir: Path,
    output_manager: OutputFileManager,
    write_tool: Callable,
    resume: bool = False,
    rag_tool: Callable | None = None,
    coach_fallback: Any | dict[str, Any] | None = None,
) -> BatchWindowOutcome:
    """Run ONE window of the two-window batched-legs generation loop.

    Fresh invocations start window 1 of pass 1; ``resume=True`` replays
    the state log and continues at the recorded position (finishing a
    crashed window, or entering the next one after the operator's serving
    switch).  The invocation exits at the next window boundary with an
    operator instruction, or completes the run.

    Args:
        player: Window-1 Player/teacher DeepAgent.
        coach: Coach DeepAgent or layer-keyed dict (as in sequential mode).
        targets: Generation targets from GOAL.md.
        config: Generation loop configuration (shared with sequential).
        batch: ``BatchConfig`` (``max_passes`` override, operator note).
        output_dir: Output directory holding the state log.
        output_manager: Open output file manager.
        write_tool: The ``write_output`` tool.
        resume: Continue from the recorded state instead of starting fresh.
        rag_tool: Optional ``rag_retrieval`` tool.
        coach_fallback: Optional non-structured fallback Coach (same shape
            as ``coach``).

    Returns:
        A :class:`BatchWindowOutcome` (paused at a boundary, or complete
        with aggregate statistics).

    Raises:
        BatchStateError: On a corrupt state log or a target-collection
            fingerprint mismatch (config changed mid-run).
    """
    start_time = time.monotonic()
    token_usage = TokenUsage()

    rows = collect_generation_targets(targets, config)
    fingerprint = target_fingerprint(rows)
    max_passes = batch.max_passes if batch.max_passes is not None else config.max_turns

    mgr = BatchStateManager(output_dir)
    if resume and mgr.exists():
        state = mgr.replay()
        if state.fingerprint and state.fingerprint != fingerprint:
            raise BatchStateError(
                "Target collection changed since the run started "
                f"(recorded fingerprint {state.fingerprint}, current "
                f"{fingerprint}). Restore the original config, or start "
                "fresh (discarding checkpointed window work)."
            )
        if state.max_passes is not None and state.max_passes != max_passes:
            raise BatchStateError(
                "max_passes changed since the run started "
                f"(recorded {state.max_passes}, current {max_passes} — "
                "batch.max_passes falls back to generation max_turns). "
                "Restore the original config, or start fresh (discarding "
                "checkpointed window work)."
            )
        if state.complete:
            logger.info("Batch run already complete; nothing to do.")
            return BatchWindowOutcome(
                status="complete",
                window=state.window,
                pass_number=state.pass_number,
                result=_result_from_state(state, start_time, token_usage),
            )
    else:
        if resume:
            logger.warning(
                "Resume requested but no batch state log found; starting fresh"
            )
        mgr.record(
            "run_started",
            total_rows=len(rows),
            fingerprint=fingerprint,
            max_passes=max_passes,
        )
        state = mgr.replay()

    if state.window == 1:
        checkpointed, failed = await _run_window1(
            player, rows, state, config, mgr, output_manager, rag_tool, token_usage
        )
        instruction = _window1_instruction(
            pass_number=state.pass_number,
            checkpointed=checkpointed,
            failed=failed,
            accepted_so_far=state.accepted_count,
            operator_note=getattr(batch, "operator_note", ""),
        )
        _log_window_tokens(token_usage)
        return BatchWindowOutcome(
            status="paused",
            window=1,
            pass_number=state.pass_number,
            operator_instruction=instruction,
        )

    # Window 2
    await _run_window2(
        coach,
        coach_fallback,
        rows,
        state,
        config,
        mgr,
        output_manager,
        write_tool,
        token_usage,
    )
    pass_number = state.pass_number

    # Pause-into-next-pass vs run-complete is decided from the REPLAYED
    # log, never from this invocation's local counters: a revise verdict
    # recorded before a crash is invisible to the local counts, and a
    # counter-based branch would terminally reject such rows with a false
    # ``max_turns_exhausted`` reason on resume.
    post_state = mgr.replay()
    pending_revise = post_state.revise_indices()

    if pending_revise and pass_number < max_passes:
        mgr.record("window2_complete", **{"pass": pass_number}, next="pass")
        instruction = _window2_instruction(
            pass_number=pass_number,
            accepted=post_state.accepted_count,
            pending=len(pending_revise),
            operator_note=getattr(batch, "operator_note", ""),
        )
        _log_window_tokens(token_usage)
        return BatchWindowOutcome(
            status="paused",
            window=2,
            pass_number=pass_number,
            operator_instruction=instruction,
        )

    # Run complete — finalise any rows still pending revision (out of
    # passes; the replayed set covers pre-crash revise verdicts too).
    row_by_index = {r.index: r for r in rows}
    for idx in pending_revise:
        row = row_by_index[idx]
        record = _build_rejection_record(
            target=row.target,
            target_index=idx,
            rejection_history=[],
            reason="max_turns_exhausted",
        )
        output_manager.rejected_fh.write(json.dumps(record) + "\n")
        output_manager.rejected_fh.flush()
        mgr.record("row_finalised", index=idx, reason="max_turns_exhausted")
    mgr.record("window2_complete", **{"pass": pass_number}, next="complete")
    mgr.record("run_complete")

    final_state = mgr.replay()
    result = _result_from_state(final_state, start_time, token_usage)
    logger.info(
        "batch_complete: accepted=%d, rejected=%d, passes=%d, "
        "elapsed_seconds=%.1f (this window)",
        result.accepted,
        result.rejected,
        pass_number,
        result.elapsed_seconds,
    )
    _log_window_tokens(token_usage)
    return BatchWindowOutcome(
        status="complete",
        window=2,
        pass_number=pass_number,
        result=result,
    )


def _result_from_state(
    state: BatchRunState, start_time: float, token_usage: TokenUsage
) -> GenerationResult:
    """Build aggregate statistics from the replayed final state.

    ``elapsed_seconds`` and ``token_usage`` cover only the CURRENT process
    invocation (the run spans multiple attended invocations by design);
    counts cover the whole run.
    """
    return GenerationResult(
        total_targets=state.total_rows,
        accepted=state.accepted_count,
        rejected=state.rejected_count,
        total_turns=state.coach_evals,
        elapsed_seconds=time.monotonic() - start_time,
        token_usage=token_usage,
    )


def _log_window_tokens(token_usage: TokenUsage) -> None:
    """Log cumulative token usage for the window just executed."""
    if token_usage.total_tokens > 0:
        logger.info(
            "window_tokens: prompt_tokens=%d, completion_tokens=%d, "
            "total_tokens=%d",
            token_usage.prompt_tokens,
            token_usage.completion_tokens,
            token_usage.total_tokens,
        )


__all__ = [
    "BatchRow",
    "BatchWindowOutcome",
    "RESUME_COMMAND",
    "collect_generation_targets",
    "run_batch_generation_loop",
    "select_window1_model_config",
    "target_fingerprint",
]
