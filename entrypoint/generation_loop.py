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
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

import httpx
from pydantic import ValidationError

from config.coach_verdict import CoachVerdict
from synthesis.validator import normalise_think_closing_tags, validate_post_generation

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
class TokenUsage:
    """Cumulative token usage statistics for the generation loop.

    Attributes:
        prompt_tokens: Total prompt tokens consumed across all LLM calls.
        completion_tokens: Total completion tokens generated across all LLM calls.
        total_tokens: Sum of prompt and completion tokens.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, prompt: int, completion: int) -> None:
        """Accumulate token counts from a single LLM call."""
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += prompt + completion


@dataclass
class GenerationResult:
    """Statistics returned after the generation loop completes.

    Attributes:
        total_targets: Number of targets actually processed (after start_index).
        accepted: Number of targets accepted by the Coach.
        rejected: Number of targets rejected (exhausted turns, timeout, or LLM failure).
        total_turns: Total Player-Coach cycles executed across all targets.
        elapsed_seconds: Wall-clock time for the entire loop.
        token_usage: Cumulative token usage across all LLM calls.
    """

    total_targets: int
    accepted: int
    rejected: int
    total_turns: int
    elapsed_seconds: float
    token_usage: TokenUsage = field(default_factory=TokenUsage)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _repair_json_strings(json_str: str) -> str:
    """Fix common JSON issues from LLM output.

    Replaces literal newlines and tabs inside JSON string values with
    their escaped equivalents (``\\n``, ``\\t``).  Uses a state machine
    to track whether the scanner is inside a quoted string so that
    structural whitespace between JSON tokens is left untouched.

    Args:
        json_str: Raw JSON string that may contain unescaped control
            characters inside string values.

    Returns:
        Repaired JSON string safe for ``json.loads``.
    """
    result: list[str] = []
    in_string = False
    escape_next = False

    for ch in json_str:
        if escape_next:
            result.append(ch)
            escape_next = False
            continue
        if ch == "\\" and in_string:
            result.append(ch)
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue
        if in_string and ch == "\n":
            result.append("\\n")
            continue
        if in_string and ch == "\t":
            result.append("\\t")
            continue
        result.append(ch)

    return "".join(result)


def _extract_json_object(raw_content: str) -> str:
    """Extract a JSON object from text that may contain surrounding prose.

    Uses a 3-try strategy:
    1. Direct parse — content is already valid JSON.
    2. Regex code-fence extraction (``\\`\\`\\`json ... \\`\\`\\``` or
       ``\\`\\`\\` ... \\`\\`\\```).
    3. Brace-matching — find the first ``{ ... }`` block that parses.

    This is the shared helper used by both ``_extract_example_json`` and
    ``_parse_coach_verdict``.

    Args:
        raw_content: Raw string that may contain a JSON object.

    Returns:
        The extracted JSON string.

    Raises:
        ValueError: If no valid JSON object can be extracted.
    """
    content = raw_content.strip()

    # Try 1: Direct parse — content is already valid JSON
    try:
        repaired = _repair_json_strings(content)
        parsed = json.loads(repaired)
        if isinstance(parsed, dict):
            return repaired
    except (json.JSONDecodeError, TypeError):
        pass

    # Try 2: Extract from markdown code fences (```json ... ``` or ``` ... ```)
    fence_pattern = re.compile(r"```(?:json)?\s*\n(.*?)```", re.DOTALL)
    for match in fence_pattern.finditer(content):
        candidate = match.group(1).strip()
        try:
            repaired = _repair_json_strings(candidate)
            parsed = json.loads(repaired)
            if isinstance(parsed, dict):
                return repaired
        except (json.JSONDecodeError, TypeError):
            continue

    # Try 3: Find the first { ... } block that parses as valid JSON
    # Use a JSON-string-aware scanner to ignore braces inside strings
    in_string = False
    escape_next = False
    brace_depth = 0
    start_idx = None

    for i, ch in enumerate(content):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        # Only count braces outside strings
        if ch == "{":
            if brace_depth == 0:
                start_idx = i
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
            if brace_depth == 0 and start_idx is not None:
                candidate = content[start_idx : i + 1]
                try:
                    repaired = _repair_json_strings(candidate)
                    parsed = json.loads(repaired)
                    if isinstance(parsed, dict):
                        return repaired
                except (json.JSONDecodeError, TypeError):
                    start_idx = None

    raise ValueError(
        f"Failed to extract JSON object from content. "
        f"Raw content (first 200 chars): {raw_content[:200]!r}"
    )


def _extract_player_content(player_response: dict[str, Any]) -> str:
    """Extract the Player's text content from an agent response.

    Mirrors ``_extract_coach_content`` — handles the case where the
    Player model returns content as a list of typed blocks (e.g.
    ``[{"type": "text", "text": "..."}]``) rather than a plain string.
    Without this, the raw list object is passed downstream, causing
    truncation or serialisation artefacts (TASK-TRF-015).

    Args:
        player_response: Dict returned by ``player.ainvoke()``.

    Returns:
        Non-empty string containing the Player's response text.

    Raises:
        ValueError: If no content can be extracted.
    """
    last_msg = player_response["messages"][-1]
    content = getattr(last_msg, "content", None)

    # Path 1: Standard string content
    if isinstance(content, str) and content.strip():
        logger.debug(
            "player_content_source: string, len=%d",
            len(content),
        )
        return content

    # Path 2: Content blocks list — concatenate text blocks
    if isinstance(content, list):
        text_parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        combined = "".join(text_parts).strip()
        if combined:
            logger.debug(
                "player_content_source: content_blocks (%d blocks), len=%d",
                len(text_parts),
                len(combined),
            )
            return combined

        # Path 3: Content blocks list — look for reasoning blocks
        reasoning_parts = [
            block.get("text", "") or block.get("content", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "reasoning"
        ]
        combined_reasoning = "".join(reasoning_parts).strip()
        if combined_reasoning:
            logger.info("player_content_source: content list (reasoning blocks)")
            return combined_reasoning

    # Path 4: additional_kwargs.reasoning_content (vLLM think-mode)
    additional_kwargs = getattr(last_msg, "additional_kwargs", None) or {}
    reasoning_content = additional_kwargs.get("reasoning_content", "")
    if isinstance(reasoning_content, str) and reasoning_content.strip():
        # If content is also present, concatenate: think + content
        base_content = content if isinstance(content, str) and content.strip() else ""
        if base_content:
            merged = f"<think>{reasoning_content}</think>\n\n{base_content}"
            logger.info(
                "player_content_source: content + reasoning_content merged, len=%d",
                len(merged),
            )
            return merged
        logger.info(
            "player_content_source: additional_kwargs.reasoning_content "
            "(vLLM think-mode fallback), len=%d",
            len(reasoning_content),
        )
        return reasoning_content

    raise ValueError(
        f"Player response has no extractable content: content type={type(content)}, "
        f"repr(content)={content!r:.500}"
    )


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
    return _extract_json_object(raw_content)


def _parse_coach_verdict(raw_content: str) -> CoachVerdict:
    """Parse the Coach agent's response into a structured CoachVerdict.

    Uses the robust 3-try JSON extraction strategy (direct parse, code-fence
    regex, brace-matching) to handle Coach responses that include preamble
    text before the JSON verdict.

    Args:
        raw_content: Raw string content from the Coach agent response.

    Returns:
        Parsed and validated CoachVerdict.

    Raises:
        ValueError: If the content cannot be parsed as a valid CoachVerdict.
    """
    try:
        json_str = _extract_json_object(raw_content)
    except ValueError:
        raise ValueError(
            f"Failed to parse CoachVerdict: no JSON object found in response. "
            f"Raw content (first 200 chars): {raw_content[:200]!r}"
        )

    try:
        return CoachVerdict.model_validate_json(json_str)
    except ValidationError as exc:
        raise ValueError(
            f"Failed to parse CoachVerdict: JSON found but validation failed: "
            f"{exc}. Raw content (first 200 chars): {raw_content[:200]!r}"
        ) from exc


async def _invoke_with_retry(
    agent: Any,
    input_data: dict[str, Any],
    *,
    max_retries: int,
    backoff_base: float,
) -> dict[str, Any]:
    """Invoke a DeepAgent with retry logic for transient failures.

    Uses exponential backoff between retries. Retries on transient LLM
    failures (``RuntimeError``, ``OSError``, ``TimeoutError``,
    ``ValidationError``) and transient HTTP errors (429, 5xx).
    Client errors (4xx except 429) are raised immediately without retry.

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
        httpx.HTTPStatusError: If a non-retryable HTTP client error occurs.
    """
    last_exc: BaseException | None = None
    total_attempts = 1 + max_retries

    for attempt in range(total_attempts):
        try:
            return await agent.ainvoke(input_data)
        except (RuntimeError, OSError, TimeoutError, ValidationError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            # Don't retry client errors (except 429 rate limit)
            if isinstance(exc, httpx.HTTPStatusError):
                status = exc.response.status_code
                if 400 <= status < 500 and status != 429:
                    raise  # Client error — retrying won't help
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


def _extract_token_usage(
    response: dict[str, Any],
) -> tuple[int, int]:
    """Extract prompt and completion token counts from an agent response.

    LangChain message objects expose token usage via ``response_metadata``
    (OpenAI-compatible) or ``usage_metadata`` (LangChain native).  This
    function tries both paths and returns ``(0, 0)`` when usage data is
    unavailable (e.g. in tests with plain MagicMock messages).

    Args:
        response: Dict returned by ``agent.ainvoke()``.

    Returns:
        Tuple of (prompt_tokens, completion_tokens).
    """
    try:
        last_msg = response["messages"][-1]
    except (KeyError, IndexError, TypeError):
        return 0, 0

    # Path 1: response_metadata.token_usage (OpenAI-compatible / vLLM)
    meta = getattr(last_msg, "response_metadata", None)
    if meta and isinstance(meta, dict):
        token_usage = meta.get("token_usage") or meta.get("usage")
        if token_usage and isinstance(token_usage, dict):
            return (
                token_usage.get("prompt_tokens", 0),
                token_usage.get("completion_tokens", 0),
            )

    # Path 2: usage_metadata (LangChain native)
    usage_meta = getattr(last_msg, "usage_metadata", None)
    if usage_meta and isinstance(usage_meta, dict):
        return (
            usage_meta.get("input_tokens", 0),
            usage_meta.get("output_tokens", 0),
        )

    return 0, 0


def _extract_coach_content(coach_response: dict[str, Any]) -> str:
    """Extract the Coach's text content from an agent response.

    vLLM with ``--reasoning-parser qwen3`` splits model output: the
    ``<think>`` block lands in ``reasoning_content`` while ``content``
    gets only the remainder.  When the entire Coach response is inside
    ``<think>`` tags, ``content`` is empty and the verdict is lost
    because LangChain's ``ChatOpenAI`` discards ``reasoning_content``.

    This function implements a 4-source fallback:

    1. ``message.content`` (string) — standard path.
    2. ``message.additional_kwargs["reasoning_content"]`` — vLLM reasoning.
    3. Content blocks with ``type: "reasoning"`` in ``message.content``
       (when content is a list of typed blocks).
    4. Raise ``ValueError`` if all sources are empty.

    Args:
        coach_response: Dict returned by ``coach.ainvoke()``.

    Returns:
        Non-empty string containing the Coach's verdict text.

    Raises:
        ValueError: If no content can be extracted from any source.
    """
    last_msg = coach_response["messages"][-1]

    # Path 1: Standard .content (string)
    content = getattr(last_msg, "content", None)
    if isinstance(content, str) and content.strip():
        logger.debug("coach_content_source: content (standard path)")
        return content

    # Path 2: Content blocks list — look for text blocks first
    if isinstance(content, list):
        # Try text blocks
        text_parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        combined_text = "".join(text_parts).strip()
        if combined_text:
            logger.debug("coach_content_source: content list (text blocks)")
            return combined_text

        # Path 3: Try reasoning blocks
        reasoning_parts = [
            block.get("text", "") or block.get("content", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "reasoning"
        ]
        combined_reasoning = "".join(reasoning_parts).strip()
        if combined_reasoning:
            logger.info("coach_content_source: content list (reasoning blocks)")
            return combined_reasoning

    # Path 4: additional_kwargs.reasoning_content (vLLM think-mode)
    additional_kwargs = getattr(last_msg, "additional_kwargs", None) or {}
    reasoning_content = additional_kwargs.get("reasoning_content", "")
    if isinstance(reasoning_content, str) and reasoning_content.strip():
        logger.info(
            "coach_content_source: additional_kwargs.reasoning_content "
            "(vLLM think-mode fallback)"
        )
        return reasoning_content

    raise ValueError(
        "Coach response has no extractable content: "
        f"content={content!r}, "
        f"additional_kwargs keys={list(additional_kwargs.keys())}"
    )


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
    token_usage: TokenUsage | None = None,
    rag_tool: Callable | None = None,
) -> tuple[bool, int, list[dict[str, Any]]]:
    """Process a single generation target through the Player-Coach cycle.

    The orchestrator owns all writes. After the Coach accepts an example,
    the orchestrator extracts the JSON from the Player's response and calls
    ``write_tool`` to persist it. If write validation fails, the example is
    treated as a rejection and the Player is asked to revise (TASK-TRF-005).

    The orchestrator also owns RAG retrieval (TASK-TRF-009).  When
    ``rag_tool`` is provided the orchestrator pre-fetches curriculum context
    before the first Player turn, injecting it into the player message.
    This guarantees RAG grounding even when the model does not invoke the
    ``rag_retrieval`` tool autonomously.

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
        token_usage: Optional cumulative token usage accumulator.
        rag_tool: Optional ``rag_retrieval`` LangChain tool.  When provided,
            the orchestrator calls it once per target before the first Player
            turn (TASK-TRF-009).

    Returns:
        Tuple of (accepted: bool, turns_used: int, rejection_history: list).
    """
    rejection_history: list[dict[str, Any]] = []
    coach_feedback: str | None = None
    write_attempts = 0
    coach_retried = False
    target_prompt_tokens = 0
    target_completion_tokens = 0

    # --- TASK-TRF-009: Orchestrator pre-fetches RAG context ---
    rag_context: str | None = None
    if rag_tool is not None:
        rag_query = f"{target.category} {target.type}"
        try:
            rag_context = rag_tool.invoke({"query": rag_query, "n_results": 5})
            if isinstance(rag_context, str) and rag_context.startswith("Error:"):
                logger.warning(
                    "RAG pre-fetch failed for index=%d: %s",
                    target_index,
                    rag_context,
                )
                rag_context = None
            else:
                logger.info(
                    "rag_prefetch: index=%d, query=%r, result_len=%d",
                    target_index,
                    rag_query,
                    len(rag_context) if rag_context else 0,
                )
        except Exception as exc:
            logger.warning(
                "RAG pre-fetch exception for index=%d: %s",
                target_index,
                exc,
            )
            rag_context = None

    # Select grade target via round-robin from the target's grade_targets list
    grade_target = target.grade_targets[target_index % len(target.grade_targets)]

    coach_turn = 0
    format_retries = 0
    total_invocations = 0

    while coach_turn < config.max_turns:
        total_invocations += 1
        # Build player input — include RAG context and Coach feedback
        player_input: dict[str, Any] = {
            "messages": [
                {
                    "role": "user",
                    "content": _build_player_message(
                        target, coach_feedback, rag_context, grade_target
                    ),
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
        player_content = _extract_player_content(player_response)

        logger.debug(
            "player_response: index=%d, turn=%d, content_len=%d",
            target_index,
            total_invocations,
            len(player_content),
        )

        # Extract and log Player token usage
        p_prompt, p_completion = _extract_token_usage(player_response)
        if p_prompt or p_completion:
            target_prompt_tokens += p_prompt
            target_completion_tokens += p_completion
            if token_usage is not None:
                token_usage.add(p_prompt, p_completion)
            logger.info(
                "LLM usage: agent=player, index=%d, turn=%d, "
                "prompt_tokens=%d, completion_tokens=%d, total_tokens=%d",
                target_index,
                total_invocations,
                p_prompt,
                p_completion,
                p_prompt + p_completion,
            )

        # Pre-Coach JSON format gate — skip Coach if Player output
        # is not parseable as JSON or lacks required keys (saves wasted
        # Coach invocations and downstream validation failures).
        try:
            extracted = _extract_json_object(player_content)
            data = json.loads(extracted)
            if "messages" not in data or "metadata" not in data:
                raise ValueError(
                    f"JSON missing required top-level keys "
                    f"(has: {sorted(data.keys())})"
                )
        except ValueError as exc:
            format_retries += 1
            logger.warning(
                "Pre-Coach format gate: Player output is not valid JSON "
                "(index=%d, turn=%d, content_len=%d, reason=%s). "
                "Skipping Coach.",
                target_index,
                total_invocations,
                len(player_content),
                exc,
            )
            rejection_history.append(
                {"format_gate": "player_output_not_json", "turn": total_invocations,
                 "reason": str(exc)}
            )
            if format_retries > config.max_format_retries:
                break
            coach_feedback = (
                "FORMAT ERROR: Your previous response could not be parsed "
                "as a valid JSON object with both 'messages' and 'metadata' "
                "top-level keys. You MUST respond with ONLY a raw JSON object "
                "containing both 'messages' (array) and 'metadata' (object). "
                "Start your response with { and end with }. "
                "Do NOT include any text before or after the JSON. "
                "Do NOT output messages and metadata as separate JSON objects."
            )
            continue

        # Format gate passed — this counts as a real Coach turn
        coach_turn += 1

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
        coach_content = _extract_coach_content(coach_response)

        # Extract and log Coach token usage
        c_prompt, c_completion = _extract_token_usage(coach_response)
        if c_prompt or c_completion:
            target_prompt_tokens += c_prompt
            target_completion_tokens += c_completion
            if token_usage is not None:
                token_usage.add(c_prompt, c_completion)
            logger.info(
                "LLM usage: agent=coach, index=%d, turn=%d, "
                "prompt_tokens=%d, completion_tokens=%d, total_tokens=%d",
                target_index,
                coach_turn,
                c_prompt,
                c_completion,
                c_prompt + c_completion,
            )

        # Parse Coach verdict (with retry on JSON parse failure — TASK-OR-001)
        try:
            verdict = _parse_coach_verdict(coach_content)
        except ValueError as parse_exc:
            if not coach_retried:
                coach_retried = True
                logger.info(
                    "Coach JSON parse failed (index=%d, turn=%d), retrying "
                    "with JSON reinforcement: %s",
                    target_index,
                    coach_turn,
                    parse_exc,
                )
                retry_input: dict[str, Any] = {
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "IMPORTANT: Your previous response was not "
                                "valid JSON. You MUST respond with ONLY a "
                                "JSON object matching the CoachVerdict schema."
                                " No prose, no reasoning text, no markdown. "
                                "Start your response with { and end with }."
                                "\n\n" + player_content
                            ),
                        },
                    ]
                }
                coach_response = await _invoke_with_retry(
                    coach,
                    retry_input,
                    max_retries=config.llm_retry_attempts,
                    backoff_base=config.llm_retry_backoff,
                )
                r_prompt, r_completion = _extract_token_usage(coach_response)
                if r_prompt or r_completion:
                    target_prompt_tokens += r_prompt
                    target_completion_tokens += r_completion
                    if token_usage is not None:
                        token_usage.add(r_prompt, r_completion)
                    logger.info(
                        "LLM usage: agent=coach_retry, index=%d, turn=%d, "
                        "prompt_tokens=%d, completion_tokens=%d, "
                        "total_tokens=%d",
                        target_index,
                        coach_turn,
                        r_prompt,
                        r_completion,
                        r_prompt + r_completion,
                    )
                coach_content = _extract_coach_content(coach_response)
                verdict = _parse_coach_verdict(coach_content)
                # If this also fails, ValueError propagates to
                # the per-target handler in run_generation_loop
            else:
                raise  # Already retried once, let it propagate

        logger.info(
            "turn_complete: index=%d, turn=%d, decision=%s, score=%d",
            target_index,
            coach_turn,
            verdict.decision,
            verdict.score,
        )

        if verdict.is_accepted:
            # Normalise malformed <think> closing tags before extraction
            player_content = normalise_think_closing_tags(player_content)
            # Extract JSON from Player response
            try:
                example_json = _extract_example_json(player_content)
                logger.debug(
                    "example_extracted: index=%d, turn=%d, "
                    "input_len=%d, output_len=%d",
                    target_index,
                    coach_turn,
                    len(player_content),
                    len(example_json),
                )
            except ValueError as exc:
                logger.warning(
                    "JSON extraction failed after Coach acceptance: %s\n"
                    "Content length: %d chars | Last 200 chars: %s",
                    exc,
                    len(player_content),
                    player_content[-200:],
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

            # Post-generation validation gate (TASK-LR1-002)
            post_gen_result = validate_post_generation(example_json)
            if not post_gen_result.is_valid:
                logger.warning(
                    "Post-generation validation failed: %s "
                    "(index=%d, turn=%d)",
                    post_gen_result.reason,
                    target_index,
                    coach_turn,
                )
                rejection_history.append(
                    {
                        "validation_error": post_gen_result.reason,
                        **verdict.model_dump(),
                    }
                )
                coach_feedback = (
                    f"Post-generation validation failed: "
                    f"{post_gen_result.reason}. "
                    f"Revise the example to fix this defect."
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
                    if target_prompt_tokens or target_completion_tokens:
                        logger.info(
                            "target_tokens: index=%d, prompt_tokens=%d, "
                            "completion_tokens=%d, total_tokens=%d",
                            target_index,
                            target_prompt_tokens,
                            target_completion_tokens,
                            target_prompt_tokens + target_completion_tokens,
                        )
                    return False, total_invocations, rejection_history
                coach_feedback = (
                    f"Write validation failed: {write_result}. "
                    f"Revise the example to fix the validation error."
                )
                continue

            logger.info(
                "target_accepted: index=%d, coach_turns=%d, "
                "total_invocations=%d, score=%d",
                target_index,
                coach_turn,
                total_invocations,
                verdict.score,
            )
            if target_prompt_tokens or target_completion_tokens:
                logger.info(
                    "target_tokens: index=%d, prompt_tokens=%d, "
                    "completion_tokens=%d, total_tokens=%d",
                    target_index,
                    target_prompt_tokens,
                    target_completion_tokens,
                    target_prompt_tokens + target_completion_tokens,
                )
            return True, total_invocations, rejection_history

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
    if target_prompt_tokens or target_completion_tokens:
        logger.info(
            "target_tokens: index=%d, prompt_tokens=%d, "
            "completion_tokens=%d, total_tokens=%d",
            target_index,
            target_prompt_tokens,
            target_completion_tokens,
            target_prompt_tokens + target_completion_tokens,
        )
    return False, total_invocations, rejection_history


def _build_player_message(
    target: GenerationTarget,
    coach_feedback: str | None,
    rag_context: str | None = None,
    grade_target: int | None = 7,
) -> str:
    """Build the user message for the Player agent.

    Args:
        target: The generation target to process.
        coach_feedback: Optional Coach feedback from previous turn for revision.
        rag_context: Optional pre-fetched RAG context from the orchestrator.
            Injected to guarantee curriculum grounding even when the model
            does not invoke the ``rag_retrieval`` tool (TASK-TRF-009).
        grade_target: The specific grade target for this example, selected
            via round-robin from the target's ``grade_targets`` list.

    Returns:
        Formatted message string for the Player.
    """
    grade_display = str(grade_target) if grade_target is not None else "null (grade-agnostic)"
    msg = (
        f"Generate a training example for:\n"
        f"  Category: {target.category}\n"
        f"  Type: {target.type}\n"
        f"  Grade Target: {grade_display}\n"
    )
    if rag_context:
        msg += (
            f"\n--- Curriculum Context (use this to ground your example) ---\n"
            f"{rag_context}\n"
            f"--- End Curriculum Context ---\n"
        )
    if coach_feedback:
        is_format_error = coach_feedback.startswith("FORMAT ERROR:")
        label = "Format Error" if is_format_error else "Coach Feedback"
        msg += (
            f"\n--- {label} (revise based on this) ---\n"
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
    rag_tool: Callable | None = None,
) -> GenerationResult:
    """Run the sequential Player-Coach generation loop.

    Processes each target one at a time (ADR-ARCH-006). For each target:
    1. Orchestrator pre-fetches RAG context (TASK-TRF-009).
    2. Player generates an example with injected RAG context.
    3. Coach evaluates the example (returns structured JSON verdict).
    4. If accepted: orchestrator calls ``write_tool`` to persist.
    5. If rejected and turns remain: Player revises with Coach feedback.
    6. If rejected at max_turns: log to rejected.jsonl.

    The orchestrator owns all writes — the Player never calls
    ``write_output`` directly (TASK-TRF-005).

    The orchestrator also owns RAG retrieval — the orchestrator pre-fetches
    curriculum context before each target, injecting it into the Player
    message (TASK-TRF-009).

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
        rag_tool: Optional ``rag_retrieval`` LangChain tool.  When provided,
            the orchestrator calls it once per target before the first Player
            turn (TASK-TRF-009).

    Returns:
        GenerationResult with aggregate statistics.
    """
    start_time = time.monotonic()
    accepted_count = 0
    rejected_count = 0
    total_turns = 0
    cumulative_tokens = TokenUsage()

    # Expand each target by its count field (e.g. count=90 → 90 copies).
    # This turns the 20-category list into the full target list (e.g. 1000).
    # Grade round-robin uses absolute_index, so distribution is automatic.
    targets = [
        target
        for target in targets
        for _ in range(target.count)
    ]

    logger.info(
        "targets_expanded: categories=%d, total=%d",
        len({t.category for t in targets}),
        len(targets),
    )

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
                    token_usage=cumulative_tokens,
                    rag_tool=rag_tool,
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

        except (RuntimeError, OSError, ValidationError, ValueError, httpx.HTTPStatusError) as exc:
            # All LLM retries exhausted or malformed LLM response: discard
            # target, continue pipeline.  ValidationError catches cases where
            # vLLM returns tool_calls.args as a JSON string instead of a dict
            # (known issue with some model/parser combinations — TASK-REV-FRF2).
            # ValueError catches Coach returning non-JSON content, e.g.
            # Player-like reasoning text instead of a verdict (TASK-NRF-12C1).
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

    if cumulative_tokens.total_tokens > 0:
        logger.info(
            "pipeline_tokens: prompt_tokens=%d, completion_tokens=%d, "
            "total_tokens=%d",
            cumulative_tokens.prompt_tokens,
            cumulative_tokens.completion_tokens,
            cumulative_tokens.total_tokens,
        )

    return GenerationResult(
        total_targets=num_targets,
        accepted=accepted_count,
        rejected=rejected_count,
        total_turns=total_turns,
        elapsed_seconds=elapsed_seconds,
        token_usage=cumulative_tokens,
    )


__all__ = [
    "GenerationResult",
    "TokenUsage",
    "_extract_coach_content",
    "_extract_player_content",
    "run_generation_loop",
]
