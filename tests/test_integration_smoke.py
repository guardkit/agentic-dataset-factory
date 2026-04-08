"""Integration smoke tests — BDD scenarios from entrypoint.feature.

Covers all 8 @smoke BDD scenarios from ``features/entrypoint/entrypoint.feature``
plus key negative cases (missing config, domain, GOAL.md, empty ChromaDB).

These tests exercise the real production code with mocked external dependencies
(LLM agents, ChromaDB) and temporary directories for file I/O.

Markers:
    - ``@pytest.mark.smoke`` — fast CI tests mapping to @smoke BDD scenarios
    - ``@pytest.mark.integration`` — end-to-end integration tests

References:
    - ``tasks/design_approved/TASK-EP-010-integration-tests.md``
    - ``features/entrypoint/entrypoint.feature`` (GROUP A + GROUP C @smoke)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from config.coach_verdict import CoachVerdict
from config.loader import ConfigValidationError, load_config
from config.logging import configure_logging
from config.models import (
    AgentConfig,
    ChunkingConfig,
    GenerationConfig,
    LoggingConfig,
    ModelConfig,
)
from domain_config.models import GenerationTarget
from entrypoint.generation_loop import GenerationResult, run_generation_loop
from entrypoint.startup import (
    DomainNotFoundError,
    configure_langsmith,
    resolve_domain,
    verify_chromadb_collection,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def config_dict() -> dict[str, Any]:
    """Minimal valid agent-config.yaml as a dict."""
    return {
        "domain": "gcse-english-tutor",
        "player": {
            "provider": "local",
            "model": "nemotron-3-super-120b",
            "endpoint": "http://localhost:8000/v1",
            "temperature": 0.7,
        },
        "coach": {
            "provider": "local",
            "model": "nemotron-3-super-120b",
            "endpoint": "http://localhost:8000/v1",
            "temperature": 0.3,
        },
        "generation": {
            "max_turns": 3,
            "llm_retry_attempts": 3,
            "llm_retry_backoff": 2.0,
            "llm_timeout": 300,
            "target_timeout": 600,
        },
        "chunking": {
            "chunk_size": 512,
            "overlap": 64,
        },
        "logging": {
            "level": "INFO",
            "format": "json",
        },
    }


@pytest.fixture()
def config_yaml_path(tmp_path: Path, config_dict: dict[str, Any]) -> Path:
    """Write a valid agent-config.yaml to tmp_path and return its path."""
    yaml_path = tmp_path / "agent-config.yaml"
    yaml_path.write_text(yaml.dump(config_dict), encoding="utf-8")
    return yaml_path


@pytest.fixture()
def agent_config(config_dict: dict[str, Any]) -> AgentConfig:
    """Return a validated AgentConfig from the config_dict fixture."""
    return AgentConfig.model_validate(config_dict)


@pytest.fixture()
def domain_dir(tmp_path: Path) -> Path:
    """Create a valid domain directory with a minimal GOAL.md."""
    domain_path = tmp_path / "domains" / "gcse-english-tutor"
    domain_path.mkdir(parents=True)
    goal_content = (
        "## Goal\n"
        + "A" * 60
        + "\n\n"
        + "## Source Documents\n"
        + "| File Pattern | Mode | Notes |\n"
        + "|---|---|---|\n"
        + "| *.pdf | standard | test |\n\n"
        + "## System Prompt\n"
        + "B" * 110
        + "\n\n"
        + "## Generation Targets\n"
        + "| Category | Type | Count |\n"
        + "|---|---|---|\n"
        + "| Literary analysis | reasoning | 10 |\n\n"
        + "## Generation Guidelines\n"
        + "C" * 110
        + "\n\n"
        + "## Evaluation Criteria\n"
        + "| Criterion | Description | Weight |\n"
        + "|---|---|---|\n"
        + "| accuracy | Is the answer correct? | 40% |\n"
        + "| relevance | Is the answer relevant? | 30% |\n"
        + "| clarity | Is the answer clear? | 30% |\n\n"
        + "## Output Schema\n"
        + '```json\n{"messages": [], "metadata": {}}\n```\n\n'
        + "## Metadata Schema\n"
        + "| Field | Type | Required | Valid Values |\n"
        + "|---|---|---|---|\n"
        + "| subject | string | yes | |\n\n"
        + "## Layer Routing\n"
        + "| Layer | Destination |\n"
        + "|---|---|\n"
        + "| behaviour | output/behaviour.jsonl |\n"
        + "| knowledge | output/knowledge.jsonl |\n"
    )
    (domain_path / "GOAL.md").write_text(goal_content, encoding="utf-8")
    return domain_path


@pytest.fixture()
def mock_chromadb_collection() -> MagicMock:
    """Return a mock ChromaDB collection with 100 chunks."""
    collection = MagicMock()
    collection.count.return_value = 100
    return collection


@pytest.fixture()
def mock_chromadb_client(mock_chromadb_collection: MagicMock) -> MagicMock:
    """Return a mock ChromaDB client that returns the mock collection."""
    client = MagicMock()
    client.get_collection.return_value = mock_chromadb_collection
    return client


@pytest.fixture()
def generation_target() -> GenerationTarget:
    """A single generation target for testing."""
    return GenerationTarget(
        category="Literary analysis",
        type="reasoning",
        count=1,
    )


@pytest.fixture()
def generation_config() -> GenerationConfig:
    """Minimal generation config for testing."""
    return GenerationConfig(
        max_turns=3,
        llm_retry_attempts=0,
        llm_retry_backoff=1.0,
        llm_timeout=300,
        target_timeout=600,
    )


def _make_accept_verdict_json() -> str:
    """Return a valid accept verdict as a JSON string."""
    return json.dumps({
        "decision": "accept",
        "score": 4,
        "layer_correct": True,
        "type_correct": True,
        "criteria_met": {"accuracy": True},
        "issues": [],
        "quality_assessment": "Well-structured example",
    })


def _make_reject_verdict_json() -> str:
    """Return a valid reject verdict as a JSON string."""
    return json.dumps({
        "decision": "revise",
        "score": 2,
        "layer_correct": True,
        "type_correct": True,
        "criteria_met": {"accuracy": False},
        "issues": [
            {
                "criterion": "accuracy",
                "severity": "blocking",
                "description": "Answer is incorrect",
                "suggestion": "Fix the answer",
            }
        ],
        "quality_assessment": "Needs improvement",
    })


def _make_mock_agent_response(content: str) -> dict[str, Any]:
    """Build a mock agent response dict mimicking DeepAgent output."""
    msg = MagicMock()
    msg.content = content
    return {"messages": [msg]}


# ===================================================================
# SCENARIO 1: Loading a valid agent-config.yaml
# ===================================================================


@pytest.mark.smoke
@pytest.mark.integration
class TestLoadValidConfig:
    """BDD Scenario 1: Loading a valid agent-config.yaml.

    Given an agent-config.yaml with domain, player, coach, generation,
          chunking, and logging sections
    When the entrypoint loads configuration
    Then an AgentConfig should be returned with all sections populated
    And the Player ModelConfig should reflect the configured values
    And the Coach ModelConfig should reflect the configured values
    """

    def test_config_loaded_with_all_sections(
        self, config_yaml_path: Path
    ) -> None:
        """AgentConfig returned with all sections populated."""
        config = load_config(config_yaml_path)

        assert isinstance(config, AgentConfig)
        assert config.domain == "gcse-english-tutor"
        assert isinstance(config.player, ModelConfig)
        assert isinstance(config.coach, ModelConfig)
        assert isinstance(config.generation, GenerationConfig)
        assert isinstance(config.chunking, ChunkingConfig)
        assert isinstance(config.logging, LoggingConfig)

    def test_player_model_config_values(
        self, config_yaml_path: Path
    ) -> None:
        """Player ModelConfig reflects configured provider, model, endpoint, temperature."""
        config = load_config(config_yaml_path)

        assert config.player.provider == "local"
        assert config.player.model == "nemotron-3-super-120b"
        assert config.player.endpoint == "http://localhost:8000/v1"
        assert config.player.temperature == 0.7

    def test_coach_model_config_values(
        self, config_yaml_path: Path
    ) -> None:
        """Coach ModelConfig reflects configured provider, model, endpoint, temperature."""
        config = load_config(config_yaml_path)

        assert config.coach.provider == "local"
        assert config.coach.model == "nemotron-3-super-120b"
        assert config.coach.endpoint == "http://localhost:8000/v1"
        assert config.coach.temperature == 0.3


# ===================================================================
# SCENARIO 2: Structured logging configured from config file
# ===================================================================


@pytest.mark.smoke
@pytest.mark.integration
class TestStructuredLogging:
    """BDD Scenario 2: Structured logging is configured from the config file.

    Given an agent-config.yaml with logging level "INFO" and format "json"
    When the entrypoint starts up
    Then structured JSON logging should be active
    And the log level should be set to INFO
    """

    def test_json_logging_active(self) -> None:
        """After configure_logging, root logger uses JsonFormatter."""
        from config.logging import JsonFormatter

        log_config = LoggingConfig(level="INFO", format="json")
        configure_logging(log_config)

        root = logging.getLogger()
        assert len(root.handlers) >= 1
        formatter = root.handlers[0].formatter
        assert isinstance(formatter, JsonFormatter)

    def test_log_level_set_to_info(self) -> None:
        """Root logger level set to INFO."""
        log_config = LoggingConfig(level="INFO", format="json")
        configure_logging(log_config)

        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_log_output_is_valid_json(self, capfd: pytest.CaptureFixture[str]) -> None:
        """Log output is parseable as JSON."""
        log_config = LoggingConfig(level="INFO", format="json")
        configure_logging(log_config)

        test_logger = logging.getLogger("test_json_output")
        test_logger.info("Smoke test message")

        captured = capfd.readouterr()
        # Parse the JSON output to verify format
        line = captured.err.strip().split("\n")[-1]
        parsed = json.loads(line)
        assert parsed["level"] == "INFO"
        assert "Smoke test message" in parsed["message"]


# ===================================================================
# SCENARIO 3: LangSmith project env var set from domain
# ===================================================================


@pytest.mark.smoke
@pytest.mark.integration
class TestLangSmithProject:
    """BDD Scenario 3: LangSmith project environment variable is set from domain.

    Given an agent-config.yaml with domain "gcse-english-tutor"
    When the entrypoint starts up
    Then LANGSMITH_PROJECT should be set to "adf-gcse-english-tutor"
    """

    def test_langsmith_project_env_var_set(
        self, agent_config: AgentConfig
    ) -> None:
        """LANGSMITH_PROJECT env var set to 'adf-{domain}'."""
        # Clean up env before test
        os.environ.pop("LANGSMITH_PROJECT", None)

        configure_langsmith(agent_config)

        assert os.environ["LANGSMITH_PROJECT"] == "adf-gcse-english-tutor"

        # Cleanup
        os.environ.pop("LANGSMITH_PROJECT", None)


# ===================================================================
# SCENARIO 4: Domain directory resolved and validated
# ===================================================================


@pytest.mark.smoke
@pytest.mark.integration
class TestDomainResolution:
    """BDD Scenario 4: Domain directory is resolved and validated.

    Given an agent-config.yaml with domain "gcse-english-tutor"
    And a directory exists at domains/gcse-english-tutor/
    When the entrypoint resolves the domain
    Then the domain path should be set to domains/gcse-english-tutor/
    """

    def test_domain_path_resolved(
        self, tmp_path: Path, domain_dir: Path
    ) -> None:
        """resolve_domain returns the correct domain path."""
        result = resolve_domain("gcse-english-tutor", project_root=tmp_path)

        assert result == domain_dir
        assert result.is_dir()


# ===================================================================
# SCENARIO 5: GOAL.md parsed and validated during startup
# ===================================================================


@pytest.mark.smoke
@pytest.mark.integration
class TestGoalMdParsing:
    """BDD Scenario 5: GOAL.md is parsed and validated during startup.

    Given a valid GOAL.md in the domain directory
    When the entrypoint parses GOAL.md
    Then all required sections should be extracted
    And the parsed goal should be available for prompt building and target generation
    """

    def test_goal_md_parsed_successfully(self, domain_dir: Path) -> None:
        """parse_goal_md returns GoalConfig with all sections."""
        from domain_config.parser import parse_goal_md

        goal = parse_goal_md(domain_dir / "GOAL.md")

        assert goal.goal is not None
        assert len(goal.generation_targets) >= 1
        assert len(goal.evaluation_criteria) >= 3
        assert goal.system_prompt is not None

    def test_generation_targets_available(self, domain_dir: Path) -> None:
        """Parsed generation targets are available for target iteration."""
        from domain_config.parser import parse_goal_md

        goal = parse_goal_md(domain_dir / "GOAL.md")

        target = goal.generation_targets[0]
        assert target.category == "Literary analysis"
        assert target.type == "reasoning"
        assert target.count == 10


# ===================================================================
# SCENARIO 6: ChromaDB collection verified to contain chunks
# ===================================================================


@pytest.mark.smoke
@pytest.mark.integration
class TestChromaDBVerification:
    """BDD Scenario 6: ChromaDB collection is verified to contain chunks.

    Given a ChromaDB collection for the domain containing ingested chunks
    When the entrypoint checks the collection
    Then startup should proceed without error
    """

    def test_chromadb_verification_succeeds(
        self, mock_chromadb_client: MagicMock
    ) -> None:
        """verify_chromadb_collection succeeds with a populated collection."""
        collection = verify_chromadb_collection(
            "gcse-english-tutor",
            client=mock_chromadb_client,
        )

        assert collection is not None
        mock_chromadb_client.get_collection.assert_called_once_with(
            name="gcse-english-tutor"
        )


# ===================================================================
# SCENARIO 7: Full startup sequence and generation loop invocation
# ===================================================================


@pytest.mark.smoke
@pytest.mark.integration
class TestFullStartupSequence:
    """BDD Scenario 7: Full startup sequence completes and generation loop is invoked.

    When the entrypoint completes the startup sequence
    Then Player and Coach agents should be instantiated via their factories
    And the tools list should contain rag_retrieval and write_output
    And the generation loop should be invoked with the agents, targets, and config
    """

    def test_full_pipeline_completes(self, tmp_path: Path, config_dict: dict[str, Any]) -> None:
        """Full pipeline runs end-to-end with mocked externals."""
        import agent

        # Write config
        config_path = tmp_path / "agent-config.yaml"
        config_path.write_text(yaml.dump(config_dict), encoding="utf-8")

        # Create domain dir (for resolve_domain path return)
        domain_path = tmp_path / "domains" / "gcse-english-tutor"
        domain_path.mkdir(parents=True)
        (domain_path / "GOAL.md").write_text("placeholder", encoding="utf-8")

        # Mock goal config with generation targets
        mock_goal = MagicMock()
        mock_goal.generation_targets = [
            GenerationTarget(category="Literary analysis", type="reasoning", count=1),
        ]
        mock_goal.metadata_schema = [MagicMock()]
        mock_goal.evaluation_criteria = []

        # Mock generation result
        mock_gen_result = GenerationResult(
            total_targets=1,
            accepted=1,
            rejected=0,
            total_turns=2,
            elapsed_seconds=1.5,
        )

        mock_player = MagicMock()
        mock_coach = MagicMock()
        mock_rag_tool = MagicMock()
        mock_rag_tool.name = "rag_retrieval"
        mock_write_tool = MagicMock()
        mock_write_tool.name = "write_output"

        with (
            patch.object(agent, "load_config", side_effect=lambda: load_config(config_path)),
            patch.object(agent, "resolve_domain", side_effect=lambda d, **kw: domain_path),
            patch.object(agent, "verify_chromadb_collection", return_value=MagicMock()),
            patch.object(agent, "parse_goal_md", return_value=mock_goal),
            patch.object(agent, "build_player_prompt", return_value="player prompt"),
            patch.object(agent, "build_coach_prompt", return_value="coach prompt"),
            patch.object(agent, "create_player", return_value=mock_player) as mock_create_player,
            patch.object(agent, "create_coach", return_value=mock_coach) as mock_create_coach,
            patch.object(agent, "create_player_tools", return_value=[mock_rag_tool]),
            patch.object(agent, "create_write_tool", return_value=mock_write_tool),
            patch.object(agent, "run_generation_loop", new_callable=AsyncMock, return_value=mock_gen_result) as mock_gen_loop,
            patch.object(agent, "LockManager") as mock_lock_cls,
            patch.object(agent, "OutputFileManager") as mock_output_cls,
            patch.object(agent, "CheckpointManager") as mock_cp_cls,
            patch.object(agent, "prepare_output_directory"),
        ):
            result = agent.run_pipeline({"resume": False})

        # Verify Player and Coach instantiated
        mock_create_player.assert_called_once()
        assert mock_create_coach.call_count == 2  # behaviour + knowledge

        # Verify Player tools contain only rag_retrieval (TASK-TRF-005)
        tools_arg = mock_create_player.call_args.kwargs.get("tools")
        assert tools_arg is not None
        tool_names = [t.name for t in tools_arg]
        assert "rag_retrieval" in tool_names
        assert "write_output" not in tool_names

        # Verify generation loop invoked with agents, targets, and config
        mock_gen_loop.assert_called_once()
        gen_kwargs = mock_gen_loop.call_args.kwargs
        assert "player" in gen_kwargs
        assert "coach" in gen_kwargs
        assert "targets" in gen_kwargs
        assert "config" in gen_kwargs

        # Pipeline result contains expected stats
        assert result["accepted"] == 1
        assert result["total_targets"] == 1


# ===================================================================
# SCENARIO 8: Generation loop processes target through Player-Coach cycle
# ===================================================================


@pytest.mark.smoke
@pytest.mark.integration
class TestGenerationLoopPlayerCoachCycle:
    """BDD Scenario 8: Generation loop processes a target through Player-Coach cycle.

    Given a generation target for category "Literary analysis" with text "macbeth"
    When the generation loop processes this target
    Then the Player should generate an example
    And the Coach should evaluate the example
    And if accepted the Player should write the output
    And if rejected and turns remain the Player should revise
    """

    @pytest.mark.asyncio
    async def test_player_coach_accept_cycle(
        self,
        generation_target: GenerationTarget,
        generation_config: GenerationConfig,
    ) -> None:
        """Player generates, Coach accepts on first turn."""
        player = AsyncMock()
        coach = AsyncMock()
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()

        # Player returns a training example as JSON (TASK-TRF-005)
        player.ainvoke.return_value = _make_mock_agent_response(
            '{"messages": [{"role": "system", "content": "tutor"}, {"role": "user", "content": "macbeth"}], "metadata": {"layer": "behaviour", "type": "direct"}}'
        )
        # Coach accepts on first turn
        coach.ainvoke.return_value = _make_mock_agent_response(
            _make_accept_verdict_json()
        )

        write_tool = MagicMock()
        write_tool.invoke.return_value = "Written to output/train.jsonl (example #1)"

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[generation_target],
            config=generation_config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
        )

        # Player was called (generated example)
        assert player.ainvoke.call_count >= 1
        # Coach was called (evaluated example)
        assert coach.ainvoke.call_count >= 1
        # Target accepted
        assert result.accepted == 1
        assert result.rejected == 0

    @pytest.mark.asyncio
    async def test_player_coach_reject_then_revise_cycle(
        self,
        generation_target: GenerationTarget,
    ) -> None:
        """Coach rejects first turn, Player revises, Coach accepts second turn."""
        config = GenerationConfig(
            max_turns=3,
            llm_retry_attempts=0,
            llm_retry_backoff=1.0,
            llm_timeout=300,
            target_timeout=600,
        )

        player = AsyncMock()
        coach = AsyncMock()
        checkpoint = MagicMock()
        output_mgr = MagicMock()
        output_mgr.rejected_fh = MagicMock()

        # Player always returns content as JSON (TASK-TRF-005)
        player.ainvoke.return_value = _make_mock_agent_response(
            '{"messages": [{"role": "system", "content": "tutor"}, {"role": "user", "content": "q"}], "metadata": {"layer": "behaviour", "type": "direct"}}'
        )
        # Coach rejects first, accepts second
        coach.ainvoke.side_effect = [
            _make_mock_agent_response(_make_reject_verdict_json()),
            _make_mock_agent_response(_make_accept_verdict_json()),
        ]

        write_tool = MagicMock()
        write_tool.invoke.return_value = "Written to output/train.jsonl (example #1)"

        result = await run_generation_loop(
            player=player,
            coach=coach,
            targets=[generation_target],
            config=config,
            checkpoint=checkpoint,
            output_manager=output_mgr,
            write_tool=write_tool,
        )

        # Player called twice (original + revision)
        assert player.ainvoke.call_count == 2
        # Coach called twice (evaluate original + evaluate revision)
        assert coach.ainvoke.call_count == 2
        # Target accepted after revision
        assert result.accepted == 1
        assert result.total_turns == 2


# ===================================================================
# NEGATIVE CASE 1: Missing agent-config.yaml
# ===================================================================


@pytest.mark.smoke
@pytest.mark.integration
class TestMissingConfig:
    """Negative: Startup with missing agent-config.yaml.

    Given no agent-config.yaml file exists in the working directory
    When the entrypoint starts up
    Then a FileNotFoundError should be raised
    And the error message should indicate the config file is missing
    """

    def test_missing_config_raises_file_not_found(self, tmp_path: Path) -> None:
        """FileNotFoundError raised when agent-config.yaml is missing."""
        non_existent = tmp_path / "agent-config.yaml"

        with pytest.raises(FileNotFoundError, match="[Cc]onfiguration file not found"):
            load_config(non_existent)


# ===================================================================
# NEGATIVE CASE 2: Non-existent domain directory
# ===================================================================


@pytest.mark.smoke
@pytest.mark.integration
class TestNonExistentDomain:
    """Negative: Startup with non-existent domain directory.

    Given an agent-config.yaml with domain "non-existent-domain"
    And no directory exists at domains/non-existent-domain/
    When the entrypoint starts up
    Then a DomainNotFoundError should be raised indicating the domain does not exist
    """

    def test_non_existent_domain_raises_error(self, tmp_path: Path) -> None:
        """DomainNotFoundError raised for missing domain directory."""
        # domains/ dir exists but not the specific domain
        (tmp_path / "domains").mkdir()

        with pytest.raises(DomainNotFoundError, match="non-existent-domain"):
            resolve_domain("non-existent-domain", project_root=tmp_path)


# ===================================================================
# NEGATIVE CASE 3: Missing GOAL.md in domain directory
# ===================================================================


@pytest.mark.smoke
@pytest.mark.integration
class TestMissingGoalMd:
    """Negative: Startup with missing GOAL.md in domain directory.

    Given a domain directory that exists but contains no GOAL.md
    When the entrypoint starts up
    Then an error should be raised indicating GOAL.md is missing
    """

    def test_missing_goal_md_raises_error(self, tmp_path: Path) -> None:
        """FileNotFoundError raised when GOAL.md is absent from domain dir."""
        domain_path = tmp_path / "domains" / "test-domain"
        domain_path.mkdir(parents=True)

        with pytest.raises(FileNotFoundError, match="GOAL.md"):
            resolve_domain("test-domain", project_root=tmp_path)


# ===================================================================
# NEGATIVE CASE 4: Empty ChromaDB collection
# ===================================================================


@pytest.mark.smoke
@pytest.mark.integration
class TestEmptyChromaDB:
    """Negative: Startup with empty ChromaDB collection.

    Given a ChromaDB collection for the domain containing zero chunks
    When the entrypoint checks the collection
    Then an error should be raised suggesting to run the ingestion pipeline
    """

    def test_empty_collection_raises_runtime_error(self) -> None:
        """RuntimeError raised with ingestion suggestion for empty collection."""
        client = MagicMock()
        collection = MagicMock()
        collection.count.return_value = 0
        client.get_collection.return_value = collection

        with pytest.raises(RuntimeError, match="(?i)ingest"):
            verify_chromadb_collection("test-domain", client=client)
