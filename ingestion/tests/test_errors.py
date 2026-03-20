"""Tests for ingestion error hierarchy.

Follows the existing test patterns in domain_config/tests/test_models.py:
- Organised by test class per error class
- AAA pattern (Arrange, Act, Assert)
- pytest.raises for negative cases
- Naming: test_<method_name>_<scenario>_<expected_result>
"""

from __future__ import annotations

import pytest

from ingestion.errors import (
    DoclingError,
    DomainNotFoundError,
    GoalValidationError,
    IndexingError,
    IngestionError,
)


# ---------------------------------------------------------------------------
# IngestionError (base class) tests
# ---------------------------------------------------------------------------


class TestIngestionError:
    def test_is_exception_subclass(self):
        assert issubclass(IngestionError, Exception)

    def test_can_be_instantiated(self):
        err = IngestionError("something went wrong")
        assert str(err) == "something went wrong"

    def test_can_be_raised_and_caught(self):
        with pytest.raises(IngestionError):
            raise IngestionError("test")

    def test_empty_message(self):
        err = IngestionError()
        assert isinstance(err, Exception)

    def test_catching_as_exception(self):
        """IngestionError should be catchable via generic Exception."""
        with pytest.raises(Exception):
            raise IngestionError("test")


# ---------------------------------------------------------------------------
# DomainNotFoundError tests
# ---------------------------------------------------------------------------


class TestDomainNotFoundError:
    def test_is_ingestion_error_subclass(self):
        assert issubclass(DomainNotFoundError, IngestionError)

    def test_is_exception_subclass(self):
        assert issubclass(DomainNotFoundError, Exception)

    def test_can_be_instantiated(self):
        err = DomainNotFoundError("domain 'foo' not found")
        assert str(err) == "domain 'foo' not found"

    def test_can_be_raised_and_caught_as_domain_error(self):
        with pytest.raises(DomainNotFoundError):
            raise DomainNotFoundError("missing")

    def test_can_be_caught_as_ingestion_error(self):
        with pytest.raises(IngestionError):
            raise DomainNotFoundError("missing")


# ---------------------------------------------------------------------------
# GoalValidationError tests
# ---------------------------------------------------------------------------


class TestGoalValidationError:
    def test_is_ingestion_error_subclass(self):
        assert issubclass(GoalValidationError, IngestionError)

    def test_is_exception_subclass(self):
        assert issubclass(GoalValidationError, Exception)

    def test_can_be_instantiated(self):
        err = GoalValidationError("GOAL.md missing")
        assert str(err) == "GOAL.md missing"

    def test_can_be_raised_and_caught_as_goal_error(self):
        with pytest.raises(GoalValidationError):
            raise GoalValidationError("invalid source docs")

    def test_can_be_caught_as_ingestion_error(self):
        with pytest.raises(IngestionError):
            raise GoalValidationError("missing")


# ---------------------------------------------------------------------------
# DoclingError tests
# ---------------------------------------------------------------------------


class TestDoclingError:
    def test_is_ingestion_error_subclass(self):
        assert issubclass(DoclingError, IngestionError)

    def test_is_exception_subclass(self):
        assert issubclass(DoclingError, Exception)

    def test_can_be_instantiated(self):
        err = DoclingError("failed to process document.pdf")
        assert str(err) == "failed to process document.pdf"

    def test_can_be_raised_and_caught_as_docling_error(self):
        with pytest.raises(DoclingError):
            raise DoclingError("processing failure")

    def test_can_be_caught_as_ingestion_error(self):
        with pytest.raises(IngestionError):
            raise DoclingError("processing failure")


# ---------------------------------------------------------------------------
# IndexingError tests
# ---------------------------------------------------------------------------


class TestIndexingError:
    def test_is_ingestion_error_subclass(self):
        assert issubclass(IndexingError, IngestionError)

    def test_is_exception_subclass(self):
        assert issubclass(IndexingError, Exception)

    def test_can_be_instantiated(self):
        err = IndexingError("ChromaDB connection refused")
        assert str(err) == "ChromaDB connection refused"

    def test_can_be_raised_and_caught_as_indexing_error(self):
        with pytest.raises(IndexingError):
            raise IndexingError("indexing failure")

    def test_can_be_caught_as_ingestion_error(self):
        with pytest.raises(IngestionError):
            raise IndexingError("indexing failure")


# ---------------------------------------------------------------------------
# Inheritance chain verification (AC-006)
# ---------------------------------------------------------------------------


class TestInheritanceChain:
    """Verify the full error hierarchy matches the specification."""

    @pytest.mark.parametrize(
        "error_cls",
        [DomainNotFoundError, GoalValidationError, DoclingError, IndexingError],
    )
    def test_all_errors_inherit_from_ingestion_error(self, error_cls):
        assert issubclass(error_cls, IngestionError)

    @pytest.mark.parametrize(
        "error_cls",
        [
            IngestionError,
            DomainNotFoundError,
            GoalValidationError,
            DoclingError,
            IndexingError,
        ],
    )
    def test_all_errors_inherit_from_exception(self, error_cls):
        assert issubclass(error_cls, Exception)

    def test_ingestion_error_direct_parent_is_exception(self):
        assert IngestionError.__bases__ == (Exception,)

    @pytest.mark.parametrize(
        "error_cls",
        [DomainNotFoundError, GoalValidationError, DoclingError, IndexingError],
    )
    def test_child_direct_parent_is_ingestion_error(self, error_cls):
        assert IngestionError in error_cls.__bases__

    def test_all_five_error_classes_exist(self):
        """Verify all 5 error classes are present in the module."""
        from ingestion import errors

        expected = {
            "IngestionError",
            "DomainNotFoundError",
            "GoalValidationError",
            "DoclingError",
            "IndexingError",
        }
        actual = set(errors.__all__)
        assert expected == actual


# ---------------------------------------------------------------------------
# Import contract tests (AC-002)
# ---------------------------------------------------------------------------


class TestErrorImportContracts:
    def test_all_errors_importable_from_errors_module(self):
        from ingestion.errors import (
            DoclingError,
            DomainNotFoundError,
            GoalValidationError,
            IndexingError,
            IngestionError,
        )

        assert all(
            cls is not None
            for cls in [
                IngestionError,
                DomainNotFoundError,
                GoalValidationError,
                DoclingError,
                IndexingError,
            ]
        )

    def test_all_errors_importable_from_package(self):
        from ingestion import (
            DoclingError,
            DomainNotFoundError,
            GoalValidationError,
            IndexingError,
            IngestionError,
        )

        assert all(
            cls is not None
            for cls in [
                IngestionError,
                DomainNotFoundError,
                GoalValidationError,
                DoclingError,
                IndexingError,
            ]
        )

    def test_all_errors_in_package_all(self):
        import ingestion

        for name in [
            "IngestionError",
            "DomainNotFoundError",
            "GoalValidationError",
            "DoclingError",
            "IndexingError",
        ]:
            assert name in ingestion.__all__
