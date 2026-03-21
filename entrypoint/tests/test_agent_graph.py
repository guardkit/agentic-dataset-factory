"""Tests for agent.py — LangGraph thin wrapper graph export.

Verifies that agent.py exports a ``graph`` object compatible with
``langgraph.json`` registration and that invocation triggers the
complete startup + generation pipeline.

References:
    - TASK-EP-008 acceptance criteria
    - ``docs/design/contracts/API-entrypoint.md`` (LangGraph Wiring section)
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# AC-001: agent.py exports a ``graph`` object
# ---------------------------------------------------------------------------


class TestGraphExport:
    """Verify agent.py exports a usable ``graph`` object."""

    def test_agent_module_exports_graph(self) -> None:
        """graph is accessible as a module-level attribute of agent."""
        import agent

        assert hasattr(agent, "graph"), "agent.py must export a 'graph' attribute"

    def test_graph_is_compiled_state_graph(self) -> None:
        """graph must be a LangGraph CompiledStateGraph (compiled from StateGraph)."""
        import agent

        # LangGraph compiled graphs have an .invoke() method
        assert hasattr(agent.graph, "invoke"), (
            "graph must have an invoke() method (CompiledStateGraph)"
        )

    def test_graph_is_not_none(self) -> None:
        """graph must not be None."""
        import agent

        assert agent.graph is not None


# ---------------------------------------------------------------------------
# AC-002: langgraph.json references "agent.py:graph" correctly
# ---------------------------------------------------------------------------


class TestLanggraphJson:
    """Verify langgraph.json is valid and points to agent.py:graph."""

    def test_langgraph_json_exists(self) -> None:
        """langgraph.json must exist in the project root."""
        project_root = Path(__file__).resolve().parents[2]
        langgraph_json_path = project_root / "langgraph.json"
        assert langgraph_json_path.exists(), (
            f"langgraph.json not found at {langgraph_json_path}"
        )

    def test_langgraph_json_valid_json(self) -> None:
        """langgraph.json must be valid JSON."""
        project_root = Path(__file__).resolve().parents[2]
        langgraph_json_path = project_root / "langgraph.json"
        content = langgraph_json_path.read_text(encoding="utf-8")
        data = json.loads(content)
        assert isinstance(data, dict)

    def test_langgraph_json_references_agent_graph(self) -> None:
        """langgraph.json must contain {"graphs": {"agent": "agent.py:graph"}}."""
        project_root = Path(__file__).resolve().parents[2]
        langgraph_json_path = project_root / "langgraph.json"
        data = json.loads(langgraph_json_path.read_text(encoding="utf-8"))

        assert "graphs" in data, "langgraph.json must have a 'graphs' key"
        assert "agent" in data["graphs"], (
            "langgraph.json 'graphs' must have an 'agent' key"
        )
        assert data["graphs"]["agent"] == "agent.py:graph", (
            f"Expected 'agent.py:graph', got {data['graphs']['agent']!r}"
        )


# ---------------------------------------------------------------------------
# AC-004: Graph invocation runs the complete startup + generation sequence
# ---------------------------------------------------------------------------


class TestGraphInvocation:
    """Verify graph invocation triggers config load → startup → generation loop."""

    @pytest.fixture(autouse=True)
    def _patch_pipeline(self, tmp_path: Path) -> None:
        """Patch all external dependencies for isolated testing.

        Mocks the entire startup + generation pipeline so we can verify
        the graph invocation triggers the correct sequence without
        requiring real config files, ChromaDB, or LLM endpoints.
        """
        # Create a minimal agent-config.yaml
        config_yaml = tmp_path / "agent-config.yaml"
        config_yaml.write_text(
            "domain: test-domain\n"
            "player:\n"
            "  provider: local\n"
            "  model: test-model\n"
            "  endpoint: http://localhost:8000/v1\n"
            "  temperature: 0.7\n"
            "coach:\n"
            "  provider: local\n"
            "  model: test-model\n"
            "  endpoint: http://localhost:8000/v1\n"
            "  temperature: 0.3\n"
        )

        # Mock config loader
        self.mock_config = MagicMock()
        self.mock_config.domain = "test-domain"
        self.mock_config.player = MagicMock()
        self.mock_config.coach = MagicMock()
        self.mock_config.generation = MagicMock()
        self.mock_config.logging = MagicMock(level="INFO", format="json")

        # Mock GOAL.md parsed config
        self.mock_goal = MagicMock()
        self.mock_goal.generation_targets = [MagicMock()]
        self.mock_goal.metadata_schema = []
        self.mock_goal.evaluation_criteria = []
        self.mock_goal.output_schema = {}
        self.mock_goal.layer_routing = {}

        # Mock generation result
        self.mock_gen_result = MagicMock()
        self.mock_gen_result.total_targets = 1
        self.mock_gen_result.accepted = 1
        self.mock_gen_result.rejected = 0
        self.mock_gen_result.total_turns = 1
        self.mock_gen_result.elapsed_seconds = 1.0

        self.patches = [
            patch("agent.load_config", return_value=self.mock_config),
            patch("agent.configure_logging"),
            patch("agent.configure_langsmith"),
            patch("agent.resolve_domain", return_value=tmp_path / "domains" / "test-domain"),
            patch("agent.verify_chromadb_collection", return_value=MagicMock()),
            patch("agent.parse_goal_md", return_value=self.mock_goal),
            patch("agent.build_player_prompt", return_value="player prompt"),
            patch("agent.build_coach_prompt", return_value="coach prompt"),
            patch("agent.create_player_tools", return_value=[MagicMock(), MagicMock()]),
            patch("agent.create_player", return_value=MagicMock()),
            patch("agent.create_coach", return_value=MagicMock()),
            patch("agent.prepare_output_directory"),
            patch("agent.CheckpointManager"),
            patch("agent.OutputFileManager"),
            patch("agent.LockManager"),
            patch("agent.run_generation_loop", new_callable=AsyncMock, return_value=self.mock_gen_result),
        ]

        for p in self.patches:
            p.start()

        yield

        for p in self.patches:
            p.stop()

        # Force reimport on next test
        if "agent" in importlib.sys.modules:
            del importlib.sys.modules["agent"]

    def test_graph_invoke_calls_load_config(self) -> None:
        """Graph invocation must call load_config."""
        import agent

        agent.graph.invoke({"resume": False})
        agent.load_config.assert_called_once()

    def test_graph_invoke_calls_configure_logging(self) -> None:
        """Graph invocation must configure logging."""
        import agent

        agent.graph.invoke({"resume": False})
        agent.configure_logging.assert_called_once()

    def test_graph_invoke_calls_resolve_domain(self) -> None:
        """Graph invocation must resolve the domain path."""
        import agent

        agent.graph.invoke({"resume": False})
        agent.resolve_domain.assert_called_once()

    def test_graph_invoke_calls_parse_goal_md(self) -> None:
        """Graph invocation must parse GOAL.md."""
        import agent

        agent.graph.invoke({"resume": False})
        agent.parse_goal_md.assert_called_once()

    def test_graph_invoke_calls_run_generation_loop(self) -> None:
        """Graph invocation must call run_generation_loop."""
        import agent

        agent.graph.invoke({"resume": False})
        agent.run_generation_loop.assert_called_once()

    def test_graph_invoke_returns_result(self) -> None:
        """Graph invocation must return a state dict with result."""
        import agent

        result = agent.graph.invoke({"resume": False})
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# AC-005: Modified files pass lint/format (verified by ruff in CI)
# ---------------------------------------------------------------------------


class TestCodeQuality:
    """Verify agent.py follows code quality standards."""

    def test_agent_module_has_docstring(self) -> None:
        """agent.py must have a module docstring."""
        import agent

        assert agent.__doc__ is not None, "agent.py must have a module docstring"

    def test_agent_module_has_all_export(self) -> None:
        """agent.py must define __all__."""
        import agent

        assert hasattr(agent, "__all__"), "agent.py must define __all__"
        assert "graph" in agent.__all__, "'graph' must be in __all__"
