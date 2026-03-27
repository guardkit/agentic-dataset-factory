# Implementation Guide — Eighth Run Fixes (FEAT-TRF8)

## Execution Strategy

### Wave 1: P0 Blockers (parallel)

These two tasks are independent and can be executed in parallel.

**TASK-TRF-024**: Remove `--reasoning-parser qwen3` from vLLM launch script
- File: `guardkit/scripts/vllm-agentic-factory.sh`
- Mode: direct (1-line removal + banner update)
- Requires: vLLM container restart after change

**TASK-TRF-025**: JSON-string-aware brace matching
- File: `entrypoint/generation_loop.py` (lines 144-161)
- Mode: task-work (needs tests)
- Requires: 4+ new test cases in `entrypoint/tests/test_generation_loop.py`

### Wave 2: Defence-in-depth (after Wave 1)

**TASK-TRF-026**: Add `reasoning_content` fallback to `_extract_player_content`
- Depends on: TASK-TRF-024 (to validate the approach works first)
- File: `entrypoint/generation_loop.py` (lines 169-217)
- Mode: task-work (needs tests)

**TASK-TRF-027**: Coach think block verification
- Depends on: TASK-TRF-024 (think blocks must be visible first)
- File: `AGENTS.md` or domain GOAL.md
- Mode: direct (prompt-only change)

## Validation Run

After Wave 1 is complete:
1. Restart vLLM with updated script (no `--reasoning-parser`)
2. Run single-target test: `python agent.py`
3. Verify:
   - Player `content` contains `<think>` blocks
   - JSON extraction succeeds
   - `write_output` validation passes
   - Training example written to `output/train.jsonl`

If validation passes → proceed with Wave 2 and then overnight run.
