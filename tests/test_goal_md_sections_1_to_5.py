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

from pathlib import Path

import pytest

from src.goal_parser import (
    GoalParseError,
    GoalSections,
    GenerationTarget,
    SourceDocument,
    load_goal_md,
    parse_generation_targets,
    parse_markdown_table,
    parse_sections,
    parse_source_documents,
    validate_file_patterns,
    validate_generation_targets,
    validate_section_content,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOAL_MD_PATH = PROJECT_ROOT / "domains" / "gcse-english-tutor" / "GOAL.md"
RESEARCH_DOC_PATH = PROJECT_ROOT / "docs" / "research" / "gcse-tutor-training-data-format.md"


@pytest.fixture(scope="module")
def goal_sections() -> GoalSections:
    """Load and parse GOAL.md into GoalSections."""
    return load_goal_md(GOAL_MD_PATH)


@pytest.fixture(scope="module")
def raw_sections(goal_sections: GoalSections) -> dict[str, str]:
    """Return raw parsed sections."""
    return goal_sections.raw_sections


@pytest.fixture(scope="module")
def research_doc_content() -> str:
    """Read the research specification document."""
    assert RESEARCH_DOC_PATH.is_file(), f"{RESEARCH_DOC_PATH} does not exist"
    return RESEARCH_DOC_PATH.read_text(encoding="utf-8")


class TestGoalSection:
    """AC-001: Section 1 (Goal) references Socratic questioning, AQA specification, and GCSE English."""

    def test_goal_section_exists(self, raw_sections: dict[str, str]) -> None:
        """Goal section must exist in GOAL.md."""
        assert "Goal" in raw_sections, "Missing 'Goal' section"

    def test_goal_references_socratic_questioning(
        self, goal_sections: GoalSections
    ) -> None:
        """Goal section must reference Socratic questioning."""
        goal = goal_sections.goal.lower()
        assert "socratic" in goal, "Goal section does not reference Socratic questioning"

    def test_goal_references_aqa_specification(
        self, goal_sections: GoalSections
    ) -> None:
        """Goal section must reference AQA specification."""
        goal = goal_sections.goal.lower()
        assert "aqa" in goal, "Goal section does not reference AQA specification"

    def test_goal_references_gcse_english(
        self, goal_sections: GoalSections
    ) -> None:
        """Goal section must reference GCSE English."""
        goal = goal_sections.goal.lower()
        assert "gcse" in goal and "english" in goal, (
            "Goal section does not reference GCSE English"
        )

    def test_goal_minimum_length(self, goal_sections: GoalSections) -> None:
        """Goal section must be at least 50 characters (per API contract)."""
        validate_section_content("Goal", goal_sections.goal, min_length=50)

    def test_goal_validate_required_terms(
        self, goal_sections: GoalSections
    ) -> None:
        """Goal section validates via validate_section_content with required terms."""
        validate_section_content(
            "Goal",
            goal_sections.goal,
            min_length=50,
            required_terms=["socratic", "aqa", "gcse"],
        )


class TestSourceDocumentsSection:
    """AC-002/AC-003: Source Documents section with proper table and safe file patterns."""

    def test_source_documents_section_exists(
        self, raw_sections: dict[str, str]
    ) -> None:
        """Source Documents section must exist."""
        assert "Source Documents" in raw_sections, "Missing 'Source Documents' section"

    def test_source_documents_has_table(
        self, raw_sections: dict[str, str]
    ) -> None:
        """Source Documents must contain a markdown table."""
        content = raw_sections["Source Documents"]
        assert "|" in content, "Source Documents section does not contain a markdown table"

    def test_source_documents_table_columns(
        self, raw_sections: dict[str, str]
    ) -> None:
        """Table must have File Pattern, Mode, Notes columns."""
        content = raw_sections["Source Documents"]
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

    def test_source_documents_parsed_entries(
        self, raw_sections: dict[str, str]
    ) -> None:
        """Table must parse into at least one SourceDocument entry."""
        documents = parse_source_documents(raw_sections["Source Documents"])
        assert len(documents) >= 1, "Source Documents table must have at least one entry"

    def test_source_documents_mode_values(
        self, raw_sections: dict[str, str]
    ) -> None:
        """Mode values must be 'standard' or 'vlm' only."""
        documents = parse_source_documents(raw_sections["Source Documents"])
        valid_modes = {"standard", "vlm"}
        for doc in documents:
            assert doc.mode in valid_modes, (
                f"Invalid mode '{doc.mode}' for pattern '{doc.file_pattern}'. "
                f"Must be 'standard' or 'vlm'"
            )

    def test_file_patterns_no_path_traversal(
        self, raw_sections: dict[str, str]
    ) -> None:
        """AC-003: File patterns must not contain '..' (path traversal)."""
        documents = parse_source_documents(raw_sections["Source Documents"])
        validate_file_patterns(documents)

    def test_file_patterns_no_absolute_paths(
        self, raw_sections: dict[str, str]
    ) -> None:
        """AC-003: File patterns must not contain absolute paths."""
        documents = parse_source_documents(raw_sections["Source Documents"])
        for doc in documents:
            assert not doc.file_pattern.startswith("/"), (
                f"File pattern '{doc.file_pattern}' is an absolute path"
            )

    def test_invalid_mode_raises_error(self) -> None:
        """Invalid mode value must raise GoalParseError."""
        bad_table = (
            "| File Pattern | Mode | Notes |\n"
            "|---|---|---|\n"
            "| test.pdf | enhanced | Bad mode |\n"
        )
        with pytest.raises(GoalParseError, match="Invalid mode"):
            parse_source_documents(bad_table)

    def test_path_traversal_raises_error(self) -> None:
        """Path traversal in file pattern must raise GoalParseError."""
        documents = [SourceDocument(file_pattern="../../secrets.pdf", mode="standard")]
        with pytest.raises(GoalParseError, match="path traversal"):
            validate_file_patterns(documents)

    def test_absolute_path_raises_error(self) -> None:
        """Absolute path in file pattern must raise GoalParseError."""
        documents = [SourceDocument(file_pattern="/etc/passwd", mode="standard")]
        with pytest.raises(GoalParseError, match="absolute path"):
            validate_file_patterns(documents)


class TestSystemPromptSection:
    """AC-004: System Prompt matches research doc verbatim; min 100 chars; refs AO1-AO6."""

    def test_system_prompt_section_exists(
        self, raw_sections: dict[str, str]
    ) -> None:
        """System Prompt section must exist."""
        assert "System Prompt" in raw_sections, "Missing 'System Prompt' section"

    def test_system_prompt_minimum_length(
        self, goal_sections: GoalSections
    ) -> None:
        """System Prompt must be at least 100 characters."""
        validate_section_content(
            "System Prompt", goal_sections.system_prompt, min_length=100
        )

    def test_system_prompt_references_ao1_through_ao6(
        self, goal_sections: GoalSections
    ) -> None:
        """System Prompt must reference assessment objectives AO1 through AO6."""
        prompt = goal_sections.system_prompt
        assert "AO1" in prompt, "System Prompt does not reference AO1"
        assert "AO6" in prompt, "System Prompt does not reference AO6"

    def test_system_prompt_matches_research_doc(
        self, goal_sections: GoalSections, research_doc_content: str
    ) -> None:
        """System Prompt must match the canonical prompt from the research doc (lines 35-47)."""
        clean_prompt = goal_sections.system_prompt

        # Extract canonical system prompt from research doc (lines 35-47, 1-indexed)
        research_lines = research_doc_content.splitlines()
        canonical_lines = research_lines[34:47]
        # Strip code fence markers
        canonical_lines = [
            line for line in canonical_lines
            if not line.strip().startswith("```")
        ]
        canonical_prompt = "\n".join(canonical_lines).strip()

        assert canonical_prompt in clean_prompt or clean_prompt == canonical_prompt, (
            "System Prompt does not match the canonical system prompt from "
            "docs/research/gcse-tutor-training-data-format.md lines 35-47"
        )

    def test_system_prompt_references_socratic(
        self, goal_sections: GoalSections
    ) -> None:
        """System Prompt must reference Socratic questioning."""
        prompt = goal_sections.system_prompt.lower()
        assert "socratic" in prompt, "System Prompt does not reference Socratic questioning"


class TestGenerationTargetsSection:
    """AC-005/AC-006: Generation Targets table with correct structure and values."""

    def test_generation_targets_section_exists(
        self, raw_sections: dict[str, str]
    ) -> None:
        """Generation Targets section must exist."""
        assert "Generation Targets" in raw_sections, "Missing 'Generation Targets' section"

    def test_generation_targets_has_table(
        self, raw_sections: dict[str, str]
    ) -> None:
        """Generation Targets must contain a markdown table."""
        content = raw_sections["Generation Targets"]
        assert "|" in content, "Generation Targets section does not contain a table"

    def test_generation_targets_table_columns(
        self, raw_sections: dict[str, str]
    ) -> None:
        """Table must have Category, Type, Count columns."""
        content = raw_sections["Generation Targets"]
        header_line = None
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("|") and "Category" in stripped:
                header_line = stripped
                break
        assert header_line is not None, "Generation Targets table missing 'Category' header"
        assert "Type" in header_line, "Generation Targets table missing 'Type' header"
        assert "Count" in header_line, "Generation Targets table missing 'Count' header"

    def test_generation_targets_parsed(
        self, raw_sections: dict[str, str]
    ) -> None:
        """Generation Targets must parse into exactly 18 entries."""
        targets = parse_generation_targets(raw_sections["Generation Targets"])
        assert len(targets) == 18, f"Expected 18 category rows, found {len(targets)}"

    def test_generation_targets_total_is_2500(
        self, raw_sections: dict[str, str]
    ) -> None:
        """Total count across all categories must equal exactly 2,500."""
        targets = parse_generation_targets(raw_sections["Generation Targets"])
        validate_generation_targets(targets, expected_total=2500)

    def test_generation_targets_reasoning_split_gte_70_percent(
        self, raw_sections: dict[str, str]
    ) -> None:
        """Reasoning examples must be >= 70% of total."""
        targets = parse_generation_targets(raw_sections["Generation Targets"])
        validate_generation_targets(
            targets, expected_total=2500, min_reasoning_ratio=0.70
        )

    def test_generation_targets_type_values_valid(
        self, raw_sections: dict[str, str]
    ) -> None:
        """AC-006: Type values must be only 'reasoning' or 'direct'."""
        targets = parse_generation_targets(raw_sections["Generation Targets"])
        valid_types = {"reasoning", "direct"}
        for target in targets:
            assert target.type in valid_types, (
                f"Invalid type '{target.type}' for '{target.category}'. "
                f"Must be 'reasoning' or 'direct'"
            )

    def test_invalid_type_raises_error(self) -> None:
        """Invalid type value must raise GoalParseError."""
        bad_table = (
            "| Category | Type | Count |\n"
            "|---|---|---|\n"
            "| Test | hybrid | 100 |\n"
        )
        with pytest.raises(GoalParseError, match="Invalid type"):
            parse_generation_targets(bad_table)

    def test_wrong_total_raises_error(self) -> None:
        """Total not matching expected must raise GoalParseError."""
        targets = [
            GenerationTarget(category="Test", type="reasoning", count=500),
        ]
        with pytest.raises(GoalParseError, match="Total count"):
            validate_generation_targets(targets, expected_total=1000)

    def test_low_reasoning_ratio_raises_error(self) -> None:
        """Reasoning ratio below minimum must raise GoalParseError."""
        targets = [
            GenerationTarget(category="A", type="reasoning", count=600),
            GenerationTarget(category="B", type="direct", count=400),
        ]
        with pytest.raises(GoalParseError, match="Reasoning ratio"):
            validate_generation_targets(
                targets, expected_total=1000, min_reasoning_ratio=0.75
            )


class TestGenerationGuidelinesSection:
    """AC-007: Generation Guidelines min 100 chars; refs Socratic, mark scheme, think block."""

    def test_generation_guidelines_section_exists(
        self, raw_sections: dict[str, str]
    ) -> None:
        """Generation Guidelines section must exist."""
        assert "Generation Guidelines" in raw_sections, (
            "Missing 'Generation Guidelines' section"
        )

    def test_generation_guidelines_minimum_length(
        self, goal_sections: GoalSections
    ) -> None:
        """Generation Guidelines must be at least 100 characters."""
        validate_section_content(
            "Generation Guidelines",
            goal_sections.generation_guidelines,
            min_length=100,
        )

    def test_generation_guidelines_references_socratic(
        self, goal_sections: GoalSections
    ) -> None:
        """Generation Guidelines must reference Socratic questioning."""
        guidelines = goal_sections.generation_guidelines.lower()
        assert "socratic" in guidelines, (
            "Generation Guidelines does not reference Socratic questioning"
        )

    def test_generation_guidelines_references_mark_scheme(
        self, goal_sections: GoalSections
    ) -> None:
        """Generation Guidelines must reference mark scheme."""
        guidelines = goal_sections.generation_guidelines.lower()
        assert "mark scheme" in guidelines, (
            "Generation Guidelines does not reference mark scheme"
        )

    def test_generation_guidelines_references_think_block(
        self, goal_sections: GoalSections
    ) -> None:
        """Generation Guidelines must reference think block format."""
        guidelines = goal_sections.generation_guidelines.lower()
        assert "think" in guidelines and "block" in guidelines, (
            "Generation Guidelines does not reference think block format"
        )

    def test_generation_guidelines_validate_with_required_terms(
        self, goal_sections: GoalSections
    ) -> None:
        """Generation Guidelines validates via validate_section_content."""
        validate_section_content(
            "Generation Guidelines",
            goal_sections.generation_guidelines,
            min_length=100,
            required_terms=["socratic", "mark scheme"],
        )


class TestGoalParserEdgeCases:
    """Tests for goal_parser module edge cases and error paths."""

    def test_parse_sections_no_headings_raises(self) -> None:
        """Content with no level-2 headings raises GoalParseError."""
        with pytest.raises(GoalParseError, match="No level-2 headings"):
            parse_sections("Just plain text without headings")

    def test_load_goal_md_missing_file_raises(self, tmp_path: Path) -> None:
        """Loading a non-existent GOAL.md raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="GOAL.md not found"):
            load_goal_md(tmp_path / "nonexistent" / "GOAL.md")

    def test_parse_markdown_table_empty(self) -> None:
        """Parsing content with no table returns empty list."""
        result = parse_markdown_table("No table here")
        assert result == []

    def test_parse_markdown_table_with_data(self) -> None:
        """Parsing a valid markdown table returns data rows."""
        table = (
            "| A | B |\n"
            "|---|---|\n"
            "| 1 | 2 |\n"
            "| 3 | 4 |\n"
        )
        result = parse_markdown_table(table)
        assert len(result) == 2
        assert result[0] == ["1", "2"]
        assert result[1] == ["3", "4"]

    def test_validate_section_content_too_short(self) -> None:
        """Content below minimum length raises GoalParseError."""
        with pytest.raises(GoalParseError, match="only 5 characters"):
            validate_section_content("Test", "short", min_length=100)

    def test_validate_section_content_missing_term(self) -> None:
        """Missing required term raises GoalParseError."""
        content = "This is a long enough section that has plenty of characters to pass the minimum length check."
        with pytest.raises(GoalParseError, match="Required term"):
            validate_section_content(
                "Test", content, min_length=10, required_terms=["nonexistent"]
            )

    def test_goal_sections_strip_comments(self) -> None:
        """GoalSections._strip_comments removes HTML comments."""
        text = "<!-- comment -->\nActual content\n<!-- another -->"
        result = GoalSections._strip_comments(text)
        assert result == "Actual content"
        assert "<!--" not in result

    def test_source_document_dataclass(self) -> None:
        """SourceDocument dataclass stores fields correctly."""
        doc = SourceDocument(file_pattern="*.pdf", mode="standard", notes="Test")
        assert doc.file_pattern == "*.pdf"
        assert doc.mode == "standard"
        assert doc.notes == "Test"

    def test_generation_target_dataclass(self) -> None:
        """GenerationTarget dataclass stores fields correctly."""
        target = GenerationTarget(category="Test", type="reasoning", count=100)
        assert target.category == "Test"
        assert target.type == "reasoning"
        assert target.count == 100

    def test_goal_parse_error_message(self) -> None:
        """GoalParseError includes section name in message."""
        err = GoalParseError("Goal", "something went wrong")
        assert "Goal" in str(err)
        assert "something went wrong" in str(err)
        assert err.section == "Goal"
