# Review Report: TASK-REV-4AA0 — Revision 2

## Executive Summary

**Confidence: HIGH.** Revision 2 replaces the Revision 1 analysis with empirically validated findings from direct inspection of the backup run output (1,716 records from `output_backup_run1/train.jsonl`), the rejection log (`rejected.jsonl`, 612 target rejections with 927 format-gate hits), end-to-end round-trip tests of `_repair_json_strings` and `_extract_json_object`, and a full data-flow walk from Player response through to disk.

**Root cause**: The Player LLM sporadically emits JSON where the `role` key in a non-first message carries a leading space inside the quoted string (`{" role": "user", ...}`). The Python pipeline faithfully preserves this through `json.loads` → dict → `json.dumps`, because **no component validates the key set of every message dict**. The defect rate is 2/1716 overall (0.12 %), and — this is new — **strictly correlated with multi-turn generation**: 2/238 multi-turn records (0.84 %) vs. **0/1478** single-turn records. The defect consistently lands at message index 3 (the second user turn) after the `}, {` JSON object separator, consistent with LLM tokenization drift at that specific delimiter position rather than prompt contamination or Python code mutation.

**Recommended fix**: Add a deterministic structural gate in `write_output` that enforces `set(msg.keys()) == {"role", "content"}` and `msg["role"] in {"system","user","assistant"}` for **every** message. Simulated against the full backup dataset: **0 false positives** on 1,716 records, rejects exactly the 2 known-bad records. Regression risk is therefore minimal.

- **Mode**: Architectural / code-quality
- **Depth**: Comprehensive (Revision 2)
- **Decision**: Refactor — single-file change with regression tests

## Evidence (what I verified on-disk)

### E1 — Ground truth: the two corrupted records

```
output_backup_run1/train.jsonl: 1716 lines, 2 malformed records
  line 1145, msg[3]: keys=[' role', 'content']   metadata.turns=2, type=reasoning, text=macbeth
  line 1330, msg[3]: keys=[' role', 'content']   metadata.turns=2, type=reasoning, text=language_paper_1
```

Raw substring pattern in both records:

```
..."}, {" role": "user", "content": "...
```

Both records are 5-message conversations (`system, user, assistant, user, assistant`). Both defects are at position 3 — the second user turn. Both are `turns=2` reasoning-type examples. The backup preserved in `output_backup_pre_rerun/train.jsonl` is byte-identical for these records, confirming the defect is reproducible across runs rather than an incidental file artefact.

### E2 — Defect rate correlates with multi-turn generation

```
train.jsonl metadata.turns distribution:
  1-turn: 1471 records   →   0 defects   (0.00 %)
  2-turn:  206 records   →   2 defects   (0.97 %)
  3-turn:    7 records   →   0 defects
  4-turn:   31 records   →   0 defects
  5-turn:    1 record    →   0 defects

Multi-turn (len>=4 msgs): 238 records, 2 defects → 0.84 %
Single-turn  (len==3 msgs): 1478 records, 0 defects → 0.00 %
```

The defect **never occurs** in single-turn records — it only appears where the generated JSON contains the `}, {` message separator. This is strong circumstantial evidence that the defect is LLM tokenization drift at the inter-object boundary, not a systemic issue with all `role` emissions.

### E3 — `_repair_json_strings` is not the culprit

Direct test (`entrypoint.generation_loop._repair_json_strings`) executed against three fixtures:

```
TEST1 (corrupted JSON in):
  input  == output?  True                ← _repair_json_strings is a no-op on the corrupted record
  keys per message:  [['role','content'], ['role','content'], ['role','content'],
                      [' role','content'], ['role','content']]

TEST2 (realistic newline-in-string repair):
  diff chars introduced: {'\\'}           ← only inserts escaped backslashes
                                             (cannot introduce a leading space inside a key)

TEST3 (full _extract_json_object pipeline):
  parsed equals original?  True           ← pipeline is a faithful pass-through

TEST4 (round-trip json.dumps):
  contains '" role"' after json.dumps?    True   ← serializer preserves key verbatim
```

`_repair_json_strings` is a state-machine that tracks whether the scanner is inside a quoted string and only rewrites `\n`/`\t` → `\\n`/`\\t` inside strings. Inspection + direct tests confirm it cannot introduce whitespace into keys. **Eliminated as a suspect.**

### E4 — Nothing in the Python pipeline mutates key shape

I walked the full chain from Player response to disk:

1. [agents/player.py:101-106](agents/player.py#L101-L106) — `create_agent(...)` with middleware `[MemoryMiddleware, PatchToolCallsMiddleware, AnthropicPromptCachingMiddleware]`. None touch training-example content strings.
2. `PatchToolCallsMiddleware` ([deepagents/middleware/patch_tool_calls.py](deepagents/middleware/patch_tool_calls.py)) — 44 lines; only appends synthetic `ToolMessage` records for dangling tool calls in the state message history. Never mutates content strings.
3. [entrypoint/generation_loop.py:247-326](entrypoint/generation_loop.py#L247) `_extract_player_content` — pulls `content` as string or concatenates text blocks; no character mutations.
4. [entrypoint/generation_loop.py:161-244](entrypoint/generation_loop.py#L161) `_extract_json_object` — 3-try extractor (direct parse, code-fence regex, brace-matching). Each try calls `_repair_json_strings` then `json.loads`. Output is either the repaired string or an error.
5. [entrypoint/generation_loop.py:756-763](entrypoint/generation_loop.py#L756) — pre-Coach format gate: `json.loads(extracted)` + top-level key check. Parsing `" role"` as a key **is valid JSON**, so this gate accepts the malformed record.
6. Coach evaluates content only. No structural key assertion in [prompts/coach_prompts.py](prompts/coach_prompts.py) (searched for `role | structural | messages` — only rubric references).
7. [synthesis/validator.py:192-256](synthesis/validator.py#L192-L256) `validate_post_generation` — checks empty-assistant, `"..."` placeholder, and unclosed `<think>` only. It iterates messages via `msg.get("role", "")` and `msg.get("content", "")`, which silently returns defaults for misspelled keys. **Does not enforce key shape.**
8. [entrypoint/generation_loop.py:1076](entrypoint/generation_loop.py#L1076) — `write_tool.invoke({"example_json": example_json})`.
9. [src/tools/write_output.py:108-140](src/tools/write_output.py#L108-L140) — step 3 checks `first_msg.get("role") != "system"` (position 0 only); step 6b iterates with `msg.get("role") == "assistant"` (silently skips messages with misspelled `role`).
10. [src/tools/write_output.py:189-191](src/tools/write_output.py#L189-L191) — `json.dumps(data, ensure_ascii=False)` writes the dict verbatim; key `" role"` is preserved.

**None of steps 1-10 can introduce, and none can detect, a key like `" role"`.** This is a validation gap, not a mutation bug.

### E5 — Rejection log corroborates: no structural-key checks ever fired

```
output_backup_run1/rejected.jsonl:
  612 target rejections
  format-gate hits across all targets: 927 (all are 'player_output_not_json',
    i.e. Player returned prose instead of JSON)
  occurrences of '" role"' substring in entire rejected.jsonl: 0
  write_error messages mentioning 'role' or 'invalid keys': 0
```

In 927 format-gate rejections, none were triggered by a malformed key — they were all "Player returned prose not JSON". Confirms the gate only catches invalid JSON, not structurally wrong JSON. Confirms the 2 defective records were never caught by any existing gate.

### E6 — Prompt contains no contaminating example

[domains/gcse-english-tutor/GOAL.md:103-121](domains/gcse-english-tutor/GOAL.md#L103-L121) Output Schema:

```json
{
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  ...
}
```

Clean. No whitespace artefacts. No source of contamination in the prompt builder either ([prompts/player_prompts.py](prompts/player_prompts.py)).

## Sequence Diagram — Validated Data Flow

The following Mermaid sequence diagram shows the exact path a training example takes, with the validation checks each actor performs. It encodes what I verified in E1–E6.

```mermaid
sequenceDiagram
    autonumber
    participant Orch as Orchestrator<br/>(generation_loop)
    participant Player as Player Agent<br/>(LLM)
    participant Extract as _extract_json_object<br/>+ _repair_json_strings
    participant FmtGate as Pre-Coach Format Gate
    participant Coach as Coach Agent<br/>(LLM)
    participant Post as validate_post_generation
    participant Write as write_output tool
    participant Disk as train.jsonl

    Orch->>Player: player_input (target + RAG context + Coach feedback)
    Player-->>Orch: raw text content<br/>(may contain '{" role": "user", ...}' ⚠)
    Orch->>Extract: _extract_player_content()<br/>then _extract_json_object()
    Note over Extract: E3/E4: faithful pass-through;<br/>cannot introduce OR detect<br/>leading-space keys
    Extract-->>Orch: valid JSON string (bug preserved)
    Orch->>FmtGate: json.loads + check top-level keys
    Note over FmtGate: Accepts any valid JSON<br/>with 'messages'+'metadata'.<br/>Key structure NOT checked ⚠
    FmtGate-->>Orch: OK (format gate passed)
    Orch->>Coach: evaluate(player_content)
    Note over Coach: Rubric = content quality only.<br/>Does not assert msg.keys() shape ⚠
    Coach-->>Orch: CoachVerdict(accept, score)
    Orch->>Post: validate_post_generation(example_json)
    Note over Post: Checks empty-assistant,<br/>"..." placeholder,<br/>unclosed <think>.<br/>Uses msg.get("role","") → silently<br/>skips misspelled role keys ⚠
    Post-->>Orch: is_valid=True
    Orch->>Write: write_tool.invoke({"example_json": s})
    Note over Write: Step 3: messages[0].get("role")=="system"<br/>✅ (msg[0] is fine; bug is at msg[3])<br/><br/>Step 6b: iterates assistant messages<br/>using .get("role")=="assistant"<br/>→ silently skips msg[3] ⚠<br/><br/>No key-shape validation anywhere
    Write->>Disk: json.dumps(data, ensure_ascii=False) + "\n"
    Note over Disk: " role" key written verbatim 💥
    Write-->>Orch: "Written to train.jsonl (example #N)"
```

**Where the fix goes**: a new gate inside `write_output`, between step 2 (`messages` is a non-empty array) and step 3 (`messages[0].role == "system"`), that iterates every message and enforces the key set deterministically. Rejection flows back via the existing `write_error` path ([entrypoint/generation_loop.py:1076-1108](entrypoint/generation_loop.py#L1076-L1108)), which triggers a Player revision with feedback — no throughput loss.

## Findings

### F1 — `write_output` never validates middle-message key sets  (HIGH, confirmed)

[src/tools/write_output.py:93-189](src/tools/write_output.py#L93-L189)

Only two message inspections exist:

- Line 109: `first_msg.get("role") != "system"` — position 0 only.
- Line 134-140: `msg.get("role") == "assistant"` — silently skips dicts with misspelled `role`.

A dict like `{" role": "user", "content": "..."}` at any non-first position passes unseen. Step 10's `json.dumps(data)` preserves the key verbatim. **This is the direct cause of the on-disk defect.**

### F2 — Bug originates in Player LLM output; Python code is innocent  (HIGH, confirmed)

Verified through direct tests (E3) and full path walk (E4). No code path can introduce a leading space into a key string. The Player LLM is the source. The defect's multi-turn-only correlation (E2) is consistent with tokenization drift immediately after the `}, {` separator between message objects.

### F3 — `synthesis.validator.TrainingExample` is unused in the write path  (MEDIUM, confirmed)

[synthesis/validator.py:49-139](synthesis/validator.py#L49-L139) defines a fully-specified pydantic model with `role: Literal["system","user","assistant"]`. Pydantic would reject `{" role": "user", ...}` immediately (the `role` field would be marked missing by default config). Grep confirms `TrainingExample` is referenced in tests and in the `synthesis.synthesise` module but **not** in `write_output` or `generation_loop`. The write path reimplements validation with looser semantics.

### F4 — `validate_post_generation` only validates content, not structure  (LOW, confirmed)

[synthesis/validator.py:192-256](synthesis/validator.py#L192-L256). Uses `msg.get("role", "")` on line 222, which silently yields `""` for misspelled keys, hiding the defect rather than catching it.

### F5 — Coach prompt does not evaluate key shape  (LOW, confirmed, and — importantly — should not)

[prompts/coach_prompts.py](prompts/coach_prompts.py) grep for `role|structural|messages` returns only Coach self-description hits. **Adding a structural-key criterion to the Coach is the wrong layer**: LLM-based character counting is unreliable, costs tokens, and would not be a proper gate. Deterministic validation belongs in Python code.

### F6 — `_repair_json_strings` is NOT the culprit  (confirmed empirically)

E3 shows both a no-op pass-through on the corrupted record and a constrained mutation set (`{'\\'}` only) on realistic fixtures. Eliminated.

### F7 — Acceptance criterion "existing train.jsonl not modified" is met by design  (INFO)

No remediation script needed; the training-script stripping workaround handles historical records. Fix is prospective.

## Regression Risk Analysis of Recommended Fix (R1)

### Simulation against the full 1716-record backup

I ran the exact proposed gate logic as a pure-Python simulation against every record in `output_backup_run1/train.jsonl` and counted rejections:

```
Simulation of proposed fix against output_backup_run1/train.jsonl:
  total records:                        1716
  records proposed fix would reject:       2
  sample rejections:
    (1145, "msg[3] keys unexpected=[' role'] missing=['role']")
    (1330, "msg[3] keys unexpected=[' role'] missing=['role']")
```

**Zero false positives on 1716 real production records.** The fix rejects exactly the two known-bad records and nothing else.

### In-run throughput impact estimate

If the gate had been in place during the run:

- 2 records would have been rejected at `write_output` time, each returning an `Error: messages[3] has invalid keys...` string.
- The orchestrator's existing `write_error` handling ([entrypoint/generation_loop.py:1076-1108](entrypoint/generation_loop.py#L1076-L1108)) tracks `write_attempts` up to `config.max_write_attempts` and feeds the error back to the Player as Coach feedback, triggering a revision turn.
- Expected cost: **+2 Player-Coach turns across the entire run** (~1,716 generated records × ~2 turns/record = ~3,432 baseline turns). Throughput impact ≈ 0.06 %.
- Acceptance rate impact: assuming both revisions succeed on second attempt (the Player clearly knows how to emit correct `"role"` keys — it did so for 99.88 % of records), acceptance rate is unchanged.

### Other edge cases considered

1. **Knowledge layer (`rag_index/knowledge.jsonl`)**: verified 172 records, 0 defects, all messages have `{role, content}` keys. Same `write_output` code path, so same gate catches any future knowledge-layer defect with no special-casing.
2. **Empty/missing content**: the new gate requires `"content"` key present; if a message were missing content, it would be caught as `missing=['content']`. Better than current behaviour which silently proceeds to `_find_last_assistant_content` returning an empty string.
3. **Extra fields like `"name"` or `"tool_call_id"`**: some OpenAI chat formats allow extra per-message keys. **Not relevant here** — the domain output schema ([domains/gcse-english-tutor/GOAL.md:103-121](domains/gcse-english-tutor/GOAL.md#L103-L121)) explicitly specifies exactly `{role, content}`. If future domains need additional fields, the allow-set should be made configurable from `metadata_schema`. Out of scope for this fix.
4. **Whitespace after `role`** (e.g., `"role "`): current fix catches this because `set(m.keys()) != {"role", "content"}`.
5. **Uppercase role** (e.g., `"Role"`): caught as unexpected key + missing required key.
6. **Valid role string with outer whitespace** (e.g., `"role": " user"` — value, not key): **not caught by R1**. I checked the backup for this pattern and found 0 occurrences, so this is not a real problem today, but if paranoid, a follow-up can strip-and-validate role values. I recommend **not** adding this now — it's speculative hardening beyond the observed defect.

### Risk of rejecting valid training examples unknown to the simulation

The simulation covers 1716 records that already passed the existing pipeline. To catch hypothetical future valid examples the simulation can't see: because R1 encodes the same contract the domain's `GOAL.md` output schema already specifies (exactly `{role, content}` with `role ∈ {system, user, assistant}`), any record rejected by R1 would also violate the declared contract. The gate enforces what's already required — it does not impose a new constraint.

**Confidence in R1's safety: HIGH.**

## Recommendations

### R1 — Add `_validate_message_structure(messages)` gate in `write_output`  (REQUIRED)

Insert after step 2 (non-empty messages array) and before step 3 (`messages[0].role == "system"`):

```python
_ALLOWED_MESSAGE_KEYS = frozenset({"role", "content"})
_VALID_ROLES = frozenset({"system", "user", "assistant"})

for i, msg in enumerate(messages):
    if not isinstance(msg, dict):
        return f"Error: messages[{i}] is not an object"
    keys = set(msg.keys())
    unexpected = keys - _ALLOWED_MESSAGE_KEYS
    missing = _ALLOWED_MESSAGE_KEYS - keys
    if unexpected or missing:
        return (
            f"Error: messages[{i}] has invalid keys "
            f"(unexpected={sorted(unexpected)}, missing={sorted(missing)})"
        )
    if msg["role"] not in _VALID_ROLES:
        return (
            f"Error: messages[{i}].role invalid value "
            f"{msg['role']!r} (expected: system, user, assistant)"
        )
```

- Place the gate at module top-level (constants) and call inline in `write_output`.
- The existing step 3 check (`first_msg.get("role") != "system"`) remains — it enforces the extra constraint that position 0 is specifically `system`. Simplify its error message to use `messages[0]["role"]` now that the new gate guarantees the key exists.
- The existing step 6b think-tag iteration ([write_output.py:134-140](src/tools/write_output.py#L134-L140)) can be left as-is — the new gate already guarantees every `msg["role"]` is a valid string, so `.get("role") == "assistant"` remains correct but is now redundant; no functional change required.

### R2 — Regression tests in `test_write_output.py`  (REQUIRED)

Add to `TestValidationChain` (following the existing `test_step3_first_message_not_system_rejected` style):

```python
def test_leading_space_in_role_key_rejected(self, write_tool):
    """Regression for TASK-REV-4AA0: ' role' key (leading space) is rejected."""
    example = {
        "messages": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "ok"},
            {" role": "user", "content": "follow"},      # ← bug
            {"role": "assistant", "content": "fin"},
        ],
        "metadata": {"layer": "behaviour", "type": "direct", "text": "macbeth"},
    }
    result = write_tool.invoke(json.dumps(example))
    assert "messages[3]" in result
    assert "invalid keys" in result
    assert " role" in result  # error includes the offending key

def test_trailing_space_in_role_key_rejected(self, write_tool): ...
def test_unexpected_extra_key_rejected(self, write_tool): ...   # e.g., {"role":"user","content":"x","speaker":"alice"}
def test_missing_content_key_rejected(self, write_tool): ...
def test_invalid_role_value_rejected(self, write_tool): ...      # e.g., {"role":"tool","content":"x"}
def test_valid_5_message_conversation_accepted(self, write_tool, output_dir): ...  # happy-path guard
```

Target coverage: all six new branches (unexpected, missing, non-dict, invalid role, plus happy path for both 3-msg and 5-msg conversations). Aligns with the project's `.claude/rules/testing.md` AAA pattern and `test_<method>_<scenario>_<result>` naming.

### R3 — Do NOT modify Player or Coach prompts  (RECOMMENDED)

- Player prompt is already explicit about JSON format and the output schema example is clean (E6). Adding "do not include spaces in your JSON keys" is unlikely to eliminate 0.12 % hallucination.
- Coach is an LLM and should not be asked to character-check keys (F5). Deterministic gates belong in code.

### R4 — (Optional, NICE-TO-HAVE, not this task) Delegate to `TrainingExample.model_validate`

Unifying the write path around the existing pydantic model (F3) would give richer validation and collapse duplicated logic. Risks surfacing pre-existing differences between the two validators; changes more than this bug demands. **Recommend filing as a follow-up refactor task (TASK-DKW-003) and NOT including in the fix wave.**

## Decision Matrix

| Option | Effort | Regression Risk | Catches bug? | Notes |
|---|---|---|---|---|
| Do nothing; rely on training-script workaround | 0 | — | ❌ | Other downstream consumers (eval, inference) still break on the 2 records + any future recurrence |
| Harden Player prompt only | Low | Low | ⚠ partial | LLM hallucinates at 0.12 % even with clean prompts |
| Add Coach structural criterion | Low | Medium (LLM unreliability) | ⚠ partial | Wrong layer |
| **R1 + R2: deterministic gate in `write_output`** | **Low** | **Minimal (0 FPs on 1716 records)** | **✅** | **Recommended** |
| R1 + R2 + R4 (full pydantic delegation) | Medium | Higher diff surface | ✅ | Defer to follow-up |

## Implementation Subtasks (for `[I]mplement`)

1. **TASK-DKW-001** — Add `_ALLOWED_MESSAGE_KEYS` + `_VALID_ROLES` constants and `_validate_message_structure` inline gate in [src/tools/write_output.py](src/tools/write_output.py) between step 2 and step 3. Update the step-3 error message to use `messages[0]["role"]` for clarity (the new gate guarantees the key exists). **Do not** alter steps 6b, 7, 8, 9, or 10.
2. **TASK-DKW-002** — Add six regression tests in [src/tools/tests/test_write_output.py::TestValidationChain](src/tools/tests/test_write_output.py#L266). Cover: leading-space-in-key, trailing-space-in-key, unexpected-extra-key, missing-content-key, invalid-role-value, happy-path 5-message conversation. Must preserve existing test pass rate.
3. **TASK-DKW-003** — *(Deferred, optional follow-up — not in this wave.)* Evaluate replacing steps 2-6 with `TrainingExample.model_validate(data)` for unified validation.

DKW-001 and DKW-002 have no file-conflict overlap (source vs. test file) and are parallelisable; both are small enough to land together in a single wave.

## Acceptance Criteria Mapping

| Criterion | Status |
|---|---|
| Root cause identified and documented | ✅ Confirmed via E1-E6; see F1, F2, F6 |
| Fix prevents whitespace in JSON keys in future runs | ✅ R1 simulated against 1716 records, catches both known defects |
| Validation gate added to `write_output` tool | ✅ R1 spec; DKW-001 |
| Existing `output/train.jsonl` not modified | ✅ By design (F7); fix is prospective |
| No regression in generation throughput or acceptance rate | ✅ 0 FPs on 1716 records; estimated impact +2 turns on ~3,432-turn run (0.06 %) |

## Context Used

No Graphiti knowledge graph MCP tools were invoked in this session (availability not established). All findings are grounded in:

- Direct static analysis: [src/tools/write_output.py](src/tools/write_output.py), [entrypoint/generation_loop.py](entrypoint/generation_loop.py), [agents/player.py](agents/player.py), [prompts/player_prompts.py](prompts/player_prompts.py), [prompts/coach_prompts.py](prompts/coach_prompts.py), [synthesis/validator.py](synthesis/validator.py), [domains/gcse-english-tutor/GOAL.md](domains/gcse-english-tutor/GOAL.md).
- Empirical inspection: `output_backup_run1/train.jsonl` (1716 records), `output_backup_pre_rerun/train.jsonl` (1716 records, identical), `output_backup_run1/rejected.jsonl` (612 target rejections, 927 format-gate hits), `output_backup_run1/rag_index/knowledge.jsonl` (172 records).
- Direct runtime tests of `_repair_json_strings` and `_extract_json_object` against three fixtures (corrupted, newline-in-string, round-trip).
- Simulation of R1 against the full 1716-record backup (0 false positives, 2 true positives).
- Verification that `PatchToolCallsMiddleware` ([deepagents/middleware/patch_tool_calls.py](deepagents/middleware/patch_tool_calls.py), 44 lines) does not mutate training-example content.

**No runtime generation logs or Docker logs exist in the repository** (`logs/` dir absent; only `.guardkit/autobuild/*/progress.log` task-tracking logs are present, none from the training run). The rejection log (`rejected.jsonl`) is the highest-fidelity runtime artefact available and was fully analysed (E5).
