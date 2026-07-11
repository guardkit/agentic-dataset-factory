---
id: TASK-REV-TRF12
title: Lessons learned — improve DeepAgents template to prevent iteration
status: review_complete
created: 2026-03-27T21:30:00Z
updated: 2026-03-27T21:30:00Z
priority: high
tags: [review, lessons-learned, template-improvement, developer-experience, retrospective]
complexity: 7
task_type: review
decision_required: true
depends_on: [TASK-REV-TRF11]
review_results:
  mode: architectural + decision
  depth: comprehensive
  score: N/A
  findings_count: 31
  recommendations_count: 8
  decision: pending
  report_path: .claude/reviews/TASK-REV-TRF12-review-report.md
  completed_at: 2026-03-27T22:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Lessons Learned — Improve DeepAgents Template to Prevent Iteration

## Description

Analyse the full 11-run iteration history (TASK-REV-E2A7 through TASK-REV-TRF11, 31 fixes) to identify systemic causes of bugs and extract actionable improvements to the DeepAgents template, scaffolding, and development workflow. The goal is that the **next** adversarial-cooperation agent built from the template works on the first or second run — not the eleventh.

## Scope

This review covers three dimensions:

### 1. Bug Taxonomy — What Went Wrong and Why

Classify all 31 fixes (TRF-001 through TRF-031) by root cause category:

| Category | Example Fixes | Question |
|----------|--------------|----------|
| **SDK/framework misunderstanding** | Tool leakage (TRF-016), FilesystemMiddleware (TRF-006) | What template code or docs would have prevented this? |
| **Prompt engineering** | No think blocks (TRF-029), JSON format compliance (TRF-031) | What prompt patterns should be baked into templates? |
| **Model-specific quirks** | vLLM reasoning-parser stripping (TRF-025), think-mode content routing (TRF-020/021) | What model compatibility checks should templates include? |
| **Validation/schema gaps** | Range notation parser (TRF-028), metadata coercion (TRF-003) | What validators should ship with the template? |
| **Orchestration logic** | Coach verdict parsing (TRF-004), extraction failure handling (TRF-023) | What orchestrator patterns should be standard? |
| **Test coverage gaps** | Mock missing create_model (test fix this session) | What test patterns should the template generate? |

### 2. Template Improvements — What to Build Into the Scaffold

For each category above, identify concrete changes to the DeepAgents template:

- **Prompt templates**: Standard sections (CRITICAL response format, think block instructions) that should be generated automatically
- **Orchestrator patterns**: Extraction strategies, retry logic, validation pipelines that should be scaffolded
- **Test fixtures**: Mock patterns, factory test templates, integration test harnesses
- **Configuration guards**: Schema validators, model compatibility checks, tool inventory assertions
- **AGENTS.md generation**: Standard ALWAYS/NEVER/ASK boundaries that prevent common mistakes
- **Pre-flight checks**: Automated validation that runs before the first pipeline execution

### 3. Developer Experience — What to Improve in the Workflow

- **Run → Review → Fix cycle**: How to make the review process faster (automated log analysis?)
- **First-run success checklist**: A pre-launch checklist that catches the top 10 issues before running
- **Error diagnostics**: Better error messages that point to the fix, not just the symptom
- **Model compatibility matrix**: Document known quirks per model family (Qwen, Llama, Mistral, etc.)

## Key Questions

1. Which of the 31 fixes could have been prevented by better template scaffolding?
2. Which fixes required deep debugging that no template could have prevented?
3. What are the top 5 highest-impact template improvements?
4. Should the template include a "smoke test" mode that validates the pipeline before a full run?
5. What documentation should accompany the template to prevent common mistakes?

## Source Documents

- `.claude/reviews/TASK-REV-E2A7-review-report.md` (Run 1)
- `.claude/reviews/TASK-REV-FRF2-review-report.md` (Run 2)
- `.claude/reviews/TASK-REV-FRF3-review-report.md` (Run 3)
- `.claude/reviews/TASK-REV-TRF4-review-report.md` (Run 4)
- `.claude/reviews/TASK-REV-TRF5-review-report.md` (Run 5)
- `.claude/reviews/TASK-REV-TRF6-review-report.md` (Run 6)
- `.claude/reviews/TASK-REV-TRF7-review-report.md` (Run 7)
- `.claude/reviews/TASK-REV-TRF8-review-report.md` (Run 8)
- `.claude/reviews/TASK-REV-TRF9-review-report.md` (Run 9)
- `.claude/reviews/TASK-REV-TRF10-review-report.md` (Run 10)
- `.claude/reviews/TASK-REV-TRF11-review-report.md` (Run 11)
- `docs/reviews/second-run/` (all raw run logs)

## Acceptance Criteria

- [ ] All 31 fixes classified by root cause category
- [ ] Each category has concrete template improvement recommendations
- [ ] Top 5 highest-impact improvements identified and prioritised
- [ ] First-run success checklist drafted
- [ ] Template change recommendations with effort estimates
- [ ] Decision: which improvements to implement before next agent project

## Decisions Required

1. **Template scope** — Should improvements go into the DeepAgents template, a separate "adversarial-cooperation" template, or both?
2. **Priority** — Which improvements to implement first (before next agent vs backlog)?
3. **Automation** — Should the template include automated pre-flight validation?
4. **Documentation** — What form should the "known issues" guide take?

## Context

After 11 runs and 31 fixes across ~10 review cycles, the agentic-dataset-factory pipeline is fully functional. This review extracts the learnings so the next project doesn't repeat the same journey. The fixes span SDK misunderstandings, prompt engineering, model quirks, validation gaps, and orchestration logic — a rich dataset for improving the developer experience.

## Implementation Notes

This is a review/analysis task. Use `/task-review TASK-REV-TRF12` to execute the review, then create implementation tasks for template improvements.

## Test Execution Log

[Automatically populated by /task-work]
