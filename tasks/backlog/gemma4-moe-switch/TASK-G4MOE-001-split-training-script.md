---
id: TASK-G4MOE-001
title: Split train_gemma4.py into dense + moe sibling scripts
status: completed
created: 2026-04-15T00:00:00Z
updated: 2026-04-15T00:00:00Z
priority: high
tags: [fine-tuning, gemma4, refactor, preserve-sunk-cost]
complexity: 1
parent_review: TASK-REV-G4MOE
feature_id: FEAT-G4MOE
wave: 1
implementation_mode: direct
dependencies: []
---

# Task: Split train_gemma4.py into dense + moe sibling scripts

## Description

The existing [docs/research/train_gemma4.py](../../../docs/research/train_gemma4.py) is hardcoded for `unsloth/gemma-4-31B-it` Dense + QLoRA 4-bit. Review TASK-REV-G4MOE recommends switching the primary fine-tune to the 26B A4B MoE variant but **preserving** the Dense script and artifacts as an offline quality tier. To keep both tiers reproducible without forking-at-runtime, split the current single script into two siblings:

- `train_gemma4_dense.py` — exact copy of the current file, unchanged content
- `train_gemma4_moe.py` — created in TASK-G4MOE-002 (this task only creates the dense-named file and deletes the old one)

This is a pure rename task with no logic changes. Contents of `train_gemma4_dense.py` must be byte-identical to the pre-rename `train_gemma4.py` (modulo optional top-of-file docstring edit noting the Dense tier).

## Scope

- [ ] `git mv docs/research/train_gemma4.py docs/research/train_gemma4_dense.py`
- [ ] (optional) Update the top-of-file docstring in `train_gemma4_dense.py` to note: "Dense 31B variant. For the primary MoE 26B A4B fine-tune, see `train_gemma4_moe.py`."
- [ ] Grep the repo for references to `train_gemma4.py` and update any that are not inside `.claude/reviews/` historical reports or archived task files:
  - [ ] `docs/research/fine-tuning-getting-started.md` references (TASK-G4MOE-003 will rewrite the rationale section, but keep paths consistent in the meantime)
  - [ ] `tasks/backlog/TASK-REV-G4MOE-review-gemma4-moe-vs-dense-choice.md` (OK to leave; historical reference)
  - [ ] Any `CLAUDE.md` or agent docs that cite the script path
- [ ] Verify no test or import machinery references `train_gemma4.py` (the script is standalone, not imported)

## Acceptance Criteria

- [ ] `docs/research/train_gemma4_dense.py` exists
- [ ] `docs/research/train_gemma4.py` no longer exists
- [ ] `diff docs/research/train_gemma4_dense.py <old-train_gemma4.py>` is empty (or only docstring header differs)
- [ ] No broken references in active docs (historical review reports excluded)
- [ ] Task file for this feature (IMPLEMENTATION-GUIDE.md) still opens correctly — all links resolved
