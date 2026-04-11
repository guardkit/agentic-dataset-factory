# Implementation Guide — dataset-key-whitespace-fix

## Source

Generated from [/task-review TASK-REV-4AA0 → I]mplement](../TASK-REV-4AA0-fix-dataset-key-whitespace-bug.md). Full review report with empirical evidence: [.claude/reviews/TASK-REV-4AA0-review-report.md](../../../.claude/reviews/TASK-REV-4AA0-review-report.md).

## Problem (1-line)

The Player LLM occasionally emits `{" role": "user", ...}` (leading-space key) in multi-turn JSON, and nothing in the pipeline validates message-dict key shape, so 2/1716 records in `output_backup_run1/train.jsonl` landed on disk malformed.

## Fix (1-line)

Add a deterministic structural-validation gate in `write_output` that enforces `set(msg.keys()) == {"role", "content"}` and `msg["role"] in {"system","user","assistant"}` for every message.

## Confidence

**HIGH.** Fix simulated against 1,716 real backup records: **0 false positives**, catches the 2 known-bad records. Expected throughput impact: +2 Player revisions across ~3,432 turns (0.06 %).

## Execution Strategy

### Wave 1 (parallel, 2 tasks)

Both tasks are small, scoped to different files, and have no overlap. DKW-002 depends on DKW-001 landing first — run them sequentially within a single agent, or serialise within a single worktree.

| Task | File | Mode | Workspace | Depends on |
|---|---|---|---|---|
| [TASK-DKW-001](TASK-DKW-001-add-message-structure-gate.md) | [src/tools/write_output.py](../../../src/tools/write_output.py) | task-work | `dataset-key-whitespace-fix-wave1-1` | — |
| [TASK-DKW-002](TASK-DKW-002-regression-tests.md) | [src/tools/tests/test_write_output.py](../../../src/tools/tests/test_write_output.py) | direct | `dataset-key-whitespace-fix-wave1-2` | TASK-DKW-001 |

Because the dependency is strict (tests need the gate in place), recommended flow is **serial within one worktree**:

```bash
/task-work TASK-DKW-001
# verify: pytest src/tools/tests/test_write_output.py -v  (existing suite still passes)
/task-work TASK-DKW-002
# verify: pytest src/tools/tests/test_write_output.py -v  (new 9 tests pass + existing)
```

If you prefer conductor parallel execution anyway, TASK-DKW-002 can be stubbed first (RED tests) and TASK-DKW-001 then makes them pass (GREEN) — TDD style. The total file change surface is small enough that parallelisation isn't necessary.

## Out of Scope

Explicitly excluded from this wave:

1. **Player/Coach prompt changes** — review §R3 argues against (F5, F6).
2. **Delegating to `TrainingExample.model_validate`** — review §R4 defers as optional follow-up TASK-DKW-003.
3. **Historical `output/train.jsonl` rewrite** — training-script workaround already handles the 2 legacy records.
4. **Value-side whitespace stripping** (e.g. `"role": " user"`) — speculative hardening; 0 occurrences in backup.
5. **Configurable allowed-key set for future domains** — YAGNI until a second domain needs extra keys.

## Validation Checklist

After both tasks land:

- [ ] `pytest src/tools/tests/test_write_output.py -v` — all existing tests pass + 9 new step-2b tests pass
- [ ] `pytest tests/ -v` — full suite regression check
- [ ] `ruff check src/tools/write_output.py src/tools/tests/test_write_output.py`
- [ ] Re-run simulation script against `output_backup_run1/train.jsonl` → confirm 2 rejects at lines 1145 and 1330
- [ ] Spot-check: a minimal 3-message single-turn example still writes successfully

## Expected Diff Surface

Roughly:

- `src/tools/write_output.py`: +~25 lines (constants + gate), -2 lines (step 3 simplification)
- `src/tools/tests/test_write_output.py`: +~100 lines (9 tests)

No changes outside these two files.
