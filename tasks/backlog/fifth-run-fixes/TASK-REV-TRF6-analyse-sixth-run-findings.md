---
id: TASK-REV-TRF6
title: Analyse sixth run findings (Qwen3.5-35B-A3B-FP8, post-TRF-011-015)
status: review_complete
created: 2026-03-27T00:00:00Z
updated: 2026-03-27T00:00:00Z
priority: critical
tags: [review, sixth-run, qwen35, post-fix-validation]
complexity: 5
task_type: review
decision_required: true
parent_review: TASK-REV-TRF5
depends_on: [TASK-TRF-011, TASK-TRF-012, TASK-TRF-013, TASK-TRF-014, TASK-TRF-015]
review_results:
  mode: architectural-decision
  depth: standard
  score: 15
  findings_count: 3
  recommendations_count: 4
  decision: implement
  report_path: .claude/reviews/TASK-REV-TRF6-review-report.md
  completed_at: 2026-03-27T00:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Analyse Sixth Run Findings (Qwen3.5-35B-A3B-FP8, Post-TRF-011-015)

## Description

Analyse the sixth end-to-end run log at `docs/reviews/second-run/qwen35-run03.md` captured after implementing all fixes from TASK-REV-TRF5:

- **TASK-TRF-011**: Restored langchain-skills from `~/.claude.backup.20260317_101318/skills/`
- **TASK-TRF-012**: Fixed Coach tool leakage — bypassed `create_deep_agent` for Coach to exclude `FilesystemMiddleware`; reverted Player to `FilesystemBackend(root_dir=".")`
- **TASK-TRF-013**: Fixed Coach reasoning content extraction — fallback to `reasoning_content`/`additional_kwargs` when `.content` is empty
- **TASK-TRF-014**: Capped Player rag_retrieval calls to prevent excessive tool-use loops
- **TASK-TRF-015**: Investigated Player example truncation before Coach evaluation

This is the third run with Qwen3.5-35B-A3B-FP8 and the first run where the Coach should have zero leaked tools and the reasoning content extraction should correctly handle vLLM's think-mode split.

## Source Document

`docs/reviews/second-run/qwen35-run03.md`

## Key Questions to Analyse

### Fix Verification (from TASK-REV-TRF5)

1. **F1 (Coach tool leakage) — TASK-TRF-012**: Does the Coach now have exactly 0 tools? Are there any leaked `read_file`, `write_file`, `ls`, `glob`, `grep`, `edit_file`, `task`, `write_todos` in the Coach's tool schemas?
2. **F2 (Coach reasoning content) — TASK-TRF-013**: Does the Coach verdict parse correctly? If the model puts content in `<think>` tags, does the reasoning fallback extract it? Are verdicts valid CoachVerdict JSON?
3. **F3 (Player FilesystemBackend revert) — TASK-TRF-012**: Does the Player now use `FilesystemBackend` again? Are `rag_retrieval` + filesystem tools present?
4. **F4 (Player tool-use cap) — TASK-TRF-014**: Does the Player make 0-1 rag_retrieval calls (not 3+)?
5. **F5 (Example truncation) — TASK-TRF-015**: Does the Coach receive the complete training example JSON (system + user + assistant messages + metadata)?

### Deferred Fix Verification (still unverified from earlier runs)

6. **F7 (`<think>` blocks) — TASK-TRF-001**: Does Qwen3.5-35B produce valid `<think>...</think>` blocks for reasoning-type examples?
7. **F6 (retry cap) — TASK-TRF-006**: If any write failures occur, does the retry cap limit them to 3?

### Pipeline Performance

8. **How many targets were processed?** Total accepted vs rejected?
9. **What was the generation quality?** Are Coach verdicts reasonable? What scores were assigned?
10. **What was the throughput?** Tokens/second, time per target, overall pipeline duration?
11. **Token budget assessment**: Peak prompt_tokens vs 262K limit? Are Coach prompt tokens lower now without leaked tool schemas (~3K saved)?
12. **Are there any new issues?** Regressions or unexpected behaviours?

### Model Quality Assessment

13. **Tool calling reliability**: Does Qwen3.5-35B reliably call `rag_retrieval` with correct arguments?
14. **Example quality**: Are the generated training examples pedagogically sound and well-structured?
15. **Metadata correctness**: Are `ao`, `text`, `topic`, `grade_target`, `source`, `turns` values valid?
16. **`<think>` block quality**: Are reasoning traces meaningful, or just boilerplate?
17. **Coach evaluation quality**: Are Coach verdicts accurate and well-reasoned? Does the Coach correctly identify issues?

## Acceptance Criteria

- [ ] Confirm each TASK-TRF-011-015 fix is working as intended (5 new fixes verified)
- [ ] Verify deferred fixes from earlier runs (F7, F6) if code paths were exercised
- [ ] Pipeline progress summary (targets processed, accepted, rejected)
- [ ] Coach verdict analysis (score distribution, common issues, quality of feedback)
- [ ] Token budget assessment (Coach prompt tokens should be ~3K lower without leaked tool schemas)
- [ ] Tool visibility audit (confirm Coach has 0 tools, Player has rag_retrieval + filesystem)
- [ ] Reasoning content extraction audit (which extraction path was used — content/reasoning/blocks?)
- [ ] New issues identified (if any)
- [ ] Decision on whether pipeline is ready for overnight run (1,000 targets)
- [ ] Implementation tasks created for any new findings

## Decisions Required

1. **Production readiness** — Is the pipeline ready for a full 1,000-target overnight run?
2. **Model confirmation** — Does Qwen3.5-35B-A3B-FP8 meet quality requirements for this domain?
3. **Configuration tuning** — Any adjustments needed to temperature, max_turns, or timeouts?
4. **Outstanding issues** — Do any new findings block the overnight run?

## Context

This is the **sixth** iteration of the review cycle:

```
TASK-REV-E2A7 (Run 1) — ChromaDB path + array validation bugs
    → TASK-FRF-001 + TASK-FRF-002 (fixes)

TASK-REV-FRF2 (Run 2) — tool_calls.args deserialization + model arg structure
    → Model switch to Nemotron 3 Nano 4B + qwen3_coder parser

TASK-REV-FRF3 (Run 3) — Context window + tool leakage + Coach bypass + type coercion
    → TASK-TRF-001 through TASK-TRF-007 (6 code fixes + validation run)

TASK-REV-TRF4 (Run 4) — Coach verdict parser preamble bug + no RAG tool use + no token logging
    → TASK-TRF-008 through TASK-TRF-010 (3 code fixes)

TASK-REV-TRF5 (Run 5) — Coach empty content (think-mode split) + tool leakage regression + skills lost
    → TASK-TRF-011 through TASK-TRF-015 (skills restore + 4 code fixes)

TASK-REV-TRF6 (Run 6, THIS REVIEW) — Post-fix validation with all tool/reasoning/skills fixes
    → Goal: Confirm all fixes working, assess production readiness
```

Each iteration has progressively unblocked the pipeline. If successful, the pipeline moves to overnight production runs.

## Implementation Notes

This is a review/analysis task. Use `/task-review TASK-REV-TRF6` to execute the review, then create implementation tasks for any new findings.

## Test Execution Log

[Automatically populated by /task-work]
