---
id: TASK-FRF-002
title: Fix write_output metadata validation for array fields
status: completed
created: 2026-03-25T00:00:00Z
updated: 2026-03-25T00:00:00Z
completed: 2026-03-25T00:00:00Z
completed_location: tasks/completed/TASK-FRF-002/
priority: critical
tags: [bug-fix, validation, write-output, p0]
complexity: 3
parent_review: TASK-REV-E2A7
feature_id: FEAT-FRF
wave: 1
implementation_mode: task-work
dependencies: []
test_results:
  status: pass
  coverage: null
  last_run: 2026-03-25
---

# Task: Fix write_output Metadata Validation for Array Fields

## Description

The `write_output` tool's Step 9 validation at `src/tools/write_output.py:149-158` treats all metadata fields as scalar strings. When a field like `ao` has type `array[string]` in GOAL.md, the model correctly produces `"ao": ["AO2", "AO3"]` (a list), but the validator checks `["AO2", "AO3"] not in ["AO1", ...]` — which is a list-in-list membership test that always returns `True`, causing every example to be rejected.

## Root Cause

See review report: `.claude/reviews/TASK-REV-E2A7-review-report.md` — Finding 2.

The `schema_lookup` dict at lines 66-69 only stores `field` and `valid_values` — the `type` field from `MetadataField` (e.g., `"array[string]"`) is discarded. Without type awareness, the validator cannot distinguish array fields from scalar fields.

### Secondary Issue

`_coerce_valid_values` in `domain_config/parser.py:86-94` splits on comma, producing `"AO6 (can be empty)"` as a valid value when GOAL.md has `AO1, AO2, AO3, AO4, AO5, AO6 (can be empty)`. The parenthetical note should either be stripped by the parser or removed from GOAL.md.

## Changes Required

1. **`src/tools/write_output.py`**: Update `schema_lookup` to also store the field type. In Step 9 validation, check if the field type starts with `array` — if so, validate each element of the list individually rather than the whole list.

   ```python
   # In closure setup (lines 64-69):
   schema_lookup: dict[str, tuple[list[str], str]] = {}
   for field_def in metadata_schema:
       if field_def.valid_values:
           schema_lookup[field_def.field] = (field_def.valid_values, field_def.type)

   # In Step 9 (lines 149-158):
   for field_name, (valid_values, field_type) in schema_lookup.items():
       if field_name in ("layer", "type"):
           continue
       field_value = metadata.get(field_name)
       if field_value is None:
           continue
       if isinstance(field_value, list):
           invalid = [v for v in field_value if v not in valid_values]
           if invalid:
               return (
                   f"Error: metadata.{field_name} contains invalid values: {invalid}"
               )
       else:
           if field_value not in valid_values:
               return (
                   f"Error: metadata.{field_name} value '{field_value}' "
                   f"not in valid values"
               )
   ```

2. **`domains/gcse-english-tutor/GOAL.md`**: Remove `(can be empty)` parenthetical from the `ao` valid values cell, changing to: `AO1, AO2, AO3, AO4, AO5, AO6`

3. **Tests**: Add test cases for array field validation (both valid and invalid array elements).

## Acceptance Criteria

- [ ] Step 9 validates array fields element-by-element
- [ ] Step 9 still validates scalar fields as before (no regression)
- [ ] `"ao": ["AO2", "AO3"]` passes validation when AO2 and AO3 are in valid_values
- [ ] `"ao": ["AO2", "INVALID"]` returns descriptive error naming the invalid element
- [ ] `"ao": []` passes validation (empty array is valid per GOAL.md)
- [ ] GOAL.md `ao` valid values cleaned up (no parenthetical)
- [ ] Existing unit tests pass
- [ ] New tests for array field validation added

## Files to Modify

- `src/tools/write_output.py` (primary — ~15 lines)
- `domains/gcse-english-tutor/GOAL.md` (minor — clean up parenthetical)
- Tests for write_output tool

## Expected Interface

After fix, the `write_output` tool should accept examples where `metadata.ao` is any subset of `["AO1", "AO2", "AO3", "AO4", "AO5", "AO6"]`, including the empty list `[]`.
