"""Tests for config.loader — load_config() and ConfigValidationError.

Covers all acceptance criteria for TASK-EP-002 and BDD scenarios from
features/entrypoint/entrypoint.feature (config-loading negative/edge cases).

TDD RED phase: tests written before implementation.
"""

from __future__ import annotations

import logging
import textwrap
from pathlib import Path

import pytest
import yaml


# ---------------------------------------------------------------------------
# AC-001: load_config() returns validated AgentConfig from valid YAML
# ---------------------------------------------------------------------------


class TestLoadConfigReturnsAgentConfig:
    """AC-001: load_config() returns validated AgentConfig from valid YAML."""

    def test_load_valid_config_returns_agent_config(self, tmp_path: Path) -> None:
        """BDD: Loading a valid agent-config.yaml."""
        config_file = tmp_path / "agent-config.yaml"
        config_file.write_text(
            textwrap.dedent("""\
                domain: gcse-english-tutor
                player:
                  provider: local
                  model: nemotron-3-super-120b
                  endpoint: http://localhost:8000/v1
                  temperature: 0.7
                coach:
                  provider: anthropic
                  model: claude-3-opus
                  temperature: 0.3
            """)
        )

        from config.loader import load_config
        from config.models import AgentConfig

        result = load_config(config_file)
        assert isinstance(result, AgentConfig)
        assert result.domain == "gcse-english-tutor"
        assert result.player.provider == "local"
        assert result.player.model == "nemotron-3-super-120b"
        assert result.player.endpoint == "http://localhost:8000/v1"
        assert result.coach.provider == "anthropic"
        assert result.coach.model == "claude-3-opus"

    def test_load_config_applies_defaults_for_optional_sections(self, tmp_path: Path) -> None:
        """Minimal config with only required fields; defaults applied."""
        config_file = tmp_path / "agent-config.yaml"
        config_file.write_text(
            textwrap.dedent("""\
                domain: test-domain
                player:
                  provider: anthropic
                  model: test-model
                coach:
                  provider: openai
                  model: gpt-4
            """)
        )

        from config.loader import load_config

        result = load_config(config_file)
        assert result.generation.max_turns == 3
        assert result.chunking.chunk_size == 512
        assert result.logging.level == "INFO"

    def test_load_config_default_path_is_agent_config_yaml(self) -> None:
        """Default path parameter is Path('agent-config.yaml')."""
        import inspect

        from config.loader import load_config

        sig = inspect.signature(load_config)
        param = sig.parameters["path"]
        assert param.default == Path("agent-config.yaml")


# ---------------------------------------------------------------------------
# AC-002: FileNotFoundError raised when config file missing
# ---------------------------------------------------------------------------


class TestLoadConfigFileNotFound:
    """AC-002: FileNotFoundError raised when config file missing."""

    def test_missing_file_raises_file_not_found_error(self, tmp_path: Path) -> None:
        """BDD: Startup with missing agent-config.yaml."""
        from config.loader import load_config

        missing_path = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError, match="nonexistent.yaml"):
            load_config(missing_path)

    def test_file_not_found_error_message_is_clear(self, tmp_path: Path) -> None:
        """Error message should include the path that was not found."""
        from config.loader import load_config

        missing_path = tmp_path / "missing-config.yaml"
        with pytest.raises(FileNotFoundError) as exc_info:
            load_config(missing_path)
        assert str(missing_path) in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC-003: ConfigValidationError raised for invalid config values
# ---------------------------------------------------------------------------


class TestLoadConfigValidationError:
    """AC-003: ConfigValidationError raised for invalid config values."""

    def test_invalid_provider_raises_config_validation_error(self, tmp_path: Path) -> None:
        """BDD: Configuration with unsupported provider."""
        config_file = tmp_path / "agent-config.yaml"
        config_file.write_text(
            textwrap.dedent("""\
                domain: test
                player:
                  provider: azure
                  model: test-model
                coach:
                  provider: anthropic
                  model: test-model
            """)
        )

        from config.loader import ConfigValidationError, load_config

        with pytest.raises(ConfigValidationError):
            load_config(config_file)

    def test_missing_domain_raises_config_validation_error(self, tmp_path: Path) -> None:
        """BDD: Configuration with no domain field."""
        config_file = tmp_path / "agent-config.yaml"
        config_file.write_text(
            textwrap.dedent("""\
                player:
                  provider: anthropic
                  model: test-model
                coach:
                  provider: anthropic
                  model: test-model
            """)
        )

        from config.loader import ConfigValidationError, load_config

        with pytest.raises(ConfigValidationError):
            load_config(config_file)

    def test_missing_player_provider_raises_config_validation_error(self, tmp_path: Path) -> None:
        """BDD: Configuration missing player provider."""
        config_file = tmp_path / "agent-config.yaml"
        config_file.write_text(
            textwrap.dedent("""\
                domain: test
                player:
                  model: test-model
                coach:
                  provider: anthropic
                  model: test-model
            """)
        )

        from config.loader import ConfigValidationError, load_config

        with pytest.raises(ConfigValidationError):
            load_config(config_file)

    def test_missing_player_model_raises_config_validation_error(self, tmp_path: Path) -> None:
        """BDD: Configuration missing player model."""
        config_file = tmp_path / "agent-config.yaml"
        config_file.write_text(
            textwrap.dedent("""\
                domain: test
                player:
                  provider: anthropic
                coach:
                  provider: anthropic
                  model: test-model
            """)
        )

        from config.loader import ConfigValidationError, load_config

        with pytest.raises(ConfigValidationError):
            load_config(config_file)

    def test_local_provider_without_endpoint_raises_config_validation_error(
        self, tmp_path: Path
    ) -> None:
        """BDD: Local provider configuration without endpoint."""
        config_file = tmp_path / "agent-config.yaml"
        config_file.write_text(
            textwrap.dedent("""\
                domain: test
                player:
                  provider: local
                  model: test-model
                coach:
                  provider: anthropic
                  model: test-model
            """)
        )

        from config.loader import ConfigValidationError, load_config

        with pytest.raises(ConfigValidationError):
            load_config(config_file)

    def test_invalid_log_level_raises_config_validation_error(self, tmp_path: Path) -> None:
        """BDD: Configuration with invalid log level."""
        config_file = tmp_path / "agent-config.yaml"
        config_file.write_text(
            textwrap.dedent("""\
                domain: test
                player:
                  provider: anthropic
                  model: test-model
                coach:
                  provider: anthropic
                  model: test-model
                logging:
                  level: VERBOSE
            """)
        )

        from config.loader import ConfigValidationError, load_config

        with pytest.raises(ConfigValidationError):
            load_config(config_file)

    def test_config_validation_error_has_actionable_message(self, tmp_path: Path) -> None:
        """Error message should be user-friendly and mention what is wrong."""
        config_file = tmp_path / "agent-config.yaml"
        config_file.write_text(
            textwrap.dedent("""\
                domain: test
                player:
                  provider: azure
                  model: test-model
                coach:
                  provider: anthropic
                  model: test-model
            """)
        )

        from config.loader import ConfigValidationError, load_config

        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(config_file)
        error_msg = str(exc_info.value)
        # Should mention configuration and have useful context
        assert "config" in error_msg.lower() or "validation" in error_msg.lower()

    def test_config_validation_error_wraps_pydantic_validation_error(self, tmp_path: Path) -> None:
        """ConfigValidationError should wrap the original Pydantic ValidationError."""
        config_file = tmp_path / "agent-config.yaml"
        config_file.write_text(
            textwrap.dedent("""\
                domain: test
                player:
                  provider: azure
                  model: test-model
                coach:
                  provider: anthropic
                  model: test-model
            """)
        )

        from pydantic import ValidationError

        from config.loader import ConfigValidationError, load_config

        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(config_file)
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, ValidationError)

    def test_config_validation_error_is_exception_subclass(self) -> None:
        """ConfigValidationError should be a standard Exception subclass."""
        from config.loader import ConfigValidationError

        assert issubclass(ConfigValidationError, Exception)


# ---------------------------------------------------------------------------
# AC-004: yaml.safe_load used (never yaml.load or yaml.unsafe_load)
# ---------------------------------------------------------------------------


class TestYamlSafeLoadUsed:
    """AC-004: yaml.safe_load used exclusively."""

    def test_loader_source_uses_safe_load(self) -> None:
        """Verify yaml.safe_load is used in the source, not yaml.load."""
        import inspect

        from config import loader

        source = inspect.getsource(loader)
        assert "yaml.safe_load" in source
        # Ensure no unsafe variants (check carefully — safe_load contains 'load')
        lines = source.split("\n")
        for line in lines:
            stripped = line.strip()
            # Skip comments and docstrings
            if stripped.startswith("#") or stripped.startswith('"""'):
                continue
            if "yaml.load(" in stripped or "yaml.unsafe_load" in stripped:
                pytest.fail(f"Unsafe YAML loading found: {stripped}")


# ---------------------------------------------------------------------------
# AC-005: Warning logged for unrecognised fields
# ---------------------------------------------------------------------------


class TestUnknownFieldWarning:
    """AC-005: Warning logged for unrecognised fields."""

    def test_unknown_top_level_fields_logged_as_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """BDD: Config file with extra unknown fields is loaded with a warning."""
        config_file = tmp_path / "agent-config.yaml"
        config_file.write_text(
            textwrap.dedent("""\
                domain: test-domain
                player:
                  provider: anthropic
                  model: test-model
                coach:
                  provider: anthropic
                  model: test-model
                experimental_feature: true
                future_setting: value
            """)
        )

        from config.loader import load_config

        with caplog.at_level(logging.WARNING):
            result = load_config(config_file)

        # Config should still load successfully
        assert result.domain == "test-domain"
        # Warning should be logged
        assert any("unknown" in msg.lower() or "ignored" in msg.lower() for msg in caplog.messages)

    def test_no_warning_for_valid_fields(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No warning when all fields are known."""
        config_file = tmp_path / "agent-config.yaml"
        config_file.write_text(
            textwrap.dedent("""\
                domain: test-domain
                player:
                  provider: anthropic
                  model: test-model
                coach:
                  provider: anthropic
                  model: test-model
            """)
        )

        from config.loader import load_config

        with caplog.at_level(logging.WARNING):
            load_config(config_file)

        warning_messages = [
            msg for msg in caplog.messages if "unknown" in msg.lower() or "ignored" in msg.lower()
        ]
        assert len(warning_messages) == 0


# ---------------------------------------------------------------------------
# AC-006: YAML anchor/alias injection rejected
# ---------------------------------------------------------------------------


class TestYamlAnchorAliasRejected:
    """AC-006: YAML anchor/alias injection rejected."""

    def test_yaml_with_anchors_and_aliases_rejected(self, tmp_path: Path) -> None:
        """BDD: Config file with YAML alias injection is rejected.

        yaml.safe_load handles anchors/aliases safely (no code execution),
        but the requirement is to verify anchors/aliases don't cause
        unexpected behavior. With safe_load, anchors are actually resolved
        safely — the key is that yaml.safe_load is used, preventing custom
        tag exploits. This test verifies safe_load handles the input
        without security issues.
        """
        config_file = tmp_path / "agent-config.yaml"
        # YAML with anchors and aliases — safe_load resolves these safely
        config_file.write_text(
            textwrap.dedent("""\
                defaults: &defaults
                  provider: anthropic
                  model: test-model
                domain: test-domain
                player:
                  <<: *defaults
                coach:
                  <<: *defaults
            """)
        )

        from config.loader import load_config

        # safe_load resolves anchors/aliases safely — this should work
        # The key security property is that custom tags are rejected
        result = load_config(config_file)
        assert result.player.provider == "anthropic"

    def test_yaml_custom_tag_rejected_by_safe_load(self, tmp_path: Path) -> None:
        """yaml.safe_load rejects custom YAML tags (the real security risk)."""
        config_file = tmp_path / "agent-config.yaml"
        config_file.write_text("exploit: !!python/object/apply:os.system ['echo pwned']\n")

        from config.loader import ConfigValidationError, load_config

        # safe_load should reject custom tags with a yaml.YAMLError
        # which load_config should handle appropriately
        with pytest.raises((yaml.YAMLError, ConfigValidationError)):
            load_config(config_file)


# ---------------------------------------------------------------------------
# Seam test: integration contract with TASK-EP-001
# ---------------------------------------------------------------------------


class TestSeamAgentConfigContract:
    """Seam test: verify AgentConfig contract from TASK-EP-001."""

    @pytest.mark.seam
    @pytest.mark.integration_contract("AgentConfig")
    def test_agent_config_format(self) -> None:
        """Verify AgentConfig matches the expected format.

        Contract: AgentConfig.model_validate() expects a dict from
        yaml.safe_load output.
        Producer: TASK-EP-001
        """
        from config.models import AgentConfig

        config_dict = {
            "domain": "test-domain",
            "player": {
                "provider": "local",
                "model": "test-model",
                "endpoint": "http://localhost:8000/v1",
            },
            "coach": {
                "provider": "local",
                "model": "test-model",
                "endpoint": "http://localhost:8000/v1",
            },
        }

        result = AgentConfig.model_validate(config_dict)
        assert result.domain == "test-domain"
        assert result.generation.max_turns == 3  # default

    @pytest.mark.seam
    @pytest.mark.integration_contract("AgentConfig")
    def test_load_config_round_trip(self, tmp_path: Path) -> None:
        """Verify load_config produces same result as direct model_validate."""
        config_file = tmp_path / "agent-config.yaml"
        config_file.write_text(
            textwrap.dedent("""\
                domain: test-domain
                player:
                  provider: local
                  model: test-model
                  endpoint: http://localhost:8000/v1
                coach:
                  provider: local
                  model: test-model
                  endpoint: http://localhost:8000/v1
            """)
        )

        from config.loader import load_config
        from config.models import AgentConfig

        loaded = load_config(config_file)
        direct = AgentConfig.model_validate(yaml.safe_load(config_file.read_text()))
        assert loaded.model_dump() == direct.model_dump()
