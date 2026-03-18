# Feature Spec Summary: GCSE English Training Example Synthesis

**Stack**: python (project-declared)
**Generated**: 2026-03-17T00:00:00Z
**Scenarios**: 28 total (6 smoke, 0 regression)
**Assumptions**: 5 total (2 high / 2 medium / 1 low confidence)
**Review required**: Yes

## Scope

This specification covers the Phase 1 synthesis script that generates GCSE English tutoring training examples by calling the Claude API. It defines the expected behaviour for loading generation targets from a YAML plan, calling the API with appropriate prompt templates (reasoning vs direct, single-turn vs multi-turn), validating output against the ShareGPT schema with metadata, enforcing the 75/25 reasoning/direct split, routing examples by layer (behaviour to train.jsonl, knowledge to rag_index/knowledge.jsonl), and handling errors, rate limits, and resumption.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 7 |
| Boundary conditions (@boundary) | 6 |
| Negative cases (@negative) | 7 |
| Edge cases (@edge-case) | 10 |

Note: Some scenarios carry multiple tags (e.g. @edge-case @negative).

## Deferred Items

None — all groups accepted.

## Open Assumptions (low confidence)

- **ASSUM-004**: Progress logged every 10 targets processed — no specification in context documents; confirm appropriate frequency for overnight GB10 runs

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Phase 1 synthesis script: generate GCSE training examples" \
      --context features/gcse-training-synthesis/gcse-training-synthesis_summary.md
