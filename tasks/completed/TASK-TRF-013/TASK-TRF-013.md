---
id: TASK-TRF-013
title: Fix Coach reasoning content extraction — handle vLLM think-mode split
status: completed
created: 2026-03-26T00:00:00Z
updated: 2026-03-27T00:00:00Z
completed: 2026-03-27T00:00:00Z
completed_location: tasks/completed/TASK-TRF-013/
priority: critical
tags: [bug-fix, coach, reasoning, vllm, P0]
complexity: 4
task_type: implementation
parent_review: TASK-REV-TRF5
feature_id: FEAT-TRF5
wave: 1
implementation_mode: task-work
depends_on: [TASK-TRF-011]
test_results:
  status: passed
  coverage: null
  last_run: 2026-03-27T00:00:00Z
  tests_passed: 75
  tests_failed: 0
---

# Task: Fix Coach Reasoning Content Extraction

## Description

The Coach LLM generated 578 completion tokens but the pipeline received an empty string. The root cause is a three-layer interaction:

1. **vLLM** (`--reasoning-parser qwen3`) splits the response: `reasoning_content` gets the `<think>` block content, `content` gets the remainder. When the entire Coach response is inside `<think>` tags, `content` is empty.

2. **LangChain ChatOpenAI** discards `reasoning_content` because it's a non-standard field. Per the `langchain-openai` docs: *"Non-standard response fields added by third-party providers (e.g., reasoning_content) are NOT extracted."*

3. **Pipeline** (`generation_loop.py:479`) reads `.content` → empty string → parse failure.

### Content Extraction Flow

```
Qwen3.5-35B → <think>JSON verdict</think>
    ↓ vLLM --reasoning-parser qwen3
reasoning_content: "JSON verdict"  |  content: ""
    ↓ LangChain ChatOpenAI
AIMessage(content="", additional_kwargs={})  ← reasoning_content LOST
    ↓ Pipeline
coach_content = "" → ValueError
```

### Fix Strategy

**Primary approach**: In `generation_loop.py`, after extracting `coach_content`, add a fallback that checks for reasoning content:

1. Check `coach_response["messages"][-1].content` (existing path)
2. If empty/whitespace, check `coach_response["messages"][-1].additional_kwargs.get("reasoning_content")`
3. If still empty, check if `.content` is a list of blocks and look for `type: "reasoning"` blocks
4. If still empty, raise the existing ValueError

This preserves the Coach's thinking capability — we're not disabling reasoning, just ensuring we capture the output regardless of where the LLM provider places it.

**Note**: TASK-TRF-012 (fix tool leakage) may resolve this issue indirectly. If the Coach has no leaked tools, it may output JSON directly in `content` rather than entering a tool-calling think loop. Both fixes should be implemented for defense in depth.

### Key Files

- `entrypoint/generation_loop.py:479` — Coach content extraction
- `entrypoint/generation_loop.py:187-217` — `_parse_coach_verdict()` function
- `entrypoint/tests/test_generation_loop.py` — Add test cases

### Interface Contract

The Coach content extraction should try these sources in order:
1. `message.content` (string) — standard path
2. `message.text` (property) — filters to text blocks only
3. `message.additional_kwargs["reasoning_content"]` — vLLM reasoning
4. Content blocks with `type: "reasoning"` in `message.content` (if list)

The extracted content is then passed to `_parse_coach_verdict()` which already has the 3-try JSON extraction strategy.

## Acceptance Criteria

- [x] Coach verdict extraction handles empty `.content` with reasoning fallback
- [x] New test: mock AIMessage with empty content + reasoning_content in additional_kwargs → verdict parsed correctly
- [x] New test: mock AIMessage with content as list of blocks including reasoning type → verdict parsed correctly
- [x] New test: mock AIMessage with normal string content → existing path still works
- [x] Existing generation_loop tests still pass
- [x] Logging: log which extraction path was used (content/reasoning/blocks)

## Context

This is one of two P0 blockers from TASK-REV-TRF5. The model DID generate a valid verdict (578 tokens) — it was lost in the ChatOpenAI → AIMessage translation. This fix ensures we capture the verdict regardless of where it lands in the response object.
