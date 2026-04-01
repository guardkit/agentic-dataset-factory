# Completion Report: TASK-LR1-004

## Task: Strengthen Player prompt for mandatory metadata

**Completed**: 2026-03-30
**Feature**: FEAT-LR1 (Long Run 1 Fixes)
**Wave**: 1

## Problem

In Long Run 1, `metadata_completeness` was the #1 revision criterion (77 issues). The Player frequently generated good pedagogical content but omitted the required `metadata` object.

## Changes Made

### 1. Added CRITICAL metadata warning to base prompt (`prompts/player_prompts.py`)

New `## CRITICAL -- Mandatory Metadata` section added to `PLAYER_BASE_PROMPT` between the Output and Output Format sections. States that metadata is required and omission causes automatic rejection.

### 2. Reordered domain context sections (`build_player_prompt`)

Moved Output Schema and Metadata Schema before Generation Guidelines so the Player sees the structural requirements before content generation instructions.

**Previous order**: Goal, System Prompt, Generation Guidelines, Output Schema, Metadata Schema, Layer Routing

**New order**: Goal, System Prompt, Output Schema, Metadata Schema, Generation Guidelines, Layer Routing, Metadata Checklist

### 3. Added metadata checklist at end of prompt

New `## Metadata Checklist (verify before returning)` section appended after Layer Routing with 5 verification items for the Player to check before submitting.

## Tests

6 new tests added to `prompts/tests/test_prompt_builders.py` in `TestPlayerMandatoryMetadataEmphasis`:
- `test_critical_metadata_section_in_base_prompt`
- `test_metadata_omission_causes_rejection`
- `test_metadata_must_keyword_present`
- `test_metadata_schema_before_generation_guidelines`
- `test_metadata_checklist_present`
- `test_metadata_checklist_after_layer_routing`

**All 101 tests pass** (95 existing + 6 new).

## Files Modified

| File | Change |
|------|--------|
| `prompts/player_prompts.py` | Added CRITICAL metadata section, reordered domain sections, added checklist |
| `prompts/tests/test_prompt_builders.py` | Added 6 tests for LR1-004 acceptance criteria |

## Acceptance Criteria Verification

- [x] Player prompt updated with mandatory metadata emphasis
- [x] Metadata schema description appears early in prompt (before Generation Guidelines)
- [x] No change to expected metadata fields or values
