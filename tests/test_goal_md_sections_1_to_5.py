"""Validate GOAL.md sections 1-5 for GCSE English tutor domain.

Tests acceptance criteria for TASK-GG-002:
- AC-001: Section 1 (Goal) references Socratic questioning, AQA specification, GCSE English
- AC-002: Section 2 (Source Documents) markdown table with File Pattern, Mode, Notes columns
- AC-003: Section 2 file patterns do not contain ".." or absolute paths
- AC-004: Section 3 (System Prompt) matches research doc verbatim; min 100 chars; refs AO1-AO6
- AC-005: Section 4 (Generation Targets) table with Category, Type, Count; total=1000; reasoning>=75%
- AC-006: Section 4 Type values are only "reasoning" or "direct"
- AC-007: Section 5 (Generation Guidelines) min 100 chars; refs Socratic questioning, mark scheme, think block
- AC-008: All modified files pass lint/format checks
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOAL_MD_PATH = PROJECT_ROOT / "domains" / "gcse-english-tutor" / "GOAL.md"
RESEARCH_DOC_PATH = PROJECT_ROOT / "docs" / "research" / "gcse-tutor-training-data-format.md"


@pytest.fixture(scope="module")
def goal_md_content() -> str:
    """Read GOAL.md content."""
    assert GOAL_MD_PATH.is_file(), f"{GOAL_MD_PATH} does not exist"
    return GOAL_MD_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sections(goal_md_content: str) -> dict[str, str]:
    """Parse GOAL.md into sections keyed by heading name."""
    result: dict[str, str] = {}
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in goal_md_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_heading is not None:
                result[current_heading] = "\n".join(current_lines)
            current_heading = stripped[3:].strip()
            current_lines = []
        elif current_heading is not None:
            current_lines.append(line)

    if current_heading is not None:
        result[current_heading] = "\n".join(current_lines)

    return result


@pytest.fixture(scope="module")
def research_doc_content() -> str:
    """Read the research specification document."""
    assert RESEARCH_DOC_PATH.is_file(), f"{RESEARCH_DOC_PATH} does not exist"
    return RESEARCH_DOC_PATH.read_text(encoding="utf-8")


class TestGoalSection:
    """AC-001: Section 1 (Goal) references Socratic questioning, AQA specification, and GCSE English."""

    def test_goal_section_exists(self, sections: dict[str, str]) -> None:
        """Goal section must exist in GOAL.md."""
        assert "Goal" in sections, "Missing 'Goal' section"

    def test_goal_references_socratic_questioning(self, sections: dict[str, str]) -> None:
        """Goal section must reference Socratic questioning."""
        goal = sections["Goal"].lower()
        assert "socratic" in goal, "Goal section does not reference Socratic questioning"

    def test_goal_references_aqa_specification(self, sections: dict[str, str]) -> None:
        """Goal section must reference AQA specification."""
        goal = sections["Goal"].lower()
        assert "aqa" in goal, "Goal section does not reference AQA specification"

    def test_goal_references_gcse_english(self, sections: dict[str, str]) -> None:
        """Goal section must reference GCSE English."""
        goal = sections["Goal"].lower()
        assert "gcse" in goal and "english" in goal, (
            "Goal section does not reference GCSE English"
        )

    def test_goal_minimum_length(self, sections: dict[str, str]) -> None:
        """Goal section must be at least 50 characters (per API contract)."""
        goal_text = sections["Goal"].strip()
        # Strip HTML comments
        lines = [
            line for line in goal_text.splitlines()
            if not line.strip().startswith("<!--")
            and not line.strip().endswith("-->")
        ]
        clean_goal = "\n".join(lines).strip()
        assert len(clean_goal) >= 50, (
            f"Goal section is only {len(clean_goal)} characters, minimum is 50"
        )


class TestSourceDocumentsSection:
    """AC-002/AC-003: Source Documents section with proper table and safe file patterns."""

    def test_source_documents_section_exists(self, sections: dict[str, str]) -> None:
        """Source Documents section must exist."""
        assert "Source Documents" in sections, "Missing 'Source Documents' section"

    def test_source_documents_has_table(self, sections: dict[str, str]) -> None:
        """Source Documents must contain a markdown table."""
        content = sections["Source Documents"]
        assert "|" in content, "Source Documents section does not contain a markdown table"

    def test_source_documents_table_columns(self, sections: dict[str, str]) -> None:
        """Table must have File Pattern, Mode, Notes columns."""
        content = sections["Source Documents"]
        header_line = None
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("|") and "File Pattern" in stripped:
                header_line = stripped
                break
        assert header_line is not None, (
            "Source Documents table missing 'File Pattern' column header"
        )
        assert "Mode" in header_line, "Source Documents table missing 'Mode' column header"
        assert "Notes" in header_line, "Source Documents table missing 'Notes' column header"

    def test_source_documents_has_data_rows(self, sections: dict[str, str]) -> None:
        """Table must have at least one data row."""
        content = sections["Source Documents"]
        table_lines = [
            line.strip() for line in content.splitlines()
            if line.strip().startswith("|") and "---" not in line
        ]
        # Subtract header row
        data_rows = [
            line for line in table_lines
            if "File Pattern" not in line
        ]
        assert len(data_rows) >= 1, "Source Documents table must have at least one data row"

    def test_source_documents_mode_values(self, sections: dict[str, str]) -> None:
        """Mode values must be 'standard' or 'vlm' only."""
        content = sections["Source Documents"]
        valid_modes = {"standard", "vlm"}
        table_lines = [
            line.strip() for line in content.splitlines()
            if line.strip().startswith("|")
            and "---" not in line
            and "File Pattern" not in line
        ]
        for line in table_lines:
            cells = [cell.strip() for cell in line.split("|") if cell.strip()]
            if len(cells) >= 2:
                mode = cells[1].strip()
                assert mode in valid_modes, (
                    f"Invalid mode '{mode}' in Source Documents table. "
                    f"Must be 'standard' or 'vlm'"
                )

    def test_file_patterns_no_path_traversal(self, sections: dict[str, str]) -> None:
        """AC-003: File patterns must not contain '..' (path traversal)."""
        content = sections["Source Documents"]
        table_lines = [
            line.strip() for line in content.splitlines()
            if line.strip().startswith("|")
            and "---" not in line
            and "File Pattern" not in line
        ]
        for line in table_lines:
            cells = [cell.strip() for cell in line.split("|") if cell.strip()]
            if cells:
                pattern = cells[0].strip()
                assert ".." not in pattern, (
                    f"File pattern '{pattern}' contains '..' path traversal"
                )

    def test_file_patterns_no_absolute_paths(self, sections: dict[str, str]) -> None:
        """AC-003: File patterns must not contain absolute paths."""
        content = sections["Source Documents"]
        table_lines = [
            line.strip() for line in content.splitlines()
            if line.strip().startswith("|")
            and "---" not in line
            and "File Pattern" not in line
        ]
        for line in table_lines:
            cells = [cell.strip() for cell in line.split("|") if cell.strip()]
            if cells:
                pattern = cells[0].strip()
                assert not pattern.startswith("/"), (
                    f"File pattern '{pattern}' is an absolute path"
                )


class TestSystemPromptSection:
    """AC-004: System Prompt matches research doc verbatim; min 100 chars; refs AO1-AO6."""

    def test_system_prompt_section_exists(self, sections: dict[str, str]) -> None:
        """System Prompt section must exist."""
        assert "System Prompt" in sections, "Missing 'System Prompt' section"

    def test_system_prompt_minimum_length(self, sections: dict[str, str]) -> None:
        """System Prompt must be at least 100 characters."""
        prompt = sections["System Prompt"].strip()
        # Strip any TODO comments
        lines = [
            line for line in prompt.splitlines()
            if not line.strip().startswith("<!--")
            and not line.strip().endswith("-->")
        ]
        clean_prompt = "\n".join(lines).strip()
        assert len(clean_prompt) >= 100, (
            f"System Prompt is only {len(clean_prompt)} characters, minimum is 100"
        )

    def test_system_prompt_references_ao1_through_ao6(self, sections: dict[str, str]) -> None:
        """System Prompt must reference assessment objectives AO1 through AO6."""
        prompt = sections["System Prompt"]
        # The prompt should reference AO1-AO6 range
        assert "AO1" in prompt, "System Prompt does not reference AO1"
        assert "AO6" in prompt, "System Prompt does not reference AO6"

    def test_system_prompt_matches_research_doc(
        self, sections: dict[str, str], research_doc_content: str
    ) -> None:
        """System Prompt must match the canonical system prompt from the research doc (lines 35-47)."""
        prompt_section = sections["System Prompt"].strip()
        # Strip HTML comments
        lines = [
            line for line in prompt_section.splitlines()
            if not line.strip().startswith("<!--")
            and not line.strip().endswith("-->")
        ]
        clean_prompt = "\n".join(lines).strip()

        # Extract the canonical system prompt from the research doc (lines 35-47, 1-indexed)
        research_lines = research_doc_content.splitlines()
        canonical_lines = research_lines[34:47]
        # Strip code fence markers (``` lines)
        canonical_lines = [
            line for line in canonical_lines
            if not line.strip().startswith("```")
        ]
        canonical_prompt = "\n".join(canonical_lines).strip()

        assert canonical_prompt in clean_prompt or clean_prompt == canonical_prompt, (
            "System Prompt does not match the canonical system prompt from "
            "docs/research/gcse-tutor-training-data-format.md lines 35-47"
        )

    def test_system_prompt_references_socratic(self, sections: dict[str, str]) -> None:
        """System Prompt must reference Socratic questioning."""
        prompt = sections["System Prompt"].lower()
        assert "socratic" in prompt, "System Prompt does not reference Socratic questioning"


class TestGenerationTargetsSection:
    """AC-005/AC-006: Generation Targets table with correct structure and values."""

    def test_generation_targets_section_exists(self, sections: dict[str, str]) -> None:
        """Generation Targets section must exist."""
        assert "Generation Targets" in sections, "Missing 'Generation Targets' section"

    def test_generation_targets_has_table(self, sections: dict[str, str]) -> None:
        """Generation Targets must contain a markdown table."""
        content = sections["Generation Targets"]
        assert "|" in content, "Generation Targets section does not contain a table"

    def test_generation_targets_table_columns(self, sections: dict[str, str]) -> None:
        """Table must have Category, Type, Count columns."""
        content = sections["Generation Targets"]
        header_line = None
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("|") and "Category" in stripped:
                header_line = stripped
                break
        assert header_line is not None, "Generation Targets table missing 'Category' header"
        assert "Type" in header_line, "Generation Targets table missing 'Type' header"
        assert "Count" in header_line, "Generation Targets table missing 'Count' header"

    def test_generation_targets_total_is_1000(self, sections: dict[str, str]) -> None:
        """Total count across all categories must equal exactly 1,000."""
        content = sections["Generation Targets"]
        table_lines = [
            line.strip() for line in content.splitlines()
            if line.strip().startswith("|")
            and "---" not in line
            and "Category" not in line
            and "Total" not in line
        ]
        total = 0
        for line in table_lines:
            cells = [cell.strip() for cell in line.split("|") if cell.strip()]
            if len(cells) >= 3:
                try:
                    count = int(cells[2])
                    total += count
                except ValueError:
                    continue
        assert total == 1000, (
            f"Generation Targets total is {total}, expected exactly 1000"
        )

    def test_generation_targets_reasoning_split_gte_75_percent(
        self, sections: dict[str, str]
    ) -> None:
        """Reasoning examples must be >= 75% of total."""
        content = sections["Generation Targets"]
        table_lines = [
            line.strip() for line in content.splitlines()
            if line.strip().startswith("|")
            and "---" not in line
            and "Category" not in line
            and "Total" not in line
        ]
        reasoning_count = 0
        total_count = 0
        for line in table_lines:
            cells = [cell.strip() for cell in line.split("|") if cell.strip()]
            if len(cells) >= 3:
                try:
                    count = int(cells[2])
                    total_count += count
                    if cells[1].strip() == "reasoning":
                        reasoning_count += count
                except ValueError:
                    continue
        if total_count > 0:
            ratio = reasoning_count / total_count
            assert ratio >= 0.75, (
                f"Reasoning split is {ratio:.1%}, expected >= 75%. "
                f"Reasoning: {reasoning_count}, Total: {total_count}"
            )

    def test_generation_targets_type_values_valid(self, sections: dict[str, str]) -> None:
        """AC-006: Type values must be only 'reasoning' or 'direct'."""
        content = sections["Generation Targets"]
        valid_types = {"reasoning", "direct"}
        table_lines = [
            line.strip() for line in content.splitlines()
            if line.strip().startswith("|")
            and "---" not in line
            and "Category" not in line
            and "Total" not in line
        ]
        for line in table_lines:
            cells = [cell.strip() for cell in line.split("|") if cell.strip()]
            if len(cells) >= 2:
                type_val = cells[1].strip()
                assert type_val in valid_types, (
                    f"Invalid type '{type_val}' in Generation Targets. "
                    f"Must be 'reasoning' or 'direct'"
                )

    def test_generation_targets_has_7_categories(self, sections: dict[str, str]) -> None:
        """Generation Targets must have 7 data categories (excluding total row)."""
        content = sections["Generation Targets"]
        table_lines = [
            line.strip() for line in content.splitlines()
            if line.strip().startswith("|")
            and "---" not in line
            and "Category" not in line
            and "Total" not in line
        ]
        data_rows = [
            line for line in table_lines
            if line.strip() and len([c for c in line.split("|") if c.strip()]) >= 3
        ]
        assert len(data_rows) == 7, (
            f"Expected 7 category rows, found {len(data_rows)}"
        )


class TestGenerationGuidelinesSection:
    """AC-007: Generation Guidelines min 100 chars; refs Socratic, mark scheme, think block."""

    def test_generation_guidelines_section_exists(self, sections: dict[str, str]) -> None:
        """Generation Guidelines section must exist."""
        assert "Generation Guidelines" in sections, "Missing 'Generation Guidelines' section"

    def test_generation_guidelines_minimum_length(self, sections: dict[str, str]) -> None:
        """Generation Guidelines must be at least 100 characters."""
        guidelines = sections["Generation Guidelines"].strip()
        # Strip any TODO comments
        lines = [
            line for line in guidelines.splitlines()
            if not line.strip().startswith("<!--")
            and not line.strip().endswith("-->")
        ]
        clean_guidelines = "\n".join(lines).strip()
        assert len(clean_guidelines) >= 100, (
            f"Generation Guidelines is only {len(clean_guidelines)} characters, minimum is 100"
        )

    def test_generation_guidelines_references_socratic(self, sections: dict[str, str]) -> None:
        """Generation Guidelines must reference Socratic questioning."""
        guidelines = sections["Generation Guidelines"].lower()
        assert "socratic" in guidelines, (
            "Generation Guidelines does not reference Socratic questioning"
        )

    def test_generation_guidelines_references_mark_scheme(
        self, sections: dict[str, str]
    ) -> None:
        """Generation Guidelines must reference mark scheme."""
        guidelines = sections["Generation Guidelines"].lower()
        assert "mark scheme" in guidelines, (
            "Generation Guidelines does not reference mark scheme"
        )

    def test_generation_guidelines_references_think_block(
        self, sections: dict[str, str]
    ) -> None:
        """Generation Guidelines must reference think block format."""
        guidelines = sections["Generation Guidelines"].lower()
        assert "think" in guidelines and "block" in guidelines, (
            "Generation Guidelines does not reference think block format"
        )
