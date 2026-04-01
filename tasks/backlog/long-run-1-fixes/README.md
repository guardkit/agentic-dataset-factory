# Long Run 1 Fixes (FEAT-LR1)

## Problem Statement

Long Run 1 achieved 83.4% acceptance across 1,000 targets but revealed:
- **245 Coach JSON parse failures** (untagged reasoning prose before JSON) causing ~70% of rejections
- **33 defective training entries** (empty responses, degenerate placeholders, unclosed think-blocks)
- **216 shallow Coach accepts** (score=5 without critical evaluation)
- **Critical RAG gaps** (3 set texts with 0 entries, severe Grade 4 underrepresentation)

## Solution

11 implementation tasks across 2 waves:

**Wave 1** (critical, before next run):
- Enable vLLM `guided_json` for Coach to eliminate parse failures at source
- Add post-generation validation to catch defective entries
- Strengthen Coach and Player prompts for better evaluation and metadata compliance
- Clean existing training data

**Wave 2** (tuning and coverage):
- Config tuning: essay max_turns, grade weighting, coach temperature
- RAG knowledge index: fill missing texts, fix misclassifications
- Increase multi-turn example weighting

## Tasks

| ID | Title | Priority | Wave | Status |
|----|-------|----------|------|--------|
| LR1-001 | Enable vLLM guided_json for Coach | Critical | 1 | Backlog |
| LR1-002 | Post-generation validation gate | High | 1 | Backlog |
| LR1-003 | Strengthen Coach prompt | High | 1 | Backlog |
| LR1-004 | Strengthen Player prompt (metadata) | Medium | 1 | Backlog |
| LR1-005 | Increase essay max_turns to 4 | Medium | 2 | Backlog |
| LR1-006 | Boost Grade 4 weighting | Medium | 2 | Backlog |
| LR1-007 | Lower Coach temperature | Low | 2 | Backlog |
| LR1-008 | Generate RAG for missing texts | Medium | 2 | Backlog |
| LR1-009 | Increase multi-turn weighting | Medium | 2 | Backlog |
| LR1-010 | Clean training data | High | 1 | Backlog |
| LR1-011 | Review RAG misclassification | Low | 2 | Backlog |

## Prior Fixes (from overnight-readiness, already completed)

These fixes from the earlier overnight-readiness feature (FEAT-OR) are already in
production and remain relevant as defensive fallbacks alongside Wave 1:

| ID | Title | Status | Location |
|----|-------|--------|----------|
| TASK-OR-006 | Fix retry message format (dual system msg bug) | Completed | tasks/completed/TASK-OR-006/ |
| TASK-OR-007 | Add httpx.HTTPStatusError to exception handlers | Completed | tasks/completed/TASK-OR-007/ |

**Note**: LR1-001 (guided_json) should eliminate Coach parse failures at the vLLM level,
making OR-006's retry fix a fallback rather than primary mitigation. OR-007's exception
handling remains independently valuable for resilience.

## Key Files

- Review report: `docs/reviews/TASK-REV-649A-long-run-1-review-report.md`
- Implementation guide: `tasks/backlog/long-run-1-fixes/IMPLEMENTATION-GUIDE.md`
- Run 1 logs: `docs/reviews/longer-runs/long_run_1.md`
- Training data: `output/train.jsonl` (761 examples)
- Rejected data: `output/rejected.jsonl` (166 examples)
- RAG index: `output/rag_index/knowledge.jsonl` (73 entries)
