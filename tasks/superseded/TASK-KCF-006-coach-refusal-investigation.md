---
id: TASK-KCF-006
title: Investigate Coach vLLM refusals (98 rejections)
status: backlog
created: 2026-04-05T19:30:00Z
updated: 2026-04-05T19:30:00Z
priority: medium
tags: [investigation, coach-refusal, vllm, infrastructure]
task_type: review
complexity: 4
parent_review: TASK-REV-3A86
feature_id: FEAT-KCF
wave: 3
implementation_mode: task-work
dependencies: []
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Investigate Coach vLLM refusals (98 rejections)

## Description

98 rejections (16% of all rejections) are caused by Coach vLLM refusals where the model
returns empty content with a refusal flag:

```
llm_failure: Coach response has no extractable content: content='', additional_kwargs=['refusal']
```

This is a separate issue from the criteria mismatch and affects both reasoning and direct targets.

### Investigation Objectives

1. **Pattern analysis**: Are refusals concentrated on specific categories, content types,
   or index ranges?
2. **Content triggers**: What Player content triggers Coach refusals? Is it specific
   topics (e.g., violence in Macbeth), long content, or specific formatting?
3. **Model behavior**: Is this a known issue with the vLLM model (Qwen2.5-14B)?
   Check if structured output mode increases refusal rates.
4. **Retry effectiveness**: The pipeline already has retry logic (`_invoke_with_retry`).
   Are refusals happening after retries are exhausted?
5. **Mitigation options**:
   - Increase Coach retry count for refusal-specific errors
   - Add refusal detection and retry with simplified prompt
   - Switch to a different Coach model that refuses less
   - Add content pre-filtering for known refusal triggers

### Data Sources

```bash
# Extract refusal rejections
python3 -c "
import json
with open('output/rejected.jsonl') as f:
    rejected = [json.loads(l) for l in f]
refusals = [r for r in rejected if 'refusal' in r.get('reason', '')]
print(f'Total refusals: {len(refusals)}')
for r in refusals[:5]:
    print(f'  index={r[\"target_index\"]}, category={r[\"category\"]}, type={r[\"type\"]}')
"
```

### Expected Output

- Root cause identification for Coach refusals
- Quantified impact (which categories, what % per category)
- Recommended mitigation with estimated recovery
- Priority assessment: is this worth fixing before or after the criteria fix?

## Acceptance Criteria

- [ ] Refusal pattern analysis completed (by category, type, index)
- [ ] Content triggers identified (or ruled out)
- [ ] Mitigation options evaluated with effort/impact
- [ ] Recommendation documented
