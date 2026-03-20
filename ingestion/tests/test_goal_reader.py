"""Tests for ingestion/goal_reader.py — GOAL.md Source Documents reader.

Covers all 9 acceptance criteria for TASK-ING-005:
- AC-001: read_source_documents() parses Source Documents from GOAL.md
- AC-002: resolve_source_files() expands glob patterns against sources/ dir
- AC-003: Missing domain directory raises DomainNotFoundError
- AC-004: Missing GOAL.md raises GoalValidationError
- AC-005: Malformed Source Documents section raises GoalValidationError
- AC-006: No matching files raises GoalValidationError with descriptive message
- AC-007: Path traversal patterns rejected with error logged
- AC-008: Resolved files returned as (absolute_path, mode) tuples
- AC-009: All modified files pass lint/format checks (verified by ruff)

Organisation:
- TestReadSourceDocuments: AC-001, AC-003, AC-004, AC-005
- TestResolveSourceFiles: AC-002, AC-006, AC-007, AC-008
- TestImportContracts: export verification
- TestSeamContract: seam test for SourceDocument contract
"""

from __future__ import annotations

import logging
import textwrap
from pathlib import Path

import pytest

from ingestion.errors import DomainNotFoundError, GoalValidationError
from ingestion.goal_reader import (
    _extract_source_documents_section,
    _has_path_traversal,
    _parse_source_documents_table,
    read_source_documents,
    resolve_source_files,
)
from ingestion.models import SourceDocument


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


VALID_SOURCE_DOCS_TABLE = textwrap.dedent("""\
    | File Pattern | Mode | Notes |
    |---|---|---|
    | mr-bruff-*.pdf | standard | Digital PDFs |
    | scanned-*.pdf | vlm | Scanned pages |
""")


VALID_GOAL_MD = textwrap.dedent("""\
    ## Goal

    Fine-tune a GCSE English Literature tutor that guides Year 10 students
    through AQA exam preparation using Socratic questioning.

    ## Source Documents

    | File Pattern | Mode | Notes |
    |---|---|---|
    | mr-bruff-*.pdf | standard | Digital PDFs |
    | scanned-*.pdf | vlm | Scanned pages |

    ## System Prompt

    You are a GCSE English Literature tutor.

    ## Generation Targets

    | Category | Type | Count |
    |---|---|---|
    | Analysis | reasoning | 200 |

    ## Generation Guidelines

    Generate training examples for GCSE English Literature.

    ## Evaluation Criteria

    | Criterion | Description | Weight |
    |---|---|---|
    | socratic_approach | Guides via questions | 25% |

    ## Output Schema

    ```json
    {"messages": [], "metadata": {}}
    ```

    ## Metadata Schema

    | Field | Type | Required | Valid Values |
    |---|---|---|---|
    | layer | string | yes | behaviour, knowledge |

    ## Layer Routing

    | Layer | Destination |
    |---|---|
    | behaviour | output/train.jsonl |
""")


@pytest.fixture
def domain_dir(tmp_path: Path) -> Path:
    """Create a temporary domain directory with valid GOAL.md and sources."""
    domain = tmp_path / "domains" / "test-domain"
    domain.mkdir(parents=True)

    # Write GOAL.md
    (domain / "GOAL.md").write_text(VALID_GOAL_MD, encoding="utf-8")

    # Create sources directory with matching files
    sources = domain / "sources"
    sources.mkdir()
    (sources / "mr-bruff-language.pdf").write_text("PDF content 1")
    (sources / "mr-bruff-literature.pdf").write_text("PDF content 2")
    (sources / "scanned-page1.pdf").write_text("PDF content 3")
    (sources / "unmatched-file.pdf").write_text("PDF content 4")

    return domain


@pytest.fixture
def empty_domain(tmp_path: Path) -> Path:
    """Create a domain directory with no GOAL.md."""
    domain = tmp_path / "domains" / "empty-domain"
    domain.mkdir(parents=True)
    return domain


@pytest.fixture
def domain_no_sources(tmp_path: Path) -> Path:
    """Create a domain with GOAL.md but no sources directory."""
    domain = tmp_path / "domains" / "no-sources"
    domain.mkdir(parents=True)
    (domain / "GOAL.md").write_text(VALID_GOAL_MD, encoding="utf-8")
    return domain


@pytest.fixture
def domain_empty_sources(tmp_path: Path) -> Path:
    """Create a domain with GOAL.md and empty sources directory."""
    domain = tmp_path / "domains" / "empty-sources"
    domain.mkdir(parents=True)
    (domain / "GOAL.md").write_text(VALID_GOAL_MD, encoding="utf-8")
    (domain / "sources").mkdir()
    return domain


# ---------------------------------------------------------------------------
# Internal helper tests
# ---------------------------------------------------------------------------


class TestHasPathTraversal:
    def test_no_traversal(self):
        assert _has_path_traversal("normal-file.pdf") is False

    def test_dotdot_slash(self):
        assert _has_path_traversal("../etc/passwd") is True

    def test_dotdot_backslash(self):
        assert _has_path_traversal("..\\etc\\passwd") is True

    def test_embedded_dotdot(self):
        assert _has_path_traversal("foo/../bar.pdf") is True

    def test_single_dot(self):
        assert _has_path_traversal("./normal.pdf") is False

    def test_dotdot_in_filename(self):
        """Filenames like 'foo..bar' should NOT be flagged."""
        assert _has_path_traversal("foo..bar.pdf") is False


class TestExtractSourceDocumentsSection:
    def test_extracts_section_body(self):
        body = _extract_source_documents_section(VALID_GOAL_MD)
        assert "File Pattern" in body
        assert "mr-bruff-*.pdf" in body

    def test_missing_section_raises_error(self):
        no_section = "## Goal\n\nSome goal text\n"
        with pytest.raises(GoalValidationError, match="Source Documents"):
            _extract_source_documents_section(no_section)


class TestParseSourceDocumentsTable:
    def test_parses_valid_table(self):
        docs = _parse_source_documents_table(VALID_SOURCE_DOCS_TABLE)
        assert len(docs) == 2
        assert docs[0].file_pattern == "mr-bruff-*.pdf"
        assert docs[0].mode == "standard"
        assert docs[0].notes == "Digital PDFs"
        assert docs[1].file_pattern == "scanned-*.pdf"
        assert docs[1].mode == "vlm"

    def test_empty_section_raises_error(self):
        with pytest.raises(GoalValidationError, match="empty"):
            _parse_source_documents_table("")

    def test_whitespace_only_raises_error(self):
        with pytest.raises(GoalValidationError, match="empty"):
            _parse_source_documents_table("   \n  \n   ")

    def test_missing_required_columns_raises_error(self):
        bad_table = "| Name | Type |\n|---|---|\n| foo | bar |\n"
        with pytest.raises(GoalValidationError, match="missing required columns"):
            _parse_source_documents_table(bad_table)

    def test_no_data_rows_raises_error(self):
        header_only = "| File Pattern | Mode | Notes |\n|---|---|---|\n"
        with pytest.raises(GoalValidationError, match="no valid data rows"):
            _parse_source_documents_table(header_only)

    def test_invalid_mode_raises_error(self):
        bad_mode = "| File Pattern | Mode | Notes |\n|---|---|---|\n| foo.pdf | ocr | Bad mode |\n"
        with pytest.raises(GoalValidationError, match="Invalid Source Documents row"):
            _parse_source_documents_table(bad_mode)

    def test_table_without_notes_column(self):
        """Notes column is optional -- table with only Pattern + Mode should work."""
        table = "| File Pattern | Mode |\n|---|---|\n| foo.pdf | standard |\n"
        docs = _parse_source_documents_table(table)
        assert len(docs) == 1
        assert docs[0].file_pattern == "foo.pdf"
        assert docs[0].notes == ""

    def test_extra_whitespace_in_cells(self):
        table = (
            "|  File Pattern   |  Mode   |  Notes   |\n"
            "|---|---|---|\n"
            "|  mr-bruff-*.pdf   |  standard   |  Digital PDFs   |\n"
        )
        docs = _parse_source_documents_table(table)
        assert docs[0].file_pattern == "mr-bruff-*.pdf"
        assert docs[0].mode == "standard"
        assert docs[0].notes == "Digital PDFs"


# ---------------------------------------------------------------------------
# AC-001: read_source_documents() parses Source Documents from GOAL.md
# ---------------------------------------------------------------------------


class TestReadSourceDocuments:
    """Tests for read_source_documents() function."""

    def test_parses_valid_goal_md(self, domain_dir: Path):
        """AC-001: Parses Source Documents from a valid GOAL.md."""
        docs = read_source_documents(domain_dir)
        assert len(docs) == 2
        assert all(isinstance(d, SourceDocument) for d in docs)

    def test_returns_correct_file_patterns(self, domain_dir: Path):
        """AC-001: Returns correct file patterns from the table."""
        docs = read_source_documents(domain_dir)
        patterns = {d.file_pattern for d in docs}
        assert "mr-bruff-*.pdf" in patterns
        assert "scanned-*.pdf" in patterns

    def test_returns_correct_modes(self, domain_dir: Path):
        """AC-001: Returns correct modes from the table."""
        docs = read_source_documents(domain_dir)
        modes = {d.file_pattern: d.mode for d in docs}
        assert modes["mr-bruff-*.pdf"] == "standard"
        assert modes["scanned-*.pdf"] == "vlm"

    def test_returns_notes(self, domain_dir: Path):
        """AC-001: Returns notes from the table."""
        docs = read_source_documents(domain_dir)
        notes = {d.file_pattern: d.notes for d in docs}
        assert notes["mr-bruff-*.pdf"] == "Digital PDFs"

    # --- AC-003: Missing domain directory raises DomainNotFoundError ---

    def test_missing_domain_raises_domain_not_found_error(self, tmp_path: Path):
        """AC-003: Non-existent domain directory raises DomainNotFoundError."""
        with pytest.raises(DomainNotFoundError, match="not found"):
            read_source_documents(tmp_path / "nonexistent")

    def test_domain_not_found_is_ingestion_error(self, tmp_path: Path):
        """AC-003: DomainNotFoundError is catchable as IngestionError."""
        from ingestion.errors import IngestionError

        with pytest.raises(IngestionError):
            read_source_documents(tmp_path / "nonexistent")

    # --- AC-004: Missing GOAL.md raises GoalValidationError ---

    def test_missing_goal_md_raises_goal_validation_error(self, empty_domain: Path):
        """AC-004: Domain without GOAL.md raises GoalValidationError."""
        with pytest.raises(GoalValidationError, match="GOAL.md not found"):
            read_source_documents(empty_domain)

    # --- AC-005: Malformed Source Documents section raises GoalValidationError ---

    def test_malformed_source_docs_raises_goal_validation_error(self, tmp_path: Path):
        """AC-005: Malformed Source Documents section raises GoalValidationError."""
        domain = tmp_path / "bad-domain"
        domain.mkdir(parents=True)
        # GOAL.md without Source Documents section
        (domain / "GOAL.md").write_text("## Goal\n\nSome goal text\n", encoding="utf-8")
        with pytest.raises(GoalValidationError, match="Source Documents"):
            read_source_documents(domain)

    def test_malformed_table_raises_goal_validation_error(self, tmp_path: Path):
        """AC-005: Malformed table format raises GoalValidationError."""
        domain = tmp_path / "bad-table-domain"
        domain.mkdir(parents=True)
        bad_goal = textwrap.dedent("""\
            ## Goal

            Some goal text

            ## Source Documents

            This is not a table at all.

            ## System Prompt

            Prompt text.
        """)
        (domain / "GOAL.md").write_text(bad_goal, encoding="utf-8")
        with pytest.raises(GoalValidationError):
            read_source_documents(domain)

    def test_empty_goal_md_raises_error(self, tmp_path: Path):
        """AC-005: Empty GOAL.md raises GoalValidationError."""
        domain = tmp_path / "empty-goal"
        domain.mkdir(parents=True)
        (domain / "GOAL.md").write_text("", encoding="utf-8")
        with pytest.raises(GoalValidationError):
            read_source_documents(domain)

    def test_single_source_document(self, tmp_path: Path):
        """AC-001: A GOAL.md with exactly one source document row should work."""
        domain = tmp_path / "single-doc"
        domain.mkdir(parents=True)
        goal = VALID_GOAL_MD.replace("| scanned-*.pdf | vlm | Scanned pages |\n", "")
        (domain / "GOAL.md").write_text(goal, encoding="utf-8")
        docs = read_source_documents(domain)
        assert len(docs) == 1
        assert docs[0].file_pattern == "mr-bruff-*.pdf"


# ---------------------------------------------------------------------------
# AC-002, AC-006, AC-007, AC-008: resolve_source_files() tests
# ---------------------------------------------------------------------------


class TestResolveSourceFiles:
    """Tests for resolve_source_files() function."""

    # --- AC-002: Expands glob patterns ---

    def test_expands_glob_patterns(self, domain_dir: Path):
        """AC-002: Glob patterns are expanded against sources/ directory."""
        docs = read_source_documents(domain_dir)
        resolved = resolve_source_files(domain_dir, docs)
        filenames = {p.name for p, _ in resolved}
        assert "mr-bruff-language.pdf" in filenames
        assert "mr-bruff-literature.pdf" in filenames
        assert "scanned-page1.pdf" in filenames

    def test_unmatched_files_excluded(self, domain_dir: Path):
        """AC-002: Files not matching patterns are not included."""
        docs = read_source_documents(domain_dir)
        resolved = resolve_source_files(domain_dir, docs)
        filenames = {p.name for p, _ in resolved}
        assert "unmatched-file.pdf" not in filenames

    def test_multiple_patterns_resolved(self, domain_dir: Path):
        """AC-002: Multiple patterns produce combined results."""
        docs = read_source_documents(domain_dir)
        resolved = resolve_source_files(domain_dir, docs)
        # 2 mr-bruff + 1 scanned = 3 matched files
        assert len(resolved) == 3

    # --- AC-008: Returned as (absolute_path, mode) tuples ---

    def test_returns_absolute_path_tuples(self, domain_dir: Path):
        """AC-008: Resolved files are (absolute_path, mode) tuples."""
        docs = read_source_documents(domain_dir)
        resolved = resolve_source_files(domain_dir, docs)
        for file_path, mode in resolved:
            assert isinstance(file_path, Path)
            assert file_path.is_absolute(), f"Path should be absolute: {file_path}"
            assert isinstance(mode, str)

    def test_mode_matches_source_document(self, domain_dir: Path):
        """AC-008: Mode in tuple matches the SourceDocument's mode."""
        docs = read_source_documents(domain_dir)
        resolved = resolve_source_files(domain_dir, docs)
        for file_path, mode in resolved:
            if "mr-bruff" in file_path.name:
                assert mode == "standard"
            elif "scanned" in file_path.name:
                assert mode == "vlm"

    def test_resolved_paths_exist(self, domain_dir: Path):
        """AC-008: All resolved paths point to actual files."""
        docs = read_source_documents(domain_dir)
        resolved = resolve_source_files(domain_dir, docs)
        for file_path, _ in resolved:
            assert file_path.exists(), f"File should exist: {file_path}"

    # --- AC-006: No matching files raises GoalValidationError ---

    def test_no_matching_files_raises_error(self, domain_empty_sources: Path):
        """AC-006: No matched files raises GoalValidationError with message."""
        docs = [SourceDocument(file_pattern="nonexistent-*.pdf", mode="standard")]
        with pytest.raises(GoalValidationError, match="No source files found"):
            resolve_source_files(domain_empty_sources, docs)

    def test_no_match_error_includes_patterns(self, domain_empty_sources: Path):
        """AC-006: Error message includes the patterns that failed to match."""
        docs = [SourceDocument(file_pattern="foo-*.pdf", mode="standard")]
        with pytest.raises(GoalValidationError, match="foo-\\*.pdf"):
            resolve_source_files(domain_empty_sources, docs)

    def test_missing_sources_dir_raises_error(self, domain_no_sources: Path):
        """AC-006: Missing sources/ directory raises GoalValidationError."""
        docs = [SourceDocument(file_pattern="*.pdf", mode="standard")]
        with pytest.raises(GoalValidationError, match="Sources directory not found"):
            resolve_source_files(domain_no_sources, docs)

    # --- AC-007: Path traversal patterns rejected ---

    def test_path_traversal_pattern_rejected(
        self, domain_dir: Path, caplog: pytest.LogCaptureFixture
    ):
        """AC-007: Pattern with ../ is rejected and logged."""
        docs = [SourceDocument(file_pattern="../etc/passwd", mode="standard")]
        with caplog.at_level(logging.ERROR):
            with pytest.raises(GoalValidationError, match="No source files found"):
                resolve_source_files(domain_dir, docs)
        assert "path traversal" in caplog.text.lower()

    def test_path_traversal_backslash_rejected(
        self, domain_dir: Path, caplog: pytest.LogCaptureFixture
    ):
        """AC-007: Pattern with ..\\ is rejected and logged."""
        docs = [SourceDocument(file_pattern="..\\etc\\passwd", mode="standard")]
        with caplog.at_level(logging.ERROR):
            with pytest.raises(GoalValidationError, match="No source files found"):
                resolve_source_files(domain_dir, docs)
        assert "path traversal" in caplog.text.lower()

    def test_path_traversal_in_filename_rejected(self, domain_dir: Path):
        """AC-007: Legitimate files never contain path traversal in name."""
        docs = [SourceDocument(file_pattern="*.pdf", mode="standard")]
        resolved = resolve_source_files(domain_dir, docs)
        # All legitimate files should be resolved without traversal
        for file_path, _ in resolved:
            assert ".." not in str(file_path.name)

    # --- De-duplication ---

    def test_deduplicates_across_patterns(self, tmp_path: Path):
        """Files matching multiple patterns are only returned once."""
        domain = tmp_path / "dedup-domain"
        domain.mkdir(parents=True)

        goal_text = VALID_GOAL_MD.replace(
            "| scanned-*.pdf | vlm | Scanned pages |",
            "| *.pdf | vlm | All PDFs |",
        )
        (domain / "GOAL.md").write_text(goal_text, encoding="utf-8")

        sources = domain / "sources"
        sources.mkdir()
        (sources / "mr-bruff-language.pdf").write_text("content")

        docs = read_source_documents(domain)
        resolved = resolve_source_files(domain, docs)

        # mr-bruff-language.pdf matches both "mr-bruff-*.pdf" and "*.pdf"
        # but should only appear once
        filenames = [p.name for p, _ in resolved]
        assert filenames.count("mr-bruff-language.pdf") == 1

    # --- Exact file pattern matching ---

    def test_exact_filename_pattern(self, tmp_path: Path):
        """An exact filename (no glob) should resolve correctly."""
        domain = tmp_path / "exact-domain"
        domain.mkdir(parents=True)

        goal_text = VALID_GOAL_MD.replace(
            "| mr-bruff-*.pdf | standard | Digital PDFs |",
            "| exact-file.pdf | standard | Exact file |",
        ).replace(
            "| scanned-*.pdf | vlm | Scanned pages |",
            "",
        )
        (domain / "GOAL.md").write_text(goal_text, encoding="utf-8")

        sources = domain / "sources"
        sources.mkdir()
        (sources / "exact-file.pdf").write_text("content")

        docs = read_source_documents(domain)
        resolved = resolve_source_files(domain, docs)
        assert len(resolved) == 1
        assert resolved[0][0].name == "exact-file.pdf"
        assert resolved[0][1] == "standard"


# ---------------------------------------------------------------------------
# Import contract tests
# ---------------------------------------------------------------------------


class TestImportContracts:
    """Verify public API exports from the ingestion package."""

    def test_read_source_documents_importable_from_module(self):
        from ingestion.goal_reader import read_source_documents

        assert callable(read_source_documents)

    def test_resolve_source_files_importable_from_module(self):
        from ingestion.goal_reader import resolve_source_files

        assert callable(resolve_source_files)

    def test_read_source_documents_importable_from_package(self):
        from ingestion import read_source_documents

        assert callable(read_source_documents)

    def test_resolve_source_files_importable_from_package(self):
        from ingestion import resolve_source_files

        assert callable(resolve_source_files)

    def test_functions_in_package_all(self):
        import ingestion

        assert "read_source_documents" in ingestion.__all__
        assert "resolve_source_files" in ingestion.__all__

    def test_functions_in_module_all(self):
        from ingestion import goal_reader

        assert "read_source_documents" in goal_reader.__all__
        assert "resolve_source_files" in goal_reader.__all__


# ---------------------------------------------------------------------------
# Seam test (from task definition)
# ---------------------------------------------------------------------------


@pytest.mark.seam
@pytest.mark.integration_contract("SourceDocument")
class TestSeamContract:
    """Seam test: verify SourceDocument contract from TASK-DC-001."""

    def test_source_document_format(self):
        """Verify SourceDocument matches the expected format.

        Contract: SourceDocument model with file_pattern (str),
        mode (Literal['standard', 'vlm']), and notes (str) fields.
        Producer: TASK-DC-001.
        """
        doc = SourceDocument(file_pattern="*.pdf", mode="standard", notes="test")
        assert hasattr(doc, "file_pattern")
        assert hasattr(doc, "mode")
        assert doc.mode in ("standard", "vlm")
        assert hasattr(doc, "notes")

    def test_source_document_vlm_mode(self):
        doc = SourceDocument(file_pattern="scanned-*.pdf", mode="vlm", notes="scanned")
        assert doc.mode == "vlm"
