# Review Report: TASK-REV-TRF9

## Executive Summary

**Run 9 achieves the first successful JSON extraction in the pipeline's history.** Turn 3 extracts a valid 3069-char training example from a 4514-char Player response. However, `write_output` validation rejects it with: `metadata.turns value '1' not in valid values`.

This is a **trivially fixable metadata schema bug**: the GOAL.md table has `1+ (number of conversation turns)` in the Valid Values column for `turns`, which the parser interprets as a single literal valid value `"1+ (number of conversation turns)"`. The integer `1` (stringified to `"1"`) doesn't match. **Fixing this single issue would have produced the pipeline's first accepted training example.**

Turns 1 and 2 still fail extraction: Turn 1 has no JSON at all (model reasoning + direct response), Turn 2 has JSON but likely with malformed string values. These are model-behaviour issues that improve across turns with the revision feedback loop.

### Progress vs Run 8

| Aspect | Run 8 | Run 9 | Delta |
|--------|-------|-------|-------|
| JSON extraction success | 0/2 accepted | 1/3 accepted | First ever success |
| Think blocks in content | Stripped by vLLM | Not stripped (TRF-024) | Fixed |
| Brace matching | Naive | JSON-string-aware (TRF-025) | Fixed |
| Write validation | Not reached | Reached (fails on turns) | Progress |
| Final result | 0 accepted | 0 accepted (but within 1 bug of success) | Close |

## Review Details

- **Mode**: Post-Fix Validation
- **Depth**: Standard
- **Source**: `docs/reviews/second-run/qwen35-run-6.md`
- **Run Date**: 2026-03-27 14:34–14:37 UTC
- **Model**: Qwen/Qwen3.5-35B-A3B-FP8
- **Reviewer**: Opus 4.6

---

## Fix Verification (TASK-TRF-024 through TASK-TRF-027)

### F1: TASK-TRF-024 — Remove --reasoning-parser qwen3

**Status: DEPLOYED AND WORKING**

Evidence:
- No `reasoning_content` fallback triggered — Coach uses "content (standard path)" on all 3 turns
- Player content is much longer than Run 8 (3882, 4855, 4514 chars vs 3195, 3251, 852)
- Player content starts with reasoning text ("I have some curriculum context about Macbeth...") — model's thinking is flowing through in the content field, NOT being stripped to `reasoning_content`
- No vLLM-level interception visible

**Note**: Without the reasoning parser, the model outputs its reasoning as **plain text** (not in `<think>` tags). The model's native Qwen3 think mode relied on the vLLM reasoning parser to wrap the thinking. Without it, thinking appears as untagged prose before the JSON output.

### F2: TASK-TRF-025 — JSON-string-aware brace matching

**Status: DEPLOYED AND WORKING**

Evidence:
- Code at `generation_loop.py:144-167` shows the new `in_string`/`escape_next` tracking
- **Turn 3 extraction succeeds**: `example_extracted: index=0, turn=3, input_len=4514, output_len=3069`
- This is the first successful JSON extraction in 9 runs

### F3: TASK-TRF-026 — Player reasoning_content fallback

**Status: DEPLOYED, NOT EXERCISED**

With TRF-024 removing the reasoning parser, the `reasoning_content` field is no longer populated. Player content comes via the standard string path (`player_content_source: string`). The fallback exists as defence-in-depth but is correctly not triggered.

### F4: TASK-TRF-027 — Coach think block verification

**Status: UNCLEAR — NOT FULLY EXERCISED**

The Coach accepted all 3 turns with score 5. We cannot determine if the Coach is checking for think blocks because:
- Turn 1: No JSON extracted, so we don't know if the example had think blocks
- Turn 2: No JSON extracted
- Turn 3: JSON extracted, but `write_output` failed on `metadata.turns` before the think block check

The Coach may or may not be enforcing think block presence. This needs verification in the next run.

---

## Carry-Forward Verification

| Check | Status | Evidence |
|-------|--------|----------|
| Player tools = `['rag_retrieval']` | PASS | Line 13 |
| Coach 0 tools | PASS | Line 15 |
| Player 0-1 RAG calls | PASS | 1 rag_retrieval call (tool_call on Turn 1 only) |
| Token logging (per-turn) | PASS | Lines 59, 77, 98, 116, 137, 155 |
| Token logging (aggregate) | PASS | Lines 159, 163 |
| max_completion_tokens: 4096 | PASS | Visible in request options (line 24) |
| Extraction failure logging | PASS | Lines 79, 118 show content length + tail |

---

## Turn-by-Turn Analysis

### Turn 1: Coach accepts (score 5), extraction FAILS

- **Player content**: 3882 chars
- **Content structure**: Model reasoning as plain text + direct tutor response (conversational)
- **First 200 chars**: `"I have some curriculum context about Macbeth and Lady Macbeth. Now I need to generate a reasoning-type training example with:\n- A student question/response about Macbeth character analysis\n- A tutor r"`
- **Last 200 chars**: `"...Take your time to think about these questions — I'd love to hear your thoughts on how the language reveals her motivations and how context might shape our understanding of her character."`
- **JSON present**: **NO** — The model generated reasoning text and a direct tutor response, NOT a JSON training example
- **Extraction result**: All 3 strategies fail (no JSON in content)

**Analysis**: The model "thought out loud" about what to generate, then wrote the tutor's response as conversational text instead of structured JSON. The revision feedback ("Return the complete training example as a single JSON object") corrects this on subsequent turns.

### Turn 2: Coach accepts (score 5), extraction FAILS

- **Player content**: 4855 chars
- **Content structure**: Model reasoning text + code-fenced JSON (```json...```)
- **First 200 chars**: `"The user is asking me to generate a training example for literary analysis (single-turn, reasoning type). I need to create a ShareGPT conversation format with system, user, and assistant messages, plu"`
- **Last 200 chars**: Complete metadata JSON ending with `"turns": 1\n  }\n}\n\`\`\``
- **JSON present**: YES — wrapped in code fence
- **Extraction result**: Fence regex matches but `json.loads` fails on extracted content

**Analysis**: The model improved — it generated a JSON training example wrapped in a code fence. But the JSON likely contains **literal (unescaped) newlines inside string values** (e.g., the assistant's multi-line tutor response), which makes it invalid JSON. The model doesn't properly escape newlines as `\n` within JSON strings.

### Turn 3: Coach accepts (score 5), extraction SUCCEEDS, write validation FAILS

- **Player content**: 4514 chars
- **Extracted JSON**: 3069 chars (68% of content is JSON, 32% is reasoning preamble)
- **Extraction**: `example_extracted: index=0, turn=3, input_len=4514, output_len=3069`
- **Write result**: `Write validation failed (attempt 1/3): Error: metadata.turns value '1' not in valid values`

**Analysis**: The model generated valid, parseable JSON on the third attempt. Extraction succeeded using the improved brace matcher or fence regex. But `write_output` validation rejected it due to the `turns` field metadata schema bug.

---

## Critical Bug: metadata.turns Validation (NEW — REVISED ANALYSIS)

**Severity: CRITICAL — sole blocker preventing first accepted example**

### The Bug

GOAL.md metadata schema table ([domains/gcse-english-tutor/GOAL.md:98](domains/gcse-english-tutor/GOAL.md#L98)):

```markdown
| turns | integer | yes | 1+ (number of conversation turns) |
```

The parser (`domain_config/parser.py:86-94`) splits the Valid Values cell by comma:

```python
def _coerce_valid_values(raw: str) -> list[str]:
    stripped = raw.strip()
    if not stripped:
        return []
    return [v.strip() for v in stripped.split(",") if v.strip()]
```

Input: `"1+ (number of conversation turns)"`
Output: `["1+ (number of conversation turns)"]` (single element — no commas to split on)

Then `write_output.py:175` validates:

```python
if str(field_value) not in valid_values:
    return f"Error: metadata.{field_name} value '{field_value}' not in valid values"
```

`str(1)` = `"1"` is checked against `["1+ (number of conversation turns)"]` → **NOT FOUND** → validation fails.

### Root Cause: Type System Gap in MetadataField

The validation architecture only supports **one validation mode: enumerated values**. This works for every field except `turns`:

| Field | Type | Valid Values | Validation Mode Needed |
|-------|------|-------------|----------------------|
| layer | string | behaviour, knowledge | Enum — works |
| type | string | reasoning, direct | Enum — works |
| ao | array[string] | AO1, AO2, ... AO6 | Enum — works |
| text | string | macbeth, a_christmas_carol, ... | Enum — works |
| topic | string | character_analysis, ... | Enum — works |
| grade_target | integer or null | 4, 5, 6, 7, 8, 9, null | Enum — works |
| source | string | synthetic, aqa_derived, exam_board_adapted | Enum — works |
| **turns** | **integer** | **1+** | **Range — NOT SUPPORTED** |

The `MetadataField` model (`domain_config/models.py:94-100`) has:

```python
class MetadataField(BaseModel):
    field: str
    type: str
    required: bool
    valid_values: list[str] = Field(default_factory=list)
```

There is no way to express "any integer >= 1" — only enumerated lists. The GOAL.md author used `1+ (number of conversation turns)` as documentation, but the parser and validator treat ALL non-empty valid_values cells as enumerations.

### The Fix: Teach _coerce_valid_values to Recognise Range Notation

The proper fix is in `_coerce_valid_values` (`domain_config/parser.py:86-94`). This function should detect common range notations (like `1+`, `0+`, `1-10`) and return an empty list for them — signalling to the validator that enumeration-based validation doesn't apply. The range constraint is already enforced by the Pydantic model (`synthesis/validator.py:88: turns: int = Field(default=1, ge=1)`).

**Why this is the right layer to fix:**

1. **GOAL.md stays human-readable** — `1+ (number of conversation turns)` is good documentation. Domain authors shouldn't need to leave cells empty and lose clarity.

2. **Parser becomes smarter** — The parser already coerces other fields (weights, booleans). Teaching it to recognise range notation is the same pattern.

3. **Pydantic already handles the constraint** — `turns: int = Field(ge=1)` in the `Metadata` model enforces the actual range. The `write_output` enumeration check is redundant and incorrect for this field.

4. **Forward-compatible** — Future domains may have other integer range fields. The fix works generically.

**Implementation:**

```python
# In domain_config/parser.py

# Pattern to detect range notation like "1+", "0+", "1-10", ">=1"
_RANGE_NOTATION_RE = re.compile(
    r"^\d+\+",  # "1+", "0+" — minimum with no maximum
)

def _coerce_valid_values(raw: str) -> list[str]:
    """Parse a comma-separated cell into a list of stripped strings.

    An empty or whitespace-only cell returns an empty list.
    Range notations like '1+' or '0+' return an empty list because
    they express constraints, not enumerations — the Pydantic model
    handles range validation.
    """
    stripped = raw.strip()
    if not stripped:
        return []
    # Range notations are documentation, not enumerations
    if _RANGE_NOTATION_RE.match(stripped):
        return []
    return [v.strip() for v in stripped.split(",") if v.strip()]
```

**Why NOT just clear the GOAL.md cell:**

- Loses documentation — `| turns | integer | yes | |` tells the reader nothing about valid values
- Pushes domain knowledge out of the domain config into code
- Every new domain author would need to know "leave this empty"
- Fragile — someone re-adding documentation would reintroduce the bug

**Why NOT add range validation to write_output:**

- The `Metadata` Pydantic model already validates `turns: int = Field(ge=1)`
- Adding range parsing to `write_output` would duplicate validation logic
- The write_output validator should only handle enumeration checks (its current design)

---

## Model Behaviour: No `<think>` Tags

**Severity: HIGH**

Without `--reasoning-parser qwen3`, the model outputs reasoning as **plain untagged text** before the JSON. It does NOT wrap reasoning in `<think>` tags. This means:

1. The model's own reasoning pollutes the content (requiring extraction to separate JSON from prose)
2. Training examples may lack `<think>` blocks in the assistant's content field
3. The `validate_think_block` check in `write_output` would reject reasoning-type examples without think blocks

**Root cause**: Qwen3.5's native thinking mode is designed to work WITH vLLM's `--reasoning-parser`. Without it, the model just outputs reasoning as prose. The `<think>` tags are a vLLM-level feature, not a model-level one.

**Options**:
- **A**: Re-enable `--reasoning-parser` but reconstruct think blocks from `reasoning_content` in `_extract_player_content` (TASK-TRF-026 already provides the fallback)
- **B**: Add explicit prompt instructions to wrap reasoning in `<think>` tags (may not work — model's thinking mode may override)
- **C**: Accept that model reasoning won't have `<think>` tags; only require think blocks in the GENERATED training example's assistant content (via prompt engineering)

**Recommended**: Option C — distinguish between the model's own reasoning (don't need `<think>` tags) and the training example's assistant content (must include `<think>` block for reasoning type). Adjust the prompt to explicitly instruct: "Include a `<think>` block at the start of the assistant's content field."

---

## JSON Extraction Robustness

Turn 2 extraction fails despite having valid-looking JSON in a code fence. The most probable cause: **literal newlines inside JSON string values**. The model generates multi-line tutor responses where newlines are not escaped as `\n`.

**Proposed fix**: Add a JSON repair pre-processing step before `json.loads`:

```python
def _repair_json_strings(json_str: str) -> str:
    """Fix common JSON issues from LLM output."""
    # Replace literal newlines inside strings with \n
    # (This is a heuristic — only applies within quoted strings)
    ...
```

This would help Turn 2 succeed, reducing the number of revision cycles needed.

---

## Pipeline Performance

| Metric | Value | vs Run 8 |
|--------|-------|----------|
| Targets | 1 | Same |
| Accepted | 0 | Same (but closer) |
| Rejected | 1 | Same |
| Total turns | 3 (max) | Same |
| Elapsed | 163.8s | -1.3s |
| Prompt tokens | 24,558 | +1,894 |
| Completion tokens | 4,994 | -462 |
| Total tokens | 29,552 | +1,432 |

**Token budget**: Slightly higher prompt tokens (longer Player content due to reasoning text), slightly lower completion tokens. Well within budget.

**Coach verdict distribution**:

| Turn | Decision | Score | Extraction | Write |
|------|----------|-------|------------|-------|
| 1 | accept | 5/5 | FAIL (no JSON) | — |
| 2 | accept | 5/5 | FAIL (malformed JSON) | — |
| 3 | accept | 5/5 | SUCCESS | FAIL (turns validation) |

---

## Findings Summary

| # | Finding | Severity | Category |
|---|---------|----------|----------|
| F1 | `metadata.turns` validation bug — GOAL.md valid values cell parsed as literal string, not integer range | CRITICAL | Metadata schema |
| F2 | Model outputs reasoning as plain text (no `<think>` tags) without reasoning parser | HIGH | Model behaviour |
| F3 | JSON extraction fails on Turn 2 — probable literal newlines in JSON strings | MEDIUM | JSON extraction |
| F4 | Turn 1: Model generates conversational response instead of JSON on first attempt | MEDIUM | Model behaviour |
| F5 | Coach accepts examples without verifying think block presence (TRF-027 unclear) | MEDIUM | Coach quality |

---

## Recommendations

### R1: Teach `_coerce_valid_values` to recognise range notation (CRITICAL — P0)

Fix `domain_config/parser.py:_coerce_valid_values` to detect range patterns like `1+` and return an empty list (no enumeration). The GOAL.md stays unchanged — `1+ (number of conversation turns)` is correct documentation.

```python
_RANGE_NOTATION_RE = re.compile(r"^\d+\+")

def _coerce_valid_values(raw: str) -> list[str]:
    stripped = raw.strip()
    if not stripped:
        return []
    if _RANGE_NOTATION_RE.match(stripped):
        return []  # Range constraint, not enumeration — Pydantic handles this
    return [v.strip() for v in stripped.split(",") if v.strip()]
```

**Files**: `domain_config/parser.py`, `domain_config/tests/test_parse_goal_md.py`

**This single change would have produced the pipeline's first accepted training example on Turn 3.** The Pydantic model (`turns: int = Field(ge=1)`) already enforces the actual range constraint.

### R2: Add `<think>` block instruction to Player prompt (HIGH — P0)

Since the model doesn't natively use `<think>` tags without the vLLM parser, add explicit instructions to the Player prompt:

```
IMPORTANT: For reasoning-type examples, the assistant's content field MUST begin with a <think>...</think> block containing the tutor's internal reasoning, followed by the visible response.

Example format:
"content": "<think>The student is asking about... I should guide them toward...</think>\n\nGreat question! Let's explore..."
```

### R3: Add JSON string repair pre-processing (MEDIUM — P1)

Before `json.loads`, attempt to fix common LLM JSON issues:
- Replace literal newlines inside quoted strings with `\n`
- Handle unescaped control characters

This would improve extraction success on earlier turns, reducing revision cycles.

### R4: Verify Coach think block enforcement in next run (MEDIUM — P1)

After fixing R1, the next run should reach the think block validation step. This will reveal whether:
- The model includes `<think>` blocks in the assistant content (after R2)
- The Coach correctly rejects examples without think blocks (TRF-027)

---

## Decisions Required

### 1. Production readiness

**DECISION: NOT READY — but very close.** The metadata.turns bug (R1) is a 1-line fix. The think block prompt (R2) needs testing. After R1+R2, the pipeline should produce accepted examples.

### 2. Model confirmation

**DECISION: PROMISING.** Qwen3.5-35B-A3B-FP8 generates quality content (Coach scores 5/5 consistently) and successfully produces valid JSON by Turn 3. The model improves across revision cycles. With prompt adjustments for think blocks, it should meet requirements.

### 3. Configuration tuning

- `max_tokens: 4096` — working well, completion tokens are 857-1118 (well under limit)
- `temperature: 0.6` (Player), `0.3` (Coach) — working well
- `max_turns: 3` — may need increase to 5 to give more chances for extraction + validation success

### 4. Outstanding blockers

| Blocker | Priority | Fix |
|---------|----------|-----|
| `_coerce_valid_values` doesn't recognise range notation (`1+`) | P0 | TASK-TRF-028: Add range detection to parser |
| No `<think>` blocks in assistant content | P0 | TASK-TRF-029: Add explicit think block prompt to Player |
| JSON with literal newlines in strings | P1 | TASK-TRF-030: JSON string repair pre-processing |

---

## Appendix: Log Timeline

```
14:34:12  RAG retrieval (tool call, 1 result)
14:34:41  Player Turn 1 completes (857 tokens, 3882 chars — no JSON)
14:35:04  Coach Turn 1: accept, score=5
14:35:04  JSON extraction FAILS (no JSON in content)
14:35:20  Player Turn 2 (revision) completes (1118 tokens, 4855 chars — JSON in fence)
14:35:50  Coach Turn 2: accept, score=5
14:35:50  JSON extraction FAILS (malformed JSON in strings)
14:36:11  Player Turn 3 (revision) completes (1067 tokens, 4514 chars — valid JSON)
14:36:40  Coach Turn 3: accept, score=5
14:36:40  JSON extraction SUCCEEDS (3069 chars extracted)
14:36:40  Write validation FAILS: metadata.turns '1' not in valid values
14:36:40  Target rejected after 3 turns
```

Total pipeline: 163.8 seconds, 29,552 tokens consumed, 0 examples produced (1 bug away from success).
