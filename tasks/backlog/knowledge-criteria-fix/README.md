# Feature: Knowledge-Layer Criteria Fix

## Parent Review

TASK-REV-3A86 — Post-knowledge-fix rejection rate analysis

## Problem Statement

The knowledge layer fix (adding Layer column to GOAL.md) introduced ~525 direct/knowledge
targets, but the evaluation criteria still apply `socratic_approach` (25% weight) uniformly
to all examples. Knowledge examples designed for factual RAG delivery are rejected at 62.7%
because they structurally cannot satisfy the Socratic questioning requirement.

Reasoning examples reject at 11.7% (within baseline). The entire rejection spike is caused
by the criteria-layer mismatch.

## Solution Approach

1. Add layer-aware evaluation criteria to GOAL.md (behaviour vs knowledge)
2. Create a direct-only GOAL variant for targeted re-run
3. Run 625 direct targets (~8hrs) with fixed criteria
4. Merge with existing reasoning output (saves ~42hrs vs full re-run)
5. Investigate Coach refusals as a separate follow-up

## Fix Safety

Verified: the fix changes ONLY GOAL.md text. Zero code changes required.
- `CoachVerdict.criteria_met` is `dict[str, bool]` — any criterion names accepted
- `is_accepted` checks decision/score/structural — never inspects criteria names
- Coach prompt rebuilt from GOAL.md each run — no cached state

## Subtasks

| Task | Description | Wave | Method |
|------|-------------|------|--------|
| KCF-001 | Add layer-aware criteria to GOAL.md | 1 | task-work |
| KCF-002 | Create GOAL-direct-only.md variant | 1 | direct |
| KCF-003 | Smoke test (10 direct targets) | 2 | direct |
| KCF-004 | Full direct-only re-run (625 targets) | 3 | manual |
| KCF-005 | Merge outputs from both runs | 3 | direct |
| KCF-006 | Investigate Coach vLLM refusals | 3 | task-work |

## Expected Outcome

- Combined rejection rate: ~10% (down from 36.4%)
- ~298 additional accepted direct examples
- ~450 knowledge examples properly evaluated for factual quality
- Total dataset: ~2,250 accepted examples
