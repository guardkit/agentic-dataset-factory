---
id: TASK-EP-006
title: Output directory management (clean/resume)
task_type: feature
parent_review: TASK-REV-9EDC
feature_id: FEAT-2CF1
wave: 2
implementation_mode: direct
complexity: 2
dependencies:
- TASK-EP-005
status: in_review
autobuild_state:
  current_turn: 1
  max_turns: 35
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/.guardkit/worktrees/FEAT-6D0B
  base_branch: main
  started_at: '2026-03-20T23:52:58.927329'
  last_updated: '2026-03-21T00:01:38.246387'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-03-20T23:52:58.927329'
    player_summary: Enhanced prepare_output_directory() in checkpoint.py to preserve
      .lock on fresh start (previously used shutil.rmtree which removed everything
      including .lock). Extracted _clean_output_directory() helper that iterates over
      output dir children and skips .lock. Created new entrypoint/output.py with OutputFileManager
      context manager that opens train.jsonl, rejected.jsonl, and rag_index/knowledge.jsonl
      in append mode ('a') with UTF-8 encoding. OutputFileManager supports both explicit
      open/close and c
    player_success: true
    coach_success: true
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
