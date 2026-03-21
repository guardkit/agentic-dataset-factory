"""Validate domain directory structure and source documents inventory.

Ensures that:
- AC-001: Directory domains/gcse-english-tutor/ exists
- AC-002: Directory domains/gcse-english-tutor/sources/ exists with .gitkeep
- AC-003: Skeleton GOAL.md exists with all 9 section headings
- AC-004: .gitignore entry excludes domains/*/sources/*.pdf

References TASK-GG-001 acceptance criteria AC-001 through AC-004.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Resolve project root relative to this test file
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestDomainDirectoryExists:
    """AC-001: Directory domains/gcse-english-tutor/ exists."""

    def test_domain_directory_exists(self) -> None:
        """domains/gcse-english-tutor/ must exist as a directory."""
        domain_dir = PROJECT_ROOT / "domains" / "gcse-english-tutor"
        assert domain_dir.is_dir(), f"{domain_dir} does not exist or is not a directory"

    def test_domains_parent_directory_exists(self) -> None:
        """domains/ parent directory must exist."""
        domains_dir = PROJECT_ROOT / "domains"
        assert domains_dir.is_dir(), f"{domains_dir} does not exist"


class TestSourcesDirectoryWithGitkeep:
    """AC-002: Directory domains/gcse-english-tutor/sources/ exists with .gitkeep."""

    def test_sources_directory_exists(self) -> None:
        """domains/gcse-english-tutor/sources/ must exist as a directory."""
        sources_dir = PROJECT_ROOT / "domains" / "gcse-english-tutor" / "sources"
        assert sources_dir.is_dir(), f"{sources_dir} does not exist or is not a directory"

    def test_sources_gitkeep_exists(self) -> None:
        """.gitkeep must exist inside sources/ directory."""
        gitkeep = PROJECT_ROOT / "domains" / "gcse-english-tutor" / "sources" / ".gitkeep"
        assert gitkeep.is_file(), f"{gitkeep} does not exist"

    def test_sources_gitkeep_is_empty(self) -> None:
        """.gitkeep should be an empty marker file."""
        gitkeep = PROJECT_ROOT / "domains" / "gcse-english-tutor" / "sources" / ".gitkeep"
        assert gitkeep.stat().st_size == 0, ".gitkeep should be empty"


class TestSkeletonGoalMd:
    """AC-003: Skeleton GOAL.md exists with all 9 section headings."""

    EXPECTED_HEADINGS = [
        "## Goal",
        "## Source Documents",
        "## System Prompt",
        "## Generation Targets",
        "## Generation Guidelines",
        "## Evaluation Criteria",
        "## Output Schema",
        "## Metadata Schema",
        "## Layer Routing",
    ]

    @pytest.fixture(scope="class")
    def goal_md_path(self) -> Path:
        """Return the path to the GOAL.md file."""
        return PROJECT_ROOT / "domains" / "gcse-english-tutor" / "GOAL.md"

    @pytest.fixture(scope="class")
    def goal_md_content(self, goal_md_path: Path) -> str:
        """Read and return the content of GOAL.md."""
        assert goal_md_path.is_file(), f"{goal_md_path} does not exist"
        return goal_md_path.read_text(encoding="utf-8")

    def test_goal_md_exists(self, goal_md_path: Path) -> None:
        """GOAL.md must exist as a file."""
        assert goal_md_path.is_file(), f"{goal_md_path} does not exist"

    def test_goal_md_is_not_empty(self, goal_md_content: str) -> None:
        """GOAL.md must not be empty."""
        assert len(goal_md_content.strip()) > 0, "GOAL.md is empty"

    @pytest.mark.parametrize("heading", EXPECTED_HEADINGS)
    def test_section_heading_present(self, goal_md_content: str, heading: str) -> None:
        """Each of the 9 required section headings must be present."""
        # Check that the heading appears as a line on its own (possibly with whitespace)
        lines = [line.strip() for line in goal_md_content.splitlines()]
        assert heading in lines, (
            f"Missing section heading '{heading}' in GOAL.md. "
            f"Found headings: {[l for l in lines if l.startswith('## ')]}"
        )

    def test_exactly_nine_section_headings(self, goal_md_content: str) -> None:
        """GOAL.md must contain exactly 9 level-2 headings."""
        lines = [line.strip() for line in goal_md_content.splitlines()]
        h2_headings = [line for line in lines if line.startswith("## ")]
        assert len(h2_headings) == 9, (
            f"Expected 9 section headings, found {len(h2_headings)}: {h2_headings}"
        )

    def test_section_heading_order(self, goal_md_content: str) -> None:
        """Section headings must appear in the canonical order."""
        lines = [line.strip() for line in goal_md_content.splitlines()]
        h2_headings = [line for line in lines if line.startswith("## ")]
        assert h2_headings == self.EXPECTED_HEADINGS, (
            f"Headings not in expected order. "
            f"Expected: {self.EXPECTED_HEADINGS}, Got: {h2_headings}"
        )


class TestGitignorePdfExclusion:
    """AC-004: .gitignore entry excludes domains/*/sources/*.pdf."""

    @pytest.fixture(scope="class")
    def gitignore_content(self) -> str:
        """Read and return the content of .gitignore."""
        gitignore_path = PROJECT_ROOT / ".gitignore"
        assert gitignore_path.is_file(), f"{gitignore_path} does not exist"
        return gitignore_path.read_text(encoding="utf-8")

    def test_gitignore_exists(self) -> None:
        """.gitignore must exist."""
        gitignore_path = PROJECT_ROOT / ".gitignore"
        assert gitignore_path.is_file(), f"{gitignore_path} does not exist"

    def test_pdf_exclusion_pattern_present(self, gitignore_content: str) -> None:
        """domains/*/sources/*.pdf must be in .gitignore."""
        lines = [line.strip() for line in gitignore_content.splitlines()]
        assert "domains/*/sources/*.pdf" in lines, (
            "Missing .gitignore entry 'domains/*/sources/*.pdf'. "
            f"Found lines: {[l for l in lines if 'pdf' in l.lower() or 'domain' in l.lower()]}"
        )

    def test_pdf_exclusion_not_commented_out(self, gitignore_content: str) -> None:
        """The PDF exclusion pattern must not be commented out."""
        for line in gitignore_content.splitlines():
            stripped = line.strip()
            if "domains/*/sources/*.pdf" in stripped:
                assert not stripped.startswith("#"), (
                    "PDF exclusion pattern is commented out in .gitignore"
                )
                break

    def test_existing_gitignore_entries_preserved(self, gitignore_content: str) -> None:
        """Pre-existing .gitignore entries must not be removed."""
        expected_patterns = [
            "__pycache__/",
            "*.py[cod]",
            ".venv/",
            ".DS_Store",
            ".env",
            ".pytest_cache/",
            "output/",
        ]
        lines = [line.strip() for line in gitignore_content.splitlines()]
        for pattern in expected_patterns:
            assert pattern in lines, f"Pre-existing .gitignore entry '{pattern}' was removed"
