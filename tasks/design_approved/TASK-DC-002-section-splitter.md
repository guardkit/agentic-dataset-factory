---
id: TASK-DC-002
title: Implement markdown section splitter
task_type: feature
parent_review: TASK-REV-DC5D
feature_id: FEAT-5606
wave: 2
implementation_mode: task-work
complexity: 4
dependencies:
- TASK-DC-001
status: in_review
priority: high
tags:
- domain-config
- parser
- markdown
created: 2026-03-19 00:00:00+00:00
updated: 2026-03-19 00:00:00+00:00
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 2
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-5606
  base_branch: main
  started_at: '2026-03-20T14:49:10.986999'
  last_updated: '2026-03-20T15:01:27.127423'
  turns:
  - turn: 1
    decision: feedback
    feedback: "- Not all acceptance criteria met:\n  \u2022 File-not-found case raises\
      \ `GoalValidationError` with descriptive message"
    timestamp: '2026-03-20T14:49:10.986999'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
  - turn: 2
    decision: approve
    feedback: null
    timestamp: '2026-03-20T14:56:58.537920'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: Implement markdown section splitter

## Description

Implement a section splitter that parses a GOAL.md file into its 9 named sections. The splitter uses a whitelist approach — only splitting on the 9 known section headings — to handle the edge case where section content contains embedded `##` headings.

## Required Sections (Whitelist)

1. Goal
2. Source Documents
3. System Prompt
4. Generation Targets
5. Generation Guidelines
6. Evaluation Criteria
7. Output Schema
8. Metadata Schema
9. Layer Routing

## Module Location

```
domain_config/
├── parser.py        ← split_sections() function
```

## Function Signature

```python
def split_sections(content: str) -> dict[str, str]:
    """Split GOAL.md content into named sections.

    Args:
        content: Raw markdown text of the GOAL.md file.

    Returns:
        Dict mapping section name → section body text (stripped).

    Raises:
        GoalValidationError: If any required section is missing.
    """
```

## Acceptance Criteria

- [ ] Splits on `## {section_name}` headings only for the 9 known sections
- [ ] Returns dict mapping section name to body text
- [ ] Strips leading/trailing whitespace from section bodies
- [ ] Handles inconsistent whitespace around headings (extra blank lines, trailing spaces)
- [ ] Embedded `##` headings within section content are preserved as content, not treated as boundaries
- [ ] Raises `GoalValidationError` identifying each missing section when any required section is absent
- [ ] Reports ALL missing sections at once (not just the first)
- [ ] Empty GOAL.md raises error indicating no sections found
- [ ] File-not-found case raises `GoalValidationError` with descriptive message
- [ ] Unicode content preserved exactly
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Seam Tests

The following seam test validates the integration contract with consumer tasks. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify split_sections output contract."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("SECTION_DICT")
def test_section_dict_keys():
    """Verify split_sections returns all 9 required section keys.

    Contract: dict[str, str] with exactly these 9 keys
    Producer: TASK-DC-002
    """
    from domain_config.parser import split_sections

    # Minimal valid GOAL.md with all 9 sections
    content = "\n".join(
        f"## {name}\n{'x' * 100}"
        for name in [
            "Goal", "Source Documents", "System Prompt",
            "Generation Targets", "Generation Guidelines",
            "Evaluation Criteria", "Output Schema",
            "Metadata Schema", "Layer Routing",
        ]
    )
    result = split_sections(content)
    assert isinstance(result, dict)
    assert len(result) == 9
    assert "Goal" in result
    assert "Layer Routing" in result
```

## Implementation Notes

- Use a regex like `^## (Goal|Source Documents|System Prompt|...)$` with `re.MULTILINE`
- Consider `re.split()` or `re.finditer()` to locate heading positions
- For the "report all missing sections" requirement, collect missing names into a list and raise a single error
- BDD scenarios to cover: lines 21-25 (valid parse), 146-162 (missing sections), 220-224 (empty file), 229-234 (whitespace variations), 272-277 (embedded headings)
