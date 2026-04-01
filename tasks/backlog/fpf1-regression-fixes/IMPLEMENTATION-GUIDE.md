# Implementation Guide: FPF1 Regression Fixes

## Execution Strategy

### Wave 1 (Parallel — no file conflicts)

| Task | Files | Est. Complexity |
|------|-------|-----------------|
| TASK-FPF1-001 | `prompts/player_prompts.py`, `prompts/tests/test_prompt_builders.py` | Low (2) |
| TASK-FPF1-002 | `entrypoint/generation_loop.py` (lines 705-726) | Low-Med (3) |

These two tasks touch completely different files and can execute in parallel.

### Wave 2 (Sequential — depends on Wave 1)

| Task | Files | Est. Complexity |
|------|-------|-----------------|
| TASK-FPF1-003 | `entrypoint/generation_loop.py` (lines 657-957) | Medium (4) |

Depends on TASK-FPF1-002 being complete (uses the hardened format gate).

## Verification Plan

After all three tasks complete:

1. **Unit tests**: `pytest tests/ prompts/tests/ synthesis/tests/ -v`
2. **Smoke test**: Run pipeline on 5 targets to verify basic flow
3. **Regression test**: Run pipeline on full 77-target set
4. **Compare metrics**: Acceptance rate should be >= 90.9% (baseline)

## Expected Outcomes

| Metric | Current | After Wave 1 | After Wave 2 |
|--------|---------|-------------|-------------|
| Acceptance rate | 68.8% | ~91-94% | ~94-96% |
| Format gate blocks | 68 | ~44 (baseline level) | ~44 |
| Write validation fails | 22 | ~0 | ~0 |
| Post-gen validation fails | 14 | ~4 (baseline level) | ~4 |

## Rollback Plan

If Wave 1 doesn't restore acceptance rate to >= 88%:
- Check that prompt revert was complete (diff against baseline commit)
- Check vLLM server hasn't changed between runs
- Consider temperature sensitivity (try 0.5 instead of 0.6)
