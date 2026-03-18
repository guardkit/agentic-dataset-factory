---
id: TASK-GTS-003
title: "Implement validation logic for schema, think-block, split tracking, and duplicates"
task_type: feature
parent_review: TASK-REV-6DBC
feature_id: FEAT-GTS
wave: 3
implementation_mode: task-work
complexity: 5
dependencies:
  - TASK-GTS-002
status: completed
completed: 2026-03-17T00:00:00Z
completed_location: tasks/completed/TASK-GTS-003/
priority: high
tags: [synthesis, phase1, validation]
---

# Task: Implement validation logic for schema, think-block, split tracking, and duplicates

## Description

Add validation functions to `synthesis/validator.py` that go beyond Pydantic model validation. These functions enforce the business rules from the feature spec: think-block presence/absence, 75/25 split ratio tracking, duplicate detection, and output routing decisions.

## Requirements

### Think-block validation
- `validate_think_block(example: TrainingExample) -> ValidationResult`
- If `metadata.type == "reasoning"`: assistant messages MUST contain `<think>...</think>` block
- If `metadata.type == "direct"`: assistant messages MUST NOT contain `<think>` block
- Maps to scenarios: "Generating a single-turn reasoning example", "Generating a direct (non-reasoning) example", "Reasoning example missing the think block"

### Split ratio tracking
- `SplitTracker` class that maintains running counts of reasoning vs direct examples
- `track(example: TrainingExample) -> None` — updates counts
- `ratio() -> tuple[float, float]` — returns (reasoning_pct, direct_pct)
- `is_within_tolerance(tolerance: float = 0.05) -> bool` — checks 75/25 ± tolerance
- `warning_message() -> str | None` — returns warning if drifted beyond tolerance
- Maps to scenarios: "Maintaining the 75/25 reasoning-to-direct split", "Split ratio within acceptable tolerance", "Split ratio drifting beyond acceptable tolerance"

### Duplicate detection
- `DuplicateDetector` class using SHA-256 content hashing
- `check(example: TrainingExample) -> bool` — returns True if duplicate
- Hash is computed over the concatenated assistant message content (not metadata)
- Maps to scenario: "Duplicate content is detected on retry"

### Output routing
- `route_example(example: TrainingExample) -> str` — returns file path
  - `layer == "behaviour"` → `"output/train.jsonl"`
  - `layer == "knowledge"` → `"output/rag_index/knowledge.jsonl"`
- Maps to scenarios: "Routing behaviour examples to the training file", "Routing knowledge examples to the RAG index"

### Validation orchestrator
- `validate_example(example: TrainingExample, split_tracker: SplitTracker, duplicate_detector: DuplicateDetector) -> ValidationResult`
- Returns a `ValidationResult` dataclass with: `is_valid: bool`, `reason: str | None`, `route: str | None`
- Runs checks in order: schema (already Pydantic) → think-block → duplicate → split tracking
- Maps to scenario: "Rejecting a malformed API response"

## Acceptance Criteria

- [x] Think-block validation catches missing/extra think blocks
- [x] SplitTracker correctly tracks ratio across sequences of examples
- [x] SplitTracker warns at exactly the boundary (±5%)
- [x] DuplicateDetector identifies identical assistant content across different metadata
- [x] Output routing returns correct paths for behaviour/knowledge layers
- [x] validate_example orchestrates all checks and returns clear reason codes
- [x] Unit tests cover all 28-scenario-relevant validation paths (Groups A-D from feature spec)
- [x] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

`SplitTracker` and `DuplicateDetector` are stateful — they accumulate state across the generation run. The orchestrator in `synthesise.py` (TASK-GTS-005) will instantiate them once and pass them through.

Use `@dataclass` for `ValidationResult` rather than Pydantic (it's an internal type, not serialised).

## Completion Notes

- Added 6 new symbols to `synthesis/validator.py`: `ValidationResult`, `validate_think_block`, `SplitTracker`, `DuplicateDetector`, `route_example`, `validate_example`
- Created `synthesis/tests/test_validation_logic.py` with 48 tests (all passing)
- Full suite: 108/108 tests pass, 0 ruff lint errors
- Boundary behaviour: `is_within_tolerance` uses strict `<` so exactly ±5% triggers a warning (per AC)
