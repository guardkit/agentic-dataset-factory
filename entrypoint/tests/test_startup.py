"""Tests for entrypoint.startup — domain resolution and ChromaDB readiness.

Covers all acceptance criteria for TASK-EP-004 and BDD scenarios from
features/entrypoint/entrypoint.feature (startup steps 3-6).

TDD RED phase: tests written before implementation.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_goal_md(domain_dir: Path) -> None:
    """Create a minimal valid GOAL.md in *domain_dir* for testing."""
    domain_dir.mkdir(parents=True, exist_ok=True)
    (domain_dir / "GOAL.md").write_text("# Placeholder GOAL.md\n")


def _make_agent_config(domain: str) -> MagicMock:
    """Create a mock AgentConfig with the given domain name."""
    config = MagicMock()
    config.domain = domain
    return config


# ---------------------------------------------------------------------------
# AC-001: Domain path resolved to domains/{domain}/
# ---------------------------------------------------------------------------


class TestDomainPathResolution:
    """AC-001: Domain path resolved to domains/{domain}/."""

    def test_resolve_domain_returns_correct_path(self, tmp_path: Path) -> None:
        """Domain directory is resolved and validated."""
        domain_name = "gcse-english-tutor"
        domain_dir = tmp_path / "domains" / domain_name
        _make_goal_md(domain_dir)

        from entrypoint.startup import resolve_domain

        result = resolve_domain(domain_name, project_root=tmp_path)
        assert result == domain_dir

    def test_resolve_domain_path_uses_domains_prefix(self, tmp_path: Path) -> None:
        """Path is under domains/ directory."""
        domain_name = "test-domain"
        domain_dir = tmp_path / "domains" / domain_name
        _make_goal_md(domain_dir)

        from entrypoint.startup import resolve_domain

        result = resolve_domain(domain_name, project_root=tmp_path)
        assert "domains" in result.parts


# ---------------------------------------------------------------------------
# AC-002: DomainNotFoundError raised for non-existent domain
# ---------------------------------------------------------------------------


class TestDomainNotFoundError:
    """AC-002: DomainNotFoundError raised for non-existent domain."""

    def test_nonexistent_domain_raises_domain_not_found_error(self, tmp_path: Path) -> None:
        """BDD: Startup with non-existent domain directory."""
        from entrypoint.startup import DomainNotFoundError, resolve_domain

        with pytest.raises(DomainNotFoundError, match="nonexistent-domain"):
            resolve_domain("nonexistent-domain", project_root=tmp_path)

    def test_domain_not_found_error_is_exception_subclass(self) -> None:
        """DomainNotFoundError inherits from Exception."""
        from entrypoint.startup import DomainNotFoundError

        assert issubclass(DomainNotFoundError, Exception)

    def test_domain_not_found_error_includes_domain_name(self, tmp_path: Path) -> None:
        """Error message includes the missing domain name."""
        from entrypoint.startup import DomainNotFoundError, resolve_domain

        with pytest.raises(DomainNotFoundError) as exc_info:
            resolve_domain("missing-domain", project_root=tmp_path)
        assert "missing-domain" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC-003: Error raised for missing GOAL.md
# ---------------------------------------------------------------------------


class TestMissingGoalMd:
    """AC-003: Error raised for missing GOAL.md in domain directory."""

    def test_missing_goal_md_raises_error(self, tmp_path: Path) -> None:
        """BDD: Startup with missing GOAL.md in domain directory."""
        domain_name = "no-goal-domain"
        domain_dir = tmp_path / "domains" / domain_name
        domain_dir.mkdir(parents=True)
        # No GOAL.md created

        from entrypoint.startup import resolve_domain

        with pytest.raises(FileNotFoundError, match="GOAL.md"):
            resolve_domain(domain_name, project_root=tmp_path)

    def test_missing_goal_md_error_message_includes_path(self, tmp_path: Path) -> None:
        """Error message includes path to expected GOAL.md."""
        domain_name = "no-goal-domain"
        domain_dir = tmp_path / "domains" / domain_name
        domain_dir.mkdir(parents=True)

        from entrypoint.startup import resolve_domain

        with pytest.raises(FileNotFoundError) as exc_info:
            resolve_domain(domain_name, project_root=tmp_path)
        assert "GOAL.md" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC-004: ChromaDB collection verified to contain chunks
# ---------------------------------------------------------------------------


class TestChromaDBCollectionVerified:
    """AC-004: ChromaDB collection verified to contain chunks."""

    def test_collection_with_chunks_passes(self) -> None:
        """BDD: ChromaDB collection is verified to contain chunks."""
        from entrypoint.startup import verify_chromadb_collection

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 42
        mock_client.get_collection.return_value = mock_collection

        # Should not raise
        result = verify_chromadb_collection("test-domain", client=mock_client)
        assert result is mock_collection

    def test_collection_get_uses_domain_name(self) -> None:
        """Collection name matches domain name (DDR-003)."""
        from entrypoint.startup import verify_chromadb_collection

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 10
        mock_client.get_collection.return_value = mock_collection

        verify_chromadb_collection("my-domain", client=mock_client)
        mock_client.get_collection.assert_called_once_with(name="my-domain")


# ---------------------------------------------------------------------------
# AC-005: Error raised for empty collection with ingestion suggestion
# ---------------------------------------------------------------------------


class TestEmptyCollectionError:
    """AC-005: Error raised for empty collection with ingestion suggestion."""

    def test_empty_collection_raises_runtime_error(self) -> None:
        """BDD: Startup with empty ChromaDB collection."""
        from entrypoint.startup import verify_chromadb_collection

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_client.get_collection.return_value = mock_collection

        with pytest.raises(RuntimeError, match="No chunks found"):
            verify_chromadb_collection("test-domain", client=mock_client)

    def test_empty_collection_error_includes_ingestion_command(self) -> None:
        """Error message includes the ingestion command to run."""
        from entrypoint.startup import verify_chromadb_collection

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_client.get_collection.return_value = mock_collection

        with pytest.raises(RuntimeError) as exc_info:
            verify_chromadb_collection("gcse-english-tutor", client=mock_client)

        error_msg = str(exc_info.value)
        assert "gcse-english-tutor" in error_msg
        assert "python -m ingestion.ingest --domain gcse-english-tutor" in error_msg


# ---------------------------------------------------------------------------
# AC-006: Error raised when ChromaDB service unavailable
# ---------------------------------------------------------------------------


class TestChromaDBUnavailable:
    """AC-006: Error raised when ChromaDB service is unavailable at startup."""

    def test_chromadb_connection_error_raises(self) -> None:
        """BDD: ChromaDB service is unavailable at startup."""
        from entrypoint.startup import verify_chromadb_collection

        mock_client = MagicMock()
        mock_client.get_collection.side_effect = Exception(
            "ChromaDB connection refused"
        )

        with pytest.raises(ConnectionError, match="ChromaDB"):
            verify_chromadb_collection("test-domain", client=mock_client)

    def test_chromadb_missing_collection_raises_connection_error(self) -> None:
        """Missing collection raises with actionable message."""
        from entrypoint.startup import verify_chromadb_collection

        mock_client = MagicMock()
        mock_client.get_collection.side_effect = ValueError(
            "Collection test-domain does not exist"
        )

        with pytest.raises(ConnectionError):
            verify_chromadb_collection("test-domain", client=mock_client)

    def test_default_client_creation_failure_raises_connection_error(self) -> None:
        """When no client provided and chromadb init fails, raises ConnectionError."""
        from entrypoint.startup import verify_chromadb_collection

        mock_chromadb = MagicMock()
        mock_chromadb.PersistentClient.side_effect = RuntimeError("disk full")

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            with pytest.raises(ConnectionError, match="ChromaDB client initialisation"):
                verify_chromadb_collection("test-domain")

    def test_default_client_creation_success_uses_persistent_client(self) -> None:
        """When no client provided, creates PersistentClient and queries collection."""
        from entrypoint.startup import verify_chromadb_collection

        mock_collection = MagicMock()
        mock_collection.count.return_value = 5

        mock_chromadb = MagicMock()
        mock_persistent_client = MagicMock()
        mock_persistent_client.get_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_persistent_client

        with patch.dict("sys.modules", {"chromadb": mock_chromadb}):
            result = verify_chromadb_collection("my-domain")

        mock_chromadb.PersistentClient.assert_called_once_with(path="./chroma_data")
        mock_persistent_client.get_collection.assert_called_once_with(name="my-domain")
        assert result is mock_collection


# ---------------------------------------------------------------------------
# AC-007: LANGSMITH_PROJECT set to "adf-{domain}"
# ---------------------------------------------------------------------------


class TestLangSmithProject:
    """AC-007: LANGSMITH_PROJECT set to 'adf-{domain}'."""

    def test_langsmith_project_set_from_domain(self) -> None:
        """BDD: LangSmith project environment variable is set from the domain."""
        from entrypoint.startup import configure_langsmith

        config = _make_agent_config("gcse-english-tutor")

        with patch.dict(os.environ, {}, clear=False):
            configure_langsmith(config)
            assert os.environ["LANGSMITH_PROJECT"] == "adf-gcse-english-tutor"

    def test_langsmith_project_uses_domain_name(self) -> None:
        """LANGSMITH_PROJECT uses the exact domain name with adf- prefix."""
        from entrypoint.startup import configure_langsmith

        config = _make_agent_config("custom-domain-name")

        with patch.dict(os.environ, {}, clear=False):
            configure_langsmith(config)
            assert os.environ["LANGSMITH_PROJECT"] == "adf-custom-domain-name"


# ---------------------------------------------------------------------------
# AC-008: Warning logged if tracing enabled without API key
# ---------------------------------------------------------------------------


class TestLangSmithTracingWarning:
    """AC-008: Warning logged if tracing enabled but API key is missing."""

    def test_tracing_without_api_key_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """BDD: LangSmith tracing enabled but API key is missing."""
        from entrypoint.startup import configure_langsmith

        config = _make_agent_config("test-domain")

        env = {"LANGSMITH_TRACING": "true"}
        # Ensure LANGSMITH_API_KEY is NOT set
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("LANGSMITH_API_KEY", None)
            with caplog.at_level(logging.WARNING):
                configure_langsmith(config)

        assert any(
            "LANGSMITH_API_KEY" in msg
            for msg in caplog.messages
        ), f"Expected warning about LANGSMITH_API_KEY, got: {caplog.messages}"

    def test_tracing_without_api_key_does_not_raise(self) -> None:
        """ASSUM-004: Warn but don't block if tracing enabled without key."""
        from entrypoint.startup import configure_langsmith

        config = _make_agent_config("test-domain")

        env = {"LANGSMITH_TRACING": "true"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("LANGSMITH_API_KEY", None)
            # Should NOT raise — just warn
            configure_langsmith(config)

    def test_no_warning_when_api_key_present(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No warning when both tracing and API key are set."""
        from entrypoint.startup import configure_langsmith

        config = _make_agent_config("test-domain")

        env = {"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": "lsv2_abc123"}
        with patch.dict(os.environ, env, clear=False):
            with caplog.at_level(logging.WARNING):
                configure_langsmith(config)

        warning_messages = [
            msg for msg in caplog.messages if "LANGSMITH_API_KEY" in msg
        ]
        assert len(warning_messages) == 0

    def test_no_warning_when_tracing_not_enabled(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No warning when LANGSMITH_TRACING is not 'true'."""
        from entrypoint.startup import configure_langsmith

        config = _make_agent_config("test-domain")

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LANGSMITH_TRACING", None)
            os.environ.pop("LANGSMITH_API_KEY", None)
            with caplog.at_level(logging.WARNING):
                configure_langsmith(config)

        warning_messages = [
            msg for msg in caplog.messages if "LANGSMITH_API_KEY" in msg
        ]
        assert len(warning_messages) == 0
