---
id: TASK-DC-003
title: "Implement table parser and JSON extractor"
task_type: feature
parent_review: TASK-REV-DC5D
feature_id: FEAT-5606
wave: 2
implementation_mode: task-work
complexity: 5
dependencies:
  - TASK-DC-001
status: pending
priority: high
tags: [domain-config, parser, markdown-tables, json]
created: 2026-03-19T00:00:00Z
updated: 2026-03-19T00:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Implement table parser and JSON extractor

## Description

Implement two parsing utilities: (1) a markdown table parser that converts table sections into lists of Pydantic model instances, and (2) a JSON code block extractor for the Output Schema section.

## Module Location

```
domain_config/
├── parser.py        ← add parse_table() and extract_json() functions
```

## Functions

### parse_table

```python
def parse_table(section_body: str, model_class: type[BaseModel], column_map: dict[str, str]) -> list[BaseModel]:
    """Parse a markdown table into a list of Pydantic model instances.

    Args:
        section_body: Raw section text containing a markdown table.
        model_class: Pydantic model class to instantiate per row.
        column_map: Maps table column headers to model field names.

    Returns:
        List of validated model instances.
    """
```

### extract_json

```python
def extract_json(section_body: str) -> dict:
    """Extract and parse JSON from a markdown code block.

    Args:
        section_body: Raw section text containing a ```json code fence.

    Returns:
        Parsed JSON as a dict.

    Raises:
        GoalValidationError: If no JSON block found or JSON is invalid.
    """
```

## Tables to Parse

| Section | Model | Column Map |
|---------|-------|------------|
| Source Documents | `SourceDocument` | File Pattern → file_pattern, Mode → mode, Notes → notes |
| Generation Targets | `GenerationTarget` | Category → category, Type → type, Count → count |
| Evaluation Criteria | `EvaluationCriterion` | Criterion → name, Description → description, Weight → weight |
| Metadata Schema | `MetadataField` | Field → field, Type → type, Required → required, Valid Values → valid_values |
| Layer Routing | returns `dict[str, str]` | Layer → key, Destination → value |

## Acceptance Criteria

- [ ] `parse_table()` handles inconsistent column alignment and trailing whitespace
- [ ] `parse_table()` trims all cell values
- [ ] `parse_table()` handles missing trailing pipes in table rows
- [ ] `parse_table()` skips the separator row (`|---|---|`)
- [ ] `parse_table()` validates each row against the Pydantic model (type coercion for int, float)
- [ ] `extract_json()` finds the first ```` ```json ```` block and parses it
- [ ] `extract_json()` handles string values containing backticks within the JSON
- [ ] `extract_json()` raises `GoalValidationError` for malformed JSON with descriptive message
- [ ] `extract_json()` validates required top-level keys (`messages`, `metadata`)
- [ ] Weight values parsed as float (e.g., "25%" → 0.25)
- [ ] Required column parsed as bool (e.g., "yes" → True)
- [ ] Valid Values column parsed as `list[str]` (comma-separated), empty column → empty list
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- For table parsing, split rows on `|`, strip each cell
- Skip header row (index 0) and separator row (index 1), process data rows from index 2
- Weight percentage conversion: strip `%`, divide by 100
- For JSON extraction, use regex to find content between ```` ```json ```` and ```` ``` ````
- BDD scenarios: 36-40 (Source Documents), 50-56 (Generation Targets), 57-63 (Evaluation Criteria), 66-71 (Output Schema), 75-79 (Layer Routing), 237-241 (table formatting), 309-314 (nested code fences), 317-322 (empty Valid Values)
