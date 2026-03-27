# Implementation Guide — Ninth Run Fixes (FEAT-TRF9)

## Execution Strategy

### Wave 1: P0 Blockers (parallel)

These two tasks are independent and can be executed in parallel.

**TASK-TRF-028**: Add range notation detection to `_coerce_valid_values`
- File: `domain_config/parser.py` (lines 86-94)
- Tests: `domain_config/tests/test_parse_goal_md.py`
- Mode: task-work (needs tests for range patterns)
- Impact: Unblocks `write_output` for `metadata.turns` validation

**TASK-TRF-029**: Add explicit `<think>` block instruction to Player prompt
- File: `domains/gcse-english-tutor/GOAL.md` (Generation Guidelines section)
- Mode: direct (prompt-only, no code changes)
- Impact: Ensures reasoning-type examples include `<think>` blocks

### Wave 2: Robustness (after Wave 1)

**TASK-TRF-030**: JSON string repair for literal newlines
- File: `entrypoint/generation_loop.py`
- Tests: `entrypoint/tests/test_generation_loop.py`
- Depends on: TASK-TRF-028 (validation must work first to verify full pipeline)
- Impact: Improves extraction success on earlier turns, reducing revision cycles

## Validation Run

After Wave 1:
1. Run single-target test: `python agent.py`
2. Verify:
   - `metadata.turns = 1` passes validation (TRF-028)
   - Player generates `<think>` blocks in assistant content (TRF-029)
   - Training example written to `output/train.jsonl`
3. If validation passes → proceed with Wave 2 then overnight run
