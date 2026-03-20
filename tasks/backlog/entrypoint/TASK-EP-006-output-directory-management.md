---
id: TASK-EP-006
title: "Output directory management (clean/resume)"
task_type: feature
parent_review: TASK-REV-9EDC
feature_id: FEAT-2CF1
wave: 2
implementation_mode: direct
complexity: 2
dependencies:
  - TASK-EP-005
status: pending
---

# Task: Output Directory Management

## Description

Implement output directory lifecycle management: create the directory structure, clean on fresh start (ADR-ARCH-008), and preserve on resume (ADR-ARCH-010).

## Requirements

- Create `output/` and `output/rag_index/` directories if they don't exist
- On fresh start (`--fresh`, default): remove all files in output directory except `.lock`
- On resume (`--resume`): skip cleaning, preserve existing `train.jsonl`, `rejected.jsonl`, `knowledge.jsonl`
- Ensure `train.jsonl`, `rejected.jsonl`, and `knowledge.jsonl` are opened in append mode for the generation loop

## Acceptance Criteria

- [ ] Output directory structure created on startup
- [ ] Fresh start removes previous output files (BDD: "Fresh start cleans the output directory")
- [ ] Resume preserves existing output files
- [ ] Files opened in append mode for generation loop compatibility

## Reference

- ADR-ARCH-008: Start fresh on re-run
- ADR-ARCH-010: Checkpoint/resume
- API contract: `docs/design/contracts/API-output.md`

## Implementation Notes

Place in `entrypoint/output.py`. Integrate with checkpoint logic from TASK-EP-005.
