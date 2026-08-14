"""LangGraph thin wrapper — graph export for langgraph.json.

Exposes the generation pipeline as a LangGraph-compatible ``graph`` for
``langgraph dev`` and Docker Compose execution.  The graph wraps the
startup + generation loop as a single invocable node; the loop itself
is plain Python (TASK-EP-007), not LangGraph nodes/edges.

Usage::

    # Via LangGraph Studio
    langgraph dev

    # Via Docker Compose
    docker compose up agent-loop

    # Direct execution
    python agent.py

References:
    - ``docs/design/contracts/API-entrypoint.md`` (LangGraph Wiring)
    - TASK-EP-008 acceptance criteria
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv

# Load .env (ANTHROPIC_API_KEY, LANGSMITH_*, etc.) before any SDK imports
load_dotenv()

# Add src/ to Python path so that `from tools.*` imports resolve at runtime
# (matches pyproject.toml [tool.pytest.ini_options] pythonpath = ["src"])
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from langgraph.graph import END, StateGraph

from agents.coach import create_coach
from agents.player import create_player
from config.loader import load_config
from config.logging import configure_logging
from domain_config.parser import parse_goal_md
from entrypoint.batch_loop import run_batch_generation_loop, select_window1_model_config
from entrypoint.batch_state import BatchStateManager
from entrypoint.checkpoint import CheckpointManager, LockManager, prepare_output_directory
from entrypoint.generation_loop import run_generation_loop
from entrypoint.output import OutputFileManager
from entrypoint.startup import configure_langsmith, resolve_domain, verify_chromadb_collection
from prompts.coach_prompts import build_coach_prompt
from prompts.player_prompts import build_player_prompt
from tools.tool_factory import create_player_tools, create_write_tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pipeline state schema
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("output")


class PipelineState(TypedDict, total=False):
    """Minimal state schema for the LangGraph wrapper.

    Attributes:
        resume: If True, resume from the last checkpoint instead of
            starting fresh.  Defaults to False.
        batch: If True, run the two-window batched-legs mode instead of
            the sequential loop (also engaged by ``batch.enabled`` in
            ``agent-config.yaml``).  Defaults to False.
        total_targets: Number of targets processed (output).
        accepted: Number of accepted targets (output).
        rejected: Number of rejected targets (output).
        total_turns: Total Player-Coach cycles executed (output).
        elapsed_seconds: Wall-clock time in seconds (output).
        paused: True when a batch run stopped at a window boundary and
            awaits the operator's serving switch + resume (output).
        operator_instruction: The window-boundary instruction text, when
            paused (output).
        error: Error message if the pipeline failed (output).
    """

    resume: bool
    batch: bool
    total_targets: int
    accepted: int
    rejected: int
    total_turns: int
    elapsed_seconds: float
    paused: bool
    operator_instruction: str
    error: str


# ---------------------------------------------------------------------------
# Pipeline node
# ---------------------------------------------------------------------------


def run_pipeline(state: PipelineState) -> PipelineState:
    """Execute the complete startup + generation pipeline.

    This is the single node in the LangGraph graph.  It orchestrates:

    1. Config loading (``agent-config.yaml``)
    2. Logging configuration (structured JSON — ADR-ARCH-007)
    3. LangSmith project setup
    4. Domain path resolution and GOAL.md validation
    5. ChromaDB collection readiness check
    6. Output directory preparation (fresh or resume)
    7. Prompt building (Player + Coach)
    8. Tool creation (Player tools bound to domain)
    9. Agent instantiation (Player + Coach factories)
    10. Generation loop execution (sequential Player-Coach cycles)

    Args:
        state: Pipeline input state.  The ``resume`` field controls
            whether to resume from a checkpoint or start fresh.

    Returns:
        Updated state with generation result statistics, or an
        ``error`` field if the pipeline failed.
    """
    resume = state.get("resume", False)

    try:
        # Step 1: Load config
        config = load_config()

        # Batch-mode routing (additive): the two-window batched-legs loop
        # engages ONLY by the explicit --batch flag or a literal
        # batch.enabled: true in agent-config.yaml.  The `is True` check is
        # deliberate — anything else (absent block, defaults, non-boolean
        # doubles) keeps the sequential path below unchanged.
        batch_enabled = getattr(getattr(config, "batch", None), "enabled", False) is True
        if state.get("batch", False) is True or batch_enabled:
            return _run_batch_pipeline(state, config)

        # Step 2: Configure logging
        configure_logging(config.logging)

        # Step 3: LangSmith project setup
        configure_langsmith(config)

        # Step 4: Resolve domain and validate GOAL.md
        domain_path = resolve_domain(config.domain)

        # Step 5: ChromaDB readiness check
        # Skip in the no-book generative mode (grounded=False): a corpus-free
        # domain (e.g. product-owner, PO Phase 1) has no ChromaDB collection,
        # so the check would hard-fail with ConnectionError.
        if config.generation.grounded:
            verify_chromadb_collection(config.domain)
        else:
            logger.info(
                "Ungrounded generative mode (grounded=false): skipping ChromaDB "
                "collection check for domain '%s'",
                config.domain,
            )

        # Step 6: Parse GOAL.md
        goal = parse_goal_md(domain_path / "GOAL.md")

        # Step 7: Prepare output directory
        prepare_output_directory(OUTPUT_DIR, resume=resume)

        # Step 8: Build prompts
        player_prompt = build_player_prompt(
            goal, grounded=config.generation.grounded
        )
        coach_prompt_behaviour = build_coach_prompt(goal, target_layer="behaviour")
        coach_prompt_knowledge = build_coach_prompt(goal, target_layer="knowledge")

        # Step 9: Create tools
        # grounded=False returns [] (no rag_retrieval) for the generative mode.
        tools = create_player_tools(
            collection_name=config.domain,
            grounded=config.generation.grounded,
        )

        # Step 9a: Keep a reference to the rag_retrieval tool for
        # orchestrator-side pre-fetch (TASK-TRF-009).  The tool is still
        # passed to the Player via ``tools`` so the model *can* call it
        # autonomously, but the orchestrator guarantees at least one
        # RAG call per target by invoking it before the first Player turn.
        rag_tool = tools[0] if tools else None

        # Step 9b: Create write tool for orchestrator-gated writes
        # (TASK-TRF-005: only the orchestrator writes, after Coach acceptance)
        write_tool = create_write_tool(
            output_dir=OUTPUT_DIR,
            metadata_schema=goal.metadata_schema,
        )

        # Step 10: Instantiate agents
        # Wire per-call LLM timeout from generation config (TASK-D0A8-001).
        llm_timeout = config.generation.llm_timeout
        player = create_player(
            model_config=config.player,
            tools=tools,
            system_prompt=player_prompt,
            memory=["./AGENTS.md"],
            timeout=llm_timeout,
        )
        coach_behaviour = create_coach(
            model_config=config.coach,
            system_prompt=coach_prompt_behaviour,
            memory=["./AGENTS.md"],
            timeout=llm_timeout,
        )
        coach_knowledge = create_coach(
            model_config=config.coach,
            system_prompt=coach_prompt_knowledge,
            memory=["./AGENTS.md"],
            timeout=llm_timeout,
        )

        # TASK-CR-007: Create fallback coaches without structured outputs
        # constraint for use when structured outputs trigger model refusals.
        coach_fallback_behaviour = create_coach(
            model_config=config.coach,
            system_prompt=coach_prompt_behaviour,
            memory=["./AGENTS.md"],
            timeout=llm_timeout,
            structured_outputs=False,
        )
        coach_fallback_knowledge = create_coach(
            model_config=config.coach,
            system_prompt=coach_prompt_knowledge,
            memory=["./AGENTS.md"],
            timeout=llm_timeout,
            structured_outputs=False,
        )
        logger.info(
            "Coach agents created: behaviour + knowledge (layer-aware criteria routing) "
            "+ fallback variants without structured outputs"
        )

        # Step 11: Determine start index
        checkpoint_mgr = CheckpointManager(OUTPUT_DIR)
        start_index = 0
        if resume:
            try:
                start_index = checkpoint_mgr.load() + 1
                logger.info("Resuming from target index %d", start_index)
            except FileNotFoundError:
                logger.warning(
                    "Resume requested but no checkpoint found; starting from index 0"
                )

        # Step 12: Run generation loop with lock and output file management
        lock = LockManager(OUTPUT_DIR)
        lock.acquire()
        try:
            output_mgr = OutputFileManager(OUTPUT_DIR)
            with output_mgr:
                result = asyncio.run(
                    run_generation_loop(
                        player=player,
                        coach={
                            "behaviour": coach_behaviour,
                            "knowledge": coach_knowledge,
                        },
                        targets=goal.generation_targets,
                        config=config.generation,
                        checkpoint=checkpoint_mgr,
                        output_manager=output_mgr,
                        write_tool=write_tool,
                        start_index=start_index,
                        rag_tool=rag_tool,
                        coach_fallback={
                            "behaviour": coach_fallback_behaviour,
                            "knowledge": coach_fallback_knowledge,
                        },
                    )
                )
        finally:
            lock.release()

        logger.info(
            "Pipeline complete: accepted=%d, rejected=%d, turns=%d, elapsed=%.1fs",
            result.accepted,
            result.rejected,
            result.total_turns,
            result.elapsed_seconds,
        )

        return PipelineState(
            resume=resume,
            total_targets=result.total_targets,
            accepted=result.accepted,
            rejected=result.rejected,
            total_turns=result.total_turns,
            elapsed_seconds=result.elapsed_seconds,
        )

    except Exception as exc:
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        return PipelineState(
            resume=resume,
            total_targets=0,
            accepted=0,
            rejected=0,
            total_turns=0,
            elapsed_seconds=0.0,
            error=str(exc),
        )


def _run_batch_pipeline(state: PipelineState, config) -> PipelineState:
    """Execute one WINDOW of the two-window batched-legs pipeline.

    Mirrors ``run_pipeline``'s startup steps, but drives
    ``run_batch_generation_loop`` instead of the sequential loop: the
    invocation runs exactly one window (all Player/teacher legs, or all
    Coach legs) and then either pauses at the window boundary — printing
    the operator instruction for the serving-posture switch — or completes
    the run.  Resume into the next window with ``--batch --resume``.

    The window-1 Player/teacher seat comes from ``batch.teacher`` when
    set, else the ordinary ``player`` block (the same ModelConfig seam —
    no model names in code).

    Args:
        state: Pipeline input state (``resume`` and ``batch`` fields).
        config: The already-loaded ``AgentConfig``.

    Returns:
        Updated state: ``paused`` + ``operator_instruction`` at a window
        boundary, statistics on completion, or ``error`` on failure.
    """
    resume = state.get("resume", False)

    try:
        configure_logging(config.logging)
        configure_langsmith(config)
        domain_path = resolve_domain(config.domain)

        if config.generation.grounded:
            verify_chromadb_collection(config.domain)
        else:
            logger.info(
                "Ungrounded generative mode (grounded=false): skipping ChromaDB "
                "collection check for domain '%s'",
                config.domain,
            )

        goal = parse_goal_md(domain_path / "GOAL.md")

        # Guard the checkpointed windows: a fresh start (no --resume) wipes
        # the output directory (ADR-ARCH-008), which for a batch run would
        # discard a whole drained-fleet window's checkpointed legs.  Refuse
        # unless the recorded run is already complete.
        state_probe = BatchStateManager(OUTPUT_DIR)
        if not resume and state_probe.exists():
            try:
                probed = state_probe.replay()
                run_complete = probed.complete
            except Exception:
                run_complete = False
            if not run_complete:
                raise RuntimeError(
                    "An incomplete batch run exists in the output directory. "
                    "Resume it with: python agent.py --batch --resume  — or "
                    f"delete {state_probe.path} (and the output dir) to "
                    "discard the checkpointed window work and start fresh."
                )

        prepare_output_directory(OUTPUT_DIR, resume=resume)

        player_prompt = build_player_prompt(goal, grounded=config.generation.grounded)
        coach_prompt_behaviour = build_coach_prompt(goal, target_layer="behaviour")
        coach_prompt_knowledge = build_coach_prompt(goal, target_layer="knowledge")

        tools = create_player_tools(
            collection_name=config.domain,
            grounded=config.generation.grounded,
        )
        rag_tool = tools[0] if tools else None
        write_tool = create_write_tool(
            output_dir=OUTPUT_DIR,
            metadata_schema=goal.metadata_schema,
        )

        llm_timeout = config.generation.llm_timeout
        # Window-1 teacher seat: batch.teacher when set, else player.
        teacher_model_config = select_window1_model_config(config)
        player = create_player(
            model_config=teacher_model_config,
            tools=tools,
            system_prompt=player_prompt,
            memory=["./AGENTS.md"],
            timeout=llm_timeout,
        )
        coach_behaviour = create_coach(
            model_config=config.coach,
            system_prompt=coach_prompt_behaviour,
            memory=["./AGENTS.md"],
            timeout=llm_timeout,
        )
        coach_knowledge = create_coach(
            model_config=config.coach,
            system_prompt=coach_prompt_knowledge,
            memory=["./AGENTS.md"],
            timeout=llm_timeout,
        )
        coach_fallback_behaviour = create_coach(
            model_config=config.coach,
            system_prompt=coach_prompt_behaviour,
            memory=["./AGENTS.md"],
            timeout=llm_timeout,
            structured_outputs=False,
        )
        coach_fallback_knowledge = create_coach(
            model_config=config.coach,
            system_prompt=coach_prompt_knowledge,
            memory=["./AGENTS.md"],
            timeout=llm_timeout,
            structured_outputs=False,
        )
        logger.info(
            "Batch mode: teacher seat model=%s endpoint=%s; coaches created "
            "(behaviour + knowledge + fallbacks)",
            teacher_model_config.model,
            teacher_model_config.endpoint or "(provider default)",
        )

        lock = LockManager(OUTPUT_DIR)
        lock.acquire()
        try:
            output_mgr = OutputFileManager(OUTPUT_DIR)
            with output_mgr:
                outcome = asyncio.run(
                    run_batch_generation_loop(
                        player=player,
                        coach={
                            "behaviour": coach_behaviour,
                            "knowledge": coach_knowledge,
                        },
                        targets=goal.generation_targets,
                        config=config.generation,
                        batch=config.batch,
                        output_dir=OUTPUT_DIR,
                        output_manager=output_mgr,
                        write_tool=write_tool,
                        resume=resume,
                        rag_tool=rag_tool,
                        coach_fallback={
                            "behaviour": coach_fallback_behaviour,
                            "knowledge": coach_fallback_knowledge,
                        },
                    )
                )
        finally:
            lock.release()

        if outcome.status == "paused":
            logger.info(
                "Batch window boundary reached: window=%d, pass=%d — "
                "awaiting operator serving switch + resume",
                outcome.window,
                outcome.pass_number,
            )
            # Operator-facing by design: the boundary instruction must be
            # visible on the console, not only in the JSON log stream.
            print(outcome.operator_instruction)
            return PipelineState(
                resume=resume,
                batch=True,
                paused=True,
                operator_instruction=outcome.operator_instruction,
            )

        result = outcome.result
        logger.info(
            "Batch pipeline complete: accepted=%d, rejected=%d, turns=%d, "
            "elapsed=%.1fs (final window)",
            result.accepted,
            result.rejected,
            result.total_turns,
            result.elapsed_seconds,
        )
        return PipelineState(
            resume=resume,
            batch=True,
            paused=False,
            total_targets=result.total_targets,
            accepted=result.accepted,
            rejected=result.rejected,
            total_turns=result.total_turns,
            elapsed_seconds=result.elapsed_seconds,
        )

    except Exception as exc:
        logger.error("Batch pipeline failed: %s", exc, exc_info=True)
        return PipelineState(
            resume=resume,
            batch=True,
            paused=False,
            total_targets=0,
            accepted=0,
            rejected=0,
            total_turns=0,
            elapsed_seconds=0.0,
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# LangGraph graph construction
# ---------------------------------------------------------------------------

_builder = StateGraph(PipelineState)
_builder.add_node("run_pipeline", run_pipeline)
_builder.set_entry_point("run_pipeline")
_builder.add_edge("run_pipeline", END)

graph = _builder.compile()
"""Compiled LangGraph graph for ``langgraph.json`` registration.

Referenced as ``"agent.py:graph"`` in ``langgraph.json``.
"""

# ---------------------------------------------------------------------------
# Direct execution support
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the pipeline directly via ``python agent.py``.

    Flags:
        ``--resume``: continue from the saved checkpoint (sequential) or
            the recorded batch state (batch mode — extended semantics).
        ``--batch``: run the two-window batched-legs mode; each invocation
            executes one window and stops at the boundary for the
            operator's serving switch.
    """
    import sys

    resume = "--resume" in sys.argv
    batch = "--batch" in sys.argv
    result = graph.invoke(PipelineState(resume=resume, batch=batch))

    if result.get("error"):
        logger.error("Pipeline failed: %s", result["error"])
        sys.exit(1)

    if result.get("paused"):
        logger.info(
            "Batch run paused at a window boundary — follow the printed "
            "operator instruction, then resume with: python agent.py "
            "--batch --resume"
        )
        return

    logger.info(
        "Done: %d accepted, %d rejected out of %d targets",
        result.get("accepted", 0),
        result.get("rejected", 0),
        result.get("total_targets", 0),
    )


__all__ = ["PipelineState", "graph", "main", "run_pipeline"]


if __name__ == "__main__":
    main()
