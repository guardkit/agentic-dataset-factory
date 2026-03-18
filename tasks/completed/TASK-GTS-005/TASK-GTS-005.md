---
id: TASK-GTS-005
title: "Implement main synthesis orchestrator with API calls, routing, checkpoint, and logging"
task_type: feature
parent_review: TASK-REV-6DBC
feature_id: FEAT-GTS
wave: 4
implementation_mode: task-work
complexity: 6
dependencies:
  - TASK-GTS-003
  - TASK-GTS-004
status: completed
completed: 2026-03-17T00:00:00Z
completed_location: tasks/completed/TASK-GTS-005/
priority: high
tags: [synthesis, phase1, orchestrator, api]
consumer_context:
  - task: TASK-GTS-003
    consumes: VALIDATION_API
    framework: "synthesis.validator (validate_example, SplitTracker, DuplicateDetector)"
    driver: "direct import"
    format_note: "validate_example returns ValidationResult with is_valid, reason, route fields"
  - task: TASK-GTS-004
    consumes: TEMPLATE_API
    framework: "synthesis.templates (select_template, PromptPair)"
    driver: "direct import"
    format_note: "select_template returns a callable that takes GenerationTarget and returns PromptPair"
---

# Task: Implement main synthesis orchestrator with API calls, routing, checkpoint, and logging

## Description

Create `synthesis/synthesise.py` — the main entry point that drives the entire Phase 1 generation pipeline. It loads the generation plan, iterates through targets, calls the Claude API, validates responses, routes accepted examples to the correct output file, and handles errors, rate limits, and resumption.

## Requirements

### Generation plan loading
- Load `domains/gcse-english-tutor/generation-plan.yaml` via PyYAML
- Parse into `GenerationPlan` Pydantic model
- Fail fast with clear error if file missing or YAML invalid
- Maps to scenarios: "Processing all targets from the generation plan", "Generation plan file does not exist", "Generation plan contains invalid YAML"

### Claude API integration
- Use `anthropic.Anthropic` client (sync, not async — ADR-ARCH-006)
- Model: `claude-sonnet-4-5-20250514` (ASSUM-002 confirmed)
- For each target: select template → build prompt → call API → parse JSON response
- Parse response: extract JSON from Claude's text response, handle cases where model adds preamble
- Maps to scenario: "Generating a single-turn reasoning example"

### Error handling and retries
- Wrap each API call in try/except
- On `anthropic.RateLimitError` (429): retry up to 3 times with exponential backoff (1s, 2s, 4s) — ASSUM-003 confirmed
- On other API errors: log error, write to rejected.jsonl with reason "api_error", continue to next target
- On JSON parse failure from response: write to rejected.jsonl with reason "malformed_content"
- Maps to scenarios: "Claude API returns an error for a single target", "Handling Claude API rate limiting with retry", "Handling a response containing malformed JSON from the API"

### Validation pipeline
- For each parsed response: construct `TrainingExample` → run `validate_example()`
- If invalid: write to `output/rejected.jsonl` with reason from ValidationResult
- If valid: write to route path from ValidationResult
- Maps to scenarios: "Rejecting a malformed API response", "Reasoning example missing the think block"

### Output writing
- Append-per-line with `flush()` after each write — crash-safe JSONL
- Create output directories if they don't exist (`output/`, `output/rag_index/`)
- Maps to scenarios: "Output files remain valid after interrupted write", "Output directories are created if they do not exist"

### Checkpoint and resumption
- After each successfully processed target (accepted or rejected), write checkpoint to `output/.checkpoint.json`:
  ```json
  {"last_completed_index": 42, "accepted": 35, "rejected": 7}
  ```
- On startup: if checkpoint exists, resume from `last_completed_index + 1`
- Skip already-processed targets (no duplication)
- Maps to scenario: "Resuming generation after partial completion"

### Progress logging
- Structured JSON log entries via Python `logging` module with JSON formatter
- Log every 10 targets processed (ASSUM-004 confirmed)
- Each log entry: `{"total_attempted": N, "accepted": N, "rejected": N, "reasoning_pct": 0.75, "direct_pct": 0.25}`
- Final summary log at completion
- API key must NEVER appear in logs or output
- Maps to scenarios: "Progress logging during generation", "API key is not included in any output or log"

### Boundary conditions
- Generation plan with 0 targets: log "0 targets", exit cleanly, no output files created
- Generation plan with 1 target: process normally
- Null grade_target: passes through to metadata as null
- Maps to scenarios: "Generation plan with zero targets", "Generation plan with exactly one target", "Generating an example with null grade target"

### CLI entry point
- `python -m synthesis.synthesise` or `python synthesis/synthesise.py`
- Optional args: `--plan-path` (default: `domains/gcse-english-tutor/generation-plan.yaml`), `--output-dir` (default: `output/`)
- Use `argparse` for argument parsing

## Acceptance Criteria

- [ ] Script loads generation plan and processes all targets
- [ ] Claude API called with correct model and prompts
- [ ] Rate limit retry works with exponential backoff (mock-testable)
- [ ] API errors don't crash the pipeline — target recorded in rejected.jsonl
- [ ] Validation pipeline catches invalid examples with correct reason codes
- [ ] Output routed correctly: behaviour → train.jsonl, knowledge → knowledge.jsonl
- [ ] Checkpoint file updated after each target
- [ ] Resumption skips already-processed targets
- [ ] Progress logged every 10 targets as structured JSON
- [ ] Zero targets handled gracefully
- [ ] Output directories created if missing
- [ ] API key never appears in output or logs
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Seam Tests

The following seam tests validate the integration contracts with producer tasks. Implement these tests to verify the boundaries before integration.

```python
"""Seam tests: verify integration contracts with validator and templates modules."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("VALIDATION_API")
def test_validation_api_contract():
    """Verify validate_example returns expected ValidationResult shape.

    Contract: validate_example returns ValidationResult with is_valid, reason, route fields
    Producer: TASK-GTS-003
    """
    from synthesis.validator import (
        validate_example,
        SplitTracker,
        DuplicateDetector,
        TrainingExample,
        ValidationResult,
    )

    # Verify the function signature and return type exist
    assert callable(validate_example)
    # Verify ValidationResult has required fields
    assert hasattr(ValidationResult, "is_valid")
    assert hasattr(ValidationResult, "reason")
    assert hasattr(ValidationResult, "route")


@pytest.mark.seam
@pytest.mark.integration_contract("TEMPLATE_API")
def test_template_api_contract():
    """Verify select_template returns callable that produces PromptPair.

    Contract: select_template returns callable taking GenerationTarget, returning PromptPair
    Producer: TASK-GTS-004
    """
    from synthesis.templates import select_template, PromptPair
    from synthesis.validator import GenerationTarget

    # Verify select_template is callable
    assert callable(select_template)
    # Verify PromptPair has required fields
    assert hasattr(PromptPair, "system_prompt")
    assert hasattr(PromptPair, "user_prompt")
```

## Implementation Notes

This is the most complex task. Tests should mock the Anthropic client — never call the real API in tests. Use `unittest.mock.patch` to mock `anthropic.Anthropic`. Test the orchestration logic (iteration, checkpoint, resumption, error handling) independently of API behaviour.

The JSON parsing from Claude responses needs to be robust — Claude may wrap JSON in markdown code fences or add preamble text. Use a regex to extract the first `{...}` block, falling back to rejection if parsing fails.
