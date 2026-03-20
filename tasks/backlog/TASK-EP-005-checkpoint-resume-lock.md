---
id: TASK-EP-005
title: "Checkpoint/resume logic and lock file concurrency guard"
task_type: feature
parent_review: TASK-REV-9EDC
feature_id: FEAT-2CF1
wave: 2
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-EP-002
status: pending
---

# Task: Checkpoint/Resume Logic and Lock File Concurrency Guard

## Description

Implement the checkpoint/resume mechanism from ADR-ARCH-010 and the lock file concurrency guard from ASSUM-002. This covers:
- Writing `output/.checkpoint` after each completed target (atomic write)
- Reading checkpoint on `--resume` to continue from last completed target
- Lock file (`output/.lock`) to prevent concurrent entrypoint processes
- Output directory clean on fresh start (ADR-ARCH-008)

## Requirements

### Checkpoint
- Write `output/.checkpoint` containing last completed target index after each target
- Atomic write: write to temp file then `os.rename()` to prevent corruption on kill
- `--resume` flag: read checkpoint, skip output directory clean, continue from saved index
- Error if `--resume` but no `.checkpoint` file exists
- Default behaviour: `--fresh` (clean output directory per ADR-ARCH-008)

### Lock File
- Acquire `output/.lock` via `fcntl.flock()` at startup
- Fail with clear error if lock already held by another process (ASSUM-002)
- Release lock on exit (use context manager or atexit)

### Output Directory
- On fresh start: clean output directory before generation
- On resume: preserve existing output files
- Create output directory structure if not exists: `output/`, `output/rag_index/`

## Acceptance Criteria

- [ ] Checkpoint written atomically after each target completion
- [ ] `--resume` reads checkpoint and continues from saved index (BDD: "Resuming from a checkpoint")
- [ ] Error raised if `--resume` without checkpoint file (BDD: "Resume requested but no checkpoint file")
- [ ] Fresh start cleans output directory (BDD: "Fresh start cleans the output directory")
- [ ] Lock file prevents concurrent processes (BDD: "Concurrent entrypoint processes")
- [ ] Checkpoint file survives process interruption (BDD: "Checkpoint file is written atomically")
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Reference

- ADR-ARCH-008: Start fresh on re-run
- ADR-ARCH-010: Overnight run resilience (checkpoint/resume)
- ASSUM-002: Lock file for concurrency detection
- BDD scenarios: `features/entrypoint/entrypoint.feature` (edge cases group)

## Implementation Notes

Place in `entrypoint/checkpoint.py` and `entrypoint/lockfile.py`.
