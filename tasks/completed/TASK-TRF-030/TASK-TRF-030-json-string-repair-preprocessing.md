---
id: TASK-TRF-030
title: JSON string repair pre-processing for literal newlines
status: completed
created: 2026-03-27T18:00:00Z
updated: 2026-03-27T18:30:00Z
completed: 2026-03-27T18:30:00Z
priority: medium
tags: [json-extraction, generation-loop, ninth-run]
complexity: 3
parent_review: TASK-REV-TRF9
feature_id: FEAT-TRF9
depends_on: [TASK-TRF-028]
wave: 2
implementation_mode: task-work
test_results:
  status: passed
  tests_total: 77
  tests_passed: 77
  tests_failed: 0
  coverage: null
  last_run: 2026-03-27T18:30:00Z
---

# Task: JSON String Repair Pre-Processing for Literal Newlines

## Problem

In Run 9, Turn 2's JSON extraction fails despite the content being wrapped in a valid code fence with structurally complete JSON. The most probable cause: the model generates JSON with **literal (unescaped) newlines inside string values**.

JSON spec requires newlines in strings to be escaped as `\n`. But the model generates:

```json
{
  "content": "Great question!
Let's explore this together..."
}
```

Instead of:

```json
{
  "content": "Great question!\nLet's explore this together..."
}
```

This causes `json.loads` to fail with a JSONDecodeError, even after the fence regex or brace matcher successfully extracts the candidate.

## Fix

Add a `_repair_json_strings` function that fixes common LLM JSON issues before `json.loads` is called. Call it within each `try` block of `_extract_json_object` before `json.loads`.

```python
def _repair_json_strings(json_str: str) -> str:
    """Fix common JSON issues from LLM output.

    Replaces literal newlines inside JSON string values with \\n.
    Uses a state machine to track whether we're inside a quoted string.
    """
    result = []
    in_string = False
    escape_next = False

    for ch in json_str:
        if escape_next:
            result.append(ch)
            escape_next = False
            continue
        if ch == '\\' and in_string:
            result.append(ch)
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue
        if in_string and ch == '\n':
            result.append('\\n')
            continue
        if in_string and ch == '\t':
            result.append('\\t')
            continue
        result.append(ch)

    return ''.join(result)
```

Then in `_extract_json_object`, wrap each `json.loads` call:

```python
# Try 1: Direct parse
try:
    repaired = _repair_json_strings(content)
    parsed = json.loads(repaired)
    ...
```

## Files to Modify

- `entrypoint/generation_loop.py` (add `_repair_json_strings`, modify `_extract_json_object`)
- `entrypoint/tests/test_generation_loop.py` (add tests)

## Acceptance Criteria

- [ ] `_repair_json_strings` replaces literal `\n` inside JSON strings with `\\n`
- [ ] `_repair_json_strings` replaces literal `\t` inside JSON strings with `\\t`
- [ ] `_repair_json_strings` does NOT affect newlines between JSON tokens (structural whitespace)
- [ ] `_repair_json_strings` handles escaped quotes correctly (`\"`)
- [ ] Existing extraction tests pass unchanged
- [ ] New test: JSON with literal newline in string value repairs and parses correctly
- [ ] New test: JSON with structural newlines (between tokens) unchanged

## Test Cases

```python
def test_repair_literal_newline_in_string():
    bad = '{"content": "Hello\nWorld"}'
    repaired = _repair_json_strings(bad)
    assert json.loads(repaired) == {"content": "Hello\nWorld"}

def test_repair_preserves_structural_newlines():
    good = '{\n  "key": "value"\n}'
    repaired = _repair_json_strings(good)
    assert json.loads(repaired) == {"key": "value"}

def test_repair_handles_escaped_quotes():
    s = '{"content": "She said \\"hello\\"\\nand left"}'
    repaired = _repair_json_strings(s)
    parsed = json.loads(repaired)
    assert 'hello' in parsed['content']

def test_repair_tab_in_string():
    bad = '{"content": "col1\tcol2"}'
    repaired = _repair_json_strings(bad)
    assert json.loads(repaired) == {"content": "col1\tcol2"}
```

## Note

This is a robustness improvement. With this fix, Turn 2 extraction would likely succeed on the first or second attempt, reducing revision cycles and improving throughput for the overnight run.
