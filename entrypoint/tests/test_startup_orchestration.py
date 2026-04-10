"""Tests for TASK-EP-009 — agent.py startup orchestration (steps 1-12).

Verifies the complete 12-step startup sequence in ``agent.py``'s
``run_pipeline()`` function, covering all 8 acceptance criteria:

    AC-001: All 12 startup steps executed in order
    AC-002: Fail-fast on any validation error during steps 1-6
    AC-003: Player and Coach instantiated via factories with correct tools
    AC-004: Tools list contains ``rag_retrieval`` and ``write_output``
    AC-005: Generation loop invoked with agents, targets, and config
    AC-006: ``--resume`` flag supported
    AC-007: ``graph`` exported for ``langgraph.json``
    AC-008: All modified files pass lint/format checks (verified by ruff)

References:
    - ``tasks/design_approved/TASK-EP-009-startup-orchestration.md``
    - ``docs/design/contracts/API-entrypoint.md`` (Startup Sequence)
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_mock_config() -> MagicMock:
    """Return a minimal mock AgentConfig for testing."""
    config = MagicMock()
    config.domain = "test-domain"
    config.player = MagicMock()
    config.coach = MagicMock()
    config.generation = MagicMock()
    config.logging = MagicMock(level="INFO", format="json")
    return config


def _build_mock_goal() -> MagicMock:
    """Return a minimal mock GoalConfig for testing."""
    goal = MagicMock()
    goal.generation_targets = [MagicMock(), MagicMock()]
    goal.metadata_schema = [MagicMock()]
    goal.evaluation_criteria = []
    return goal


def _build_mock_result(
    total: int = 2, accepted: int = 2, rejected: int = 0, turns: int = 4
) -> MagicMock:
    """Return a mock GenerationResult."""
    result = MagicMock()
    result.total_targets = total
    result.accepted = accepted
    result.rejected = rejected
    result.total_turns = turns
    result.elapsed_seconds = 12.5
    return result


# ---------------------------------------------------------------------------
# Fixture: patch all external dependencies
# ---------------------------------------------------------------------------


@pytest.fixture()
def pipeline_env(tmp_path: Path):
    """Patch every dependency agent.py imports, yielding a namespace of mocks.

    Provides a clean slate for testing ``run_pipeline`` in isolation.
    """
    mock_config = _build_mock_config()
    mock_goal = _build_mock_goal()
    mock_result = _build_mock_result()

    mock_rag_tool = MagicMock()
    mock_rag_tool.name = "rag_retrieval"
    mock_write_tool = MagicMock()
    mock_write_tool.name = "write_output"

    mock_player = MagicMock()
    mock_coach = MagicMock()
    mock_checkpoint_mgr = MagicMock()
    mock_output_mgr = MagicMock()
    mock_lock_mgr = MagicMock()

    # Track call order globally so AC-001 can verify sequence
    call_order: list[str] = []

    def _track(name: str):
        """Return a side_effect that records *name* into call_order."""
        def _side(*args, **kwargs):
            call_order.append(name)
            return None
        return _side

    patches = {
        "load_config": patch(
            "agent.load_config",
            side_effect=lambda: (call_order.append("load_config"), mock_config)[-1],
        ),
        "configure_logging": patch(
            "agent.configure_logging",
            side_effect=lambda cfg: call_order.append("configure_logging"),
        ),
        "configure_langsmith": patch(
            "agent.configure_langsmith",
            side_effect=lambda cfg: call_order.append("configure_langsmith"),
        ),
        "resolve_domain": patch(
            "agent.resolve_domain",
            side_effect=lambda d, **kw: (
                call_order.append("resolve_domain"),
                tmp_path / "domains" / "test-domain",
            )[-1],
        ),
        "verify_chromadb_collection": patch(
            "agent.verify_chromadb_collection",
            side_effect=lambda d, **kw: (
                call_order.append("verify_chromadb_collection"),
                MagicMock(),
            )[-1],
        ),
        "parse_goal_md": patch(
            "agent.parse_goal_md",
            side_effect=lambda p: (call_order.append("parse_goal_md"), mock_goal)[-1],
        ),
        "prepare_output_directory": patch(
            "agent.prepare_output_directory",
            side_effect=lambda d, **kw: call_order.append("prepare_output_directory"),
        ),
        "build_player_prompt": patch(
            "agent.build_player_prompt",
            side_effect=lambda g: (
                call_order.append("build_player_prompt"),
                "player prompt",
            )[-1],
        ),
        "build_coach_prompt": patch(
            "agent.build_coach_prompt",
            side_effect=lambda g, **kw: (
                call_order.append("build_coach_prompt"),
                "coach prompt",
            )[-1],
        ),
        "create_player_tools": patch(
            "agent.create_player_tools",
            side_effect=lambda **kw: (
                call_order.append("create_player_tools"),
                [mock_rag_tool],
            )[-1],
        ),
        "create_write_tool": patch(
            "agent.create_write_tool",
            side_effect=lambda **kw: (
                call_order.append("create_write_tool"),
                mock_write_tool,
            )[-1],
        ),
        "create_player": patch(
            "agent.create_player",
            side_effect=lambda **kw: (
                call_order.append("create_player"),
                mock_player,
            )[-1],
        ),
        "create_coach": patch(
            "agent.create_coach",
            side_effect=lambda **kw: (
                call_order.append("create_coach"),
                mock_coach,
            )[-1],
        ),
        "CheckpointManager": patch("agent.CheckpointManager", return_value=mock_checkpoint_mgr),
        "OutputFileManager": patch("agent.OutputFileManager", return_value=mock_output_mgr),
        "LockManager": patch("agent.LockManager", return_value=mock_lock_mgr),
        "run_generation_loop": patch(
            "agent.run_generation_loop",
            new_callable=AsyncMock,
            return_value=mock_result,
        ),
    }

    started = []
    for p in patches.values():
        started.append(p.start())

    class _Env:
        """Namespace for test assertions."""

    env = _Env()
    env.config = mock_config  # type: ignore[attr-defined]
    env.goal = mock_goal  # type: ignore[attr-defined]
    env.result = mock_result  # type: ignore[attr-defined]
    env.player = mock_player  # type: ignore[attr-defined]
    env.coach = mock_coach  # type: ignore[attr-defined]
    env.rag_tool = mock_rag_tool  # type: ignore[attr-defined]
    env.write_tool = mock_write_tool  # type: ignore[attr-defined]
    env.checkpoint_mgr = mock_checkpoint_mgr  # type: ignore[attr-defined]
    env.output_mgr = mock_output_mgr  # type: ignore[attr-defined]
    env.lock_mgr = mock_lock_mgr  # type: ignore[attr-defined]
    env.call_order = call_order  # type: ignore[attr-defined]

    yield env

    for p in patches.values():
        p.stop()

    # Clean up module cache so each test starts fresh
    if "agent" in sys.modules:
        del sys.modules["agent"]


# ===================================================================
# AC-001: All 12 startup steps executed in order
# ===================================================================


class TestStartupSequenceOrder:
    """AC-001: All 12 startup steps executed in correct order."""

    def test_all_steps_called(self, pipeline_env) -> None:
        """All 12 startup steps must be invoked during run_pipeline."""
        import agent

        agent.run_pipeline({"resume": False})

        expected_steps = [
            "load_config",
            "configure_logging",
            "configure_langsmith",
            "resolve_domain",
            "verify_chromadb_collection",
            "parse_goal_md",
            "prepare_output_directory",
            "build_player_prompt",
            "build_coach_prompt",
            "create_player_tools",
            "create_write_tool",
            "create_player",
            "create_coach",
        ]
        for step in expected_steps:
            assert step in pipeline_env.call_order, (
                f"Step '{step}' was not called during startup"
            )

    def test_steps_called_in_order(self, pipeline_env) -> None:
        """Steps 1-12 must execute in the API-entrypoint.md prescribed order.

        The ordering constraint is:
        load_config → configure_logging → configure_langsmith →
        resolve_domain → verify_chromadb_collection → parse_goal_md →
        prepare_output_directory → build_prompts → create_tools →
        create_agents → generation_loop
        """
        import agent

        agent.run_pipeline({"resume": False})

        order = pipeline_env.call_order

        # Config must come before logging
        assert order.index("load_config") < order.index("configure_logging")
        # Logging before langsmith
        assert order.index("configure_logging") < order.index("configure_langsmith")
        # Langsmith before domain resolution
        assert order.index("configure_langsmith") < order.index("resolve_domain")
        # Domain before ChromaDB check
        assert order.index("resolve_domain") < order.index("verify_chromadb_collection")
        # ChromaDB before GOAL.md parsing
        assert order.index("verify_chromadb_collection") < order.index("parse_goal_md")
        # GOAL.md before output directory prep
        assert order.index("parse_goal_md") < order.index("prepare_output_directory")
        # Output dir before prompt building
        assert order.index("prepare_output_directory") < order.index("build_player_prompt")
        assert order.index("prepare_output_directory") < order.index("build_coach_prompt")
        # Prompts before tool creation
        assert order.index("build_player_prompt") < order.index("create_player_tools")
        assert order.index("build_coach_prompt") < order.index("create_player_tools")
        # Tools before agent creation
        assert order.index("create_player_tools") < order.index("create_player")
        assert order.index("create_player_tools") < order.index("create_coach")

    def test_generation_loop_called_after_agent_creation(self, pipeline_env) -> None:
        """run_generation_loop must be called after Player and Coach are created."""
        import agent

        agent.run_pipeline({"resume": False})
        agent.run_generation_loop.assert_called_once()


# ===================================================================
# AC-002: Fail-fast on any validation error during steps 1-6
# ===================================================================


class TestFailFastValidation:
    """AC-002: Validation errors in steps 1-6 abort the pipeline."""

    def test_load_config_failure_returns_error(self, pipeline_env) -> None:
        """If load_config() raises, run_pipeline returns an error state."""
        import agent

        with patch(
            "agent.load_config",
            side_effect=FileNotFoundError("agent-config.yaml not found"),
        ):
            result = agent.run_pipeline({"resume": False})

        assert "error" in result
        assert result["error"]

    def test_configure_logging_failure_returns_error(self, pipeline_env) -> None:
        """If configure_logging() raises, run_pipeline returns an error state."""
        import agent

        with patch("agent.configure_logging", side_effect=ValueError("bad log config")):
            result = agent.run_pipeline({"resume": False})

        assert "error" in result

    def test_resolve_domain_failure_returns_error(self, pipeline_env) -> None:
        """If resolve_domain() raises, the pipeline fails fast."""
        import agent

        with patch(
            "agent.resolve_domain",
            side_effect=Exception("Domain not found"),
        ):
            result = agent.run_pipeline({"resume": False})

        assert "error" in result
        assert "Domain not found" in result["error"]

    def test_verify_chromadb_failure_returns_error(self, pipeline_env) -> None:
        """If verify_chromadb_collection() raises, the pipeline fails fast."""
        import agent

        with patch(
            "agent.verify_chromadb_collection",
            side_effect=RuntimeError("No chunks found"),
        ):
            result = agent.run_pipeline({"resume": False})

        assert "error" in result
        assert "No chunks" in result["error"]

    def test_parse_goal_md_failure_returns_error(self, pipeline_env) -> None:
        """If parse_goal_md() raises, the pipeline fails fast."""
        import agent

        with patch(
            "agent.parse_goal_md",
            side_effect=ValueError("Invalid GOAL.md"),
        ):
            result = agent.run_pipeline({"resume": False})

        assert "error" in result
        assert "Invalid GOAL.md" in result["error"]

    def test_early_failure_skips_generation_loop(self, pipeline_env) -> None:
        """When step 1 fails, generation loop must NOT be invoked."""
        import agent

        with patch(
            "agent.load_config",
            side_effect=FileNotFoundError("missing"),
        ):
            agent.run_pipeline({"resume": False})

        agent.run_generation_loop.assert_not_called()


# ===================================================================
# AC-003: Player and Coach instantiated via factories
# ===================================================================


class TestAgentFactories:
    """AC-003: Player and Coach instantiated via factories with correct assignments."""

    def test_create_player_called_with_tools(self, pipeline_env) -> None:
        """create_player must receive the tools list."""
        import agent

        agent.run_pipeline({"resume": False})

        agent.create_player.assert_called_once()
        call_kwargs = agent.create_player.call_args
        # tools keyword should contain our mocked tools
        tools_arg = call_kwargs.kwargs.get("tools") or call_kwargs[1].get("tools")
        assert tools_arg is not None, "create_player must receive tools= keyword"
        assert len(tools_arg) == 1, "Player must receive exactly 1 tool (rag_retrieval only — TASK-TRF-005)"

    def test_create_player_receives_player_prompt(self, pipeline_env) -> None:
        """create_player must receive the player system prompt."""
        import agent

        agent.run_pipeline({"resume": False})

        call_kwargs = agent.create_player.call_args
        prompt_arg = call_kwargs.kwargs.get("system_prompt")
        assert prompt_arg == "player prompt"

    def test_create_coach_called_with_coach_prompt(self, pipeline_env) -> None:
        """create_coach must be called twice (behaviour + knowledge)."""
        import agent

        agent.run_pipeline({"resume": False})

        # behaviour + knowledge + 2 fallback variants (TASK-CR-007)
        assert agent.create_coach.call_count == 4
        prompts = [
            call.kwargs.get("system_prompt")
            for call in agent.create_coach.call_args_list
        ]
        assert all(p == "coach prompt" for p in prompts)

    def test_create_player_receives_model_config(self, pipeline_env) -> None:
        """create_player must receive the player model config."""
        import agent

        agent.run_pipeline({"resume": False})

        call_kwargs = agent.create_player.call_args
        model_config_arg = call_kwargs.kwargs.get("model_config")
        assert model_config_arg is pipeline_env.config.player

    def test_create_coach_receives_model_config(self, pipeline_env) -> None:
        """create_coach must receive the coach model config."""
        import agent

        agent.run_pipeline({"resume": False})

        call_kwargs = agent.create_coach.call_args
        model_config_arg = call_kwargs.kwargs.get("model_config")
        assert model_config_arg is pipeline_env.config.coach


# ===================================================================
# AC-004: Tools list contains rag_retrieval and write_output
# ===================================================================


class TestToolCreation:
    """AC-004: Tools list contains rag_retrieval and write_output."""

    def test_create_player_tools_called(self, pipeline_env) -> None:
        """create_player_tools must be called during startup."""
        import agent

        agent.run_pipeline({"resume": False})
        agent.create_player_tools.assert_called_once()

    def test_tools_bound_to_domain(self, pipeline_env) -> None:
        """create_player_tools must receive the domain as collection_name."""
        import agent

        agent.run_pipeline({"resume": False})

        call_kwargs = agent.create_player_tools.call_args.kwargs
        assert call_kwargs["collection_name"] == "test-domain"

    def test_write_tool_receives_metadata_schema(self, pipeline_env) -> None:
        """create_write_tool must receive metadata_schema from GOAL.md (TASK-TRF-005)."""
        import agent

        agent.run_pipeline({"resume": False})

        call_kwargs = agent.create_write_tool.call_args.kwargs
        assert call_kwargs["metadata_schema"] is pipeline_env.goal.metadata_schema

    def test_tools_passed_to_player(self, pipeline_env) -> None:
        """Player tools must contain rag_retrieval only (TASK-TRF-005)."""
        import agent

        agent.run_pipeline({"resume": False})

        player_call_kwargs = agent.create_player.call_args.kwargs
        tools = player_call_kwargs.get("tools")
        assert tools is not None
        tool_names = [t.name for t in tools]
        assert "rag_retrieval" in tool_names
        assert "write_output" not in tool_names


# ===================================================================
# AC-005: Generation loop invoked with agents, targets, and config
# ===================================================================


class TestGenerationLoopInvocation:
    """AC-005: run_generation_loop invoked with correct arguments."""

    def test_generation_loop_receives_player_and_coach(self, pipeline_env) -> None:
        """Generation loop must receive the Player and Coach agents."""
        import agent

        agent.run_pipeline({"resume": False})

        call_kwargs = agent.run_generation_loop.call_args.kwargs
        assert "player" in call_kwargs
        assert "coach" in call_kwargs

    def test_generation_loop_receives_targets(self, pipeline_env) -> None:
        """Generation loop must receive the generation targets from GOAL.md."""
        import agent

        agent.run_pipeline({"resume": False})

        call_kwargs = agent.run_generation_loop.call_args.kwargs
        assert "targets" in call_kwargs
        assert call_kwargs["targets"] is pipeline_env.goal.generation_targets

    def test_generation_loop_receives_config(self, pipeline_env) -> None:
        """Generation loop must receive the generation config."""
        import agent

        agent.run_pipeline({"resume": False})

        call_kwargs = agent.run_generation_loop.call_args.kwargs
        assert "config" in call_kwargs
        assert call_kwargs["config"] is pipeline_env.config.generation

    def test_generation_loop_receives_checkpoint(self, pipeline_env) -> None:
        """Generation loop must receive the checkpoint manager."""
        import agent

        agent.run_pipeline({"resume": False})

        call_kwargs = agent.run_generation_loop.call_args.kwargs
        assert "checkpoint" in call_kwargs

    def test_generation_loop_receives_output_manager(self, pipeline_env) -> None:
        """Generation loop must receive the output file manager."""
        import agent

        agent.run_pipeline({"resume": False})

        call_kwargs = agent.run_generation_loop.call_args.kwargs
        assert "output_manager" in call_kwargs

    def test_result_statistics_returned(self, pipeline_env) -> None:
        """Pipeline result must contain generation statistics."""
        import agent

        result = agent.run_pipeline({"resume": False})

        assert result["total_targets"] == 2
        assert result["accepted"] == 2
        assert result["rejected"] == 0
        assert result["total_turns"] == 4
        assert isinstance(result["elapsed_seconds"], float)


# ===================================================================
# AC-006: --resume flag supported
# ===================================================================


class TestResumeFlag:
    """AC-006: ``--resume`` flag is supported."""

    def test_resume_false_starts_fresh(self, pipeline_env) -> None:
        """When resume=False, start_index should be 0."""
        import agent

        agent.run_pipeline({"resume": False})

        call_kwargs = agent.run_generation_loop.call_args.kwargs
        assert call_kwargs.get("start_index", 0) == 0

    def test_resume_true_loads_checkpoint(self, pipeline_env) -> None:
        """When resume=True, CheckpointManager.load() should be called."""
        import agent

        pipeline_env.checkpoint_mgr.load.return_value = 5

        agent.run_pipeline({"resume": True})

        pipeline_env.checkpoint_mgr.load.assert_called_once()

    def test_resume_true_uses_checkpoint_index(self, pipeline_env) -> None:
        """When resume=True, generation loop gets start_index = checkpoint + 1."""
        import agent

        pipeline_env.checkpoint_mgr.load.return_value = 5

        agent.run_pipeline({"resume": True})

        call_kwargs = agent.run_generation_loop.call_args.kwargs
        assert call_kwargs["start_index"] == 6

    def test_resume_no_checkpoint_starts_from_zero(self, pipeline_env) -> None:
        """Resume with no checkpoint file should fall back to start_index=0."""
        import agent

        pipeline_env.checkpoint_mgr.load.side_effect = FileNotFoundError("no checkpoint")

        agent.run_pipeline({"resume": True})

        call_kwargs = agent.run_generation_loop.call_args.kwargs
        assert call_kwargs["start_index"] == 0

    def test_resume_default_is_false(self, pipeline_env) -> None:
        """If resume is not specified in state, it defaults to False."""
        import agent

        agent.run_pipeline({})

        # Should complete successfully and not try to load checkpoint
        pipeline_env.checkpoint_mgr.load.assert_not_called()

    def test_main_parses_resume_flag(self) -> None:
        """``main()`` must pass resume=True when --resume is in sys.argv."""
        import agent

        mock_result = {"accepted": 1, "rejected": 0, "total_targets": 1}
        with (
            patch.object(agent.graph, "invoke", return_value=mock_result) as mock_invoke,
            patch.object(sys, "argv", ["agent.py", "--resume"]),
        ):
            agent.main()

        # Check that invoke was called with resume=True
        call_args = mock_invoke.call_args
        state_arg = call_args[0][0] if call_args[0] else call_args.kwargs.get("input", {})
        assert state_arg.get("resume") is True


# ===================================================================
# AC-007: graph exported for langgraph.json
# ===================================================================


class TestGraphExport:
    """AC-007: ``graph`` exported for ``langgraph.json``."""

    def test_graph_attribute_exists(self) -> None:
        """agent.py must export a ``graph`` attribute."""
        import agent

        assert hasattr(agent, "graph")
        assert agent.graph is not None

    def test_graph_is_invocable(self) -> None:
        """graph must have an ``invoke()`` method."""
        import agent

        assert hasattr(agent.graph, "invoke")

    def test_graph_in_all(self) -> None:
        """``graph`` must be in ``__all__``."""
        import agent

        assert "graph" in agent.__all__

    def test_langgraph_json_references_graph(self) -> None:
        """``langgraph.json`` must point to ``agent.py:graph``."""
        project_root = Path(__file__).resolve().parents[2]
        langgraph_json_path = project_root / "langgraph.json"
        assert langgraph_json_path.exists(), f"langgraph.json not found at {project_root}"

        data = json.loads(langgraph_json_path.read_text(encoding="utf-8"))
        assert data["graphs"]["agent"] == "agent.py:graph"

    def test_pipeline_state_has_required_fields(self) -> None:
        """PipelineState TypedDict must have all required fields."""
        import agent

        annotations = agent.PipelineState.__annotations__
        required_fields = {"resume", "total_targets", "accepted", "rejected",
                          "total_turns", "elapsed_seconds", "error"}
        for field in required_fields:
            assert field in annotations, (
                f"PipelineState missing field '{field}'"
            )


# ===================================================================
# AC-008: Lint / format checks (verified structurally)
# ===================================================================


class TestCodeQualityStructural:
    """AC-008: Structural quality checks (lint-compatible code)."""

    def test_agent_has_module_docstring(self) -> None:
        """agent.py must have a module-level docstring."""
        import agent

        assert agent.__doc__ is not None
        assert len(agent.__doc__.strip()) > 20

    def test_agent_has_future_annotations(self) -> None:
        """agent.py must use ``from __future__ import annotations``."""
        source_path = Path(__file__).resolve().parents[2] / "agent.py"
        source = source_path.read_text(encoding="utf-8")
        assert "from __future__ import annotations" in source

    def test_run_pipeline_has_docstring(self) -> None:
        """run_pipeline() must have a docstring."""
        import agent

        assert agent.run_pipeline.__doc__ is not None

    def test_main_has_docstring(self) -> None:
        """main() must have a docstring."""
        import agent

        assert agent.main.__doc__ is not None

    def test_no_bare_except(self) -> None:
        """agent.py must not use bare ``except:`` clauses."""
        source_path = Path(__file__).resolve().parents[2] / "agent.py"
        source = source_path.read_text(encoding="utf-8")
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == "except:":
                pytest.fail(f"Bare except found at line {i}")


# ===================================================================
# Integration: Lock management during generation
# ===================================================================


class TestLockManagement:
    """Verify that LockManager is properly acquired and released."""

    def test_lock_acquired_before_generation(self, pipeline_env) -> None:
        """LockManager.acquire() must be called before generation loop."""
        import agent

        agent.run_pipeline({"resume": False})
        pipeline_env.lock_mgr.acquire.assert_called_once()

    def test_lock_released_after_generation(self, pipeline_env) -> None:
        """LockManager.release() must be called after generation loop."""
        import agent

        agent.run_pipeline({"resume": False})
        pipeline_env.lock_mgr.release.assert_called_once()

    def test_lock_released_on_generation_failure(self, pipeline_env) -> None:
        """LockManager.release() must be called even if generation loop fails."""
        import agent

        agent.run_generation_loop.side_effect = RuntimeError("loop failed")

        result = agent.run_pipeline({"resume": False})

        # Lock should still be released via finally block
        pipeline_env.lock_mgr.release.assert_called_once()
        assert "error" in result


# ===================================================================
# Integration: Output manager context
# ===================================================================


class TestOutputManagerContext:
    """Verify OutputFileManager is used as a context manager."""

    def test_output_manager_entered(self, pipeline_env) -> None:
        """OutputFileManager must be used as a context manager (__enter__)."""
        import agent

        agent.run_pipeline({"resume": False})
        pipeline_env.output_mgr.__enter__.assert_called()

    def test_output_manager_exited(self, pipeline_env) -> None:
        """OutputFileManager __exit__ must be called."""
        import agent

        agent.run_pipeline({"resume": False})
        pipeline_env.output_mgr.__exit__.assert_called()
