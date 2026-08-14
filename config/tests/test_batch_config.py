"""Tests for the ``batch:`` config block (BatchConfig — two-window mode).

Sequential-mode regression is the load-bearing property here: a config
WITHOUT a ``batch:`` block (every existing domain) must parse to the
defaults that keep the sequential loop engaged and unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from config.loader import load_config
from config.models import AgentConfig, BatchConfig, ModelConfig


def _base_data(**extra: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "domain": "test-domain",
        "player": {
            "provider": "local",
            "model": "player-model",
            "endpoint": "http://localhost:9000/v1",
        },
        "coach": {
            "provider": "local",
            "model": "coach-model",
            "endpoint": "http://localhost:9000/v1",
        },
    }
    data.update(extra)
    return data


class TestBatchConfigDefaults:
    """Configs without a batch block stay sequential (byte-compatible)."""

    def test_absent_batch_block_defaults_to_sequential(self) -> None:
        config = AgentConfig.model_validate(_base_data())
        assert config.batch.enabled is False
        assert config.batch.teacher is None
        assert config.batch.max_passes is None
        assert config.batch.operator_note == ""

    def test_repo_agent_config_yaml_stays_sequential(self) -> None:
        """The live top-level agent-config.yaml (product-owner lane) must
        keep parsing with batch disabled."""
        repo_root = Path(__file__).resolve().parents[2]
        config = load_config(repo_root / "agent-config.yaml")
        assert config.batch.enabled is False

    def test_batch_config_standalone_defaults(self) -> None:
        batch = BatchConfig()
        assert batch.enabled is False
        assert batch.teacher is None


class TestBatchConfigParsing:
    """The batch block parses through the same ModelConfig seam."""

    def test_enabled_with_teacher_seat(self) -> None:
        config = AgentConfig.model_validate(
            _base_data(
                batch={
                    "enabled": True,
                    "teacher": {
                        "provider": "local",
                        "model": "teacher-model",
                        "endpoint": "http://nodea:8888/v1",
                        "temperature": 0.5,
                    },
                    "max_passes": 2,
                    "operator_note": "per the teacher serving runbook",
                }
            )
        )
        assert config.batch.enabled is True
        assert isinstance(config.batch.teacher, ModelConfig)
        assert config.batch.teacher.model == "teacher-model"
        assert config.batch.teacher.endpoint == "http://nodea:8888/v1"
        assert config.batch.max_passes == 2
        assert config.batch.operator_note == "per the teacher serving runbook"

    def test_local_teacher_requires_endpoint(self) -> None:
        """The teacher seat inherits ModelConfig validation unchanged."""
        with pytest.raises(ValidationError, match="endpoint"):
            AgentConfig.model_validate(
                _base_data(
                    batch={
                        "enabled": True,
                        "teacher": {"provider": "local", "model": "teacher-model"},
                    }
                )
            )

    def test_max_passes_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            AgentConfig.model_validate(_base_data(batch={"max_passes": 0}))

    def test_unknown_batch_fields_are_ignored(self) -> None:
        """Forward compatibility (ASSUM-003) extends to the batch block."""
        config = AgentConfig.model_validate(
            _base_data(batch={"enabled": True, "future_field": "x"})
        )
        assert config.batch.enabled is True
