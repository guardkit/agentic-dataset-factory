# TASK-REV: Dataset Generation Key Whitespace Bug

## Context

During the first fine-tuning run of the GCSE English tutor model (Gemma 4 31B on DGX Spark GB10, April 2026), we discovered that the agentic dataset factory is producing training examples with whitespace-corrupted JSON keys in the `messages` array.

## The Bug

Out of 1,736 generated training examples in `output/train.jsonl`, **2 records** (lines 1145 and 1330) contain messages where the `"role"` key has a leading space: `" role"` instead of `"role"`.

Example of the malformed data:
```json
{" role": "user", "content": "Oh, I see what you mean about tracking..."}
```

Should be:
```json
{"role": "user", "content": "Oh, I see what you mean about tracking..."}
```

## Impact

- The training script crashed with `KeyError: 'role'` on first run
- We had to add a workaround (`{k.strip(): v for k, v in msg.items()}`) to the training script to handle this
- While only 2 records were affected in this run, the root cause could produce more corrupted records in future runs
- Other downstream consumers of `train.jsonl` (evaluation scripts, inference pipelines) would also break on these records

## Review Scope

Please investigate and fix the root cause in the agentic dataset factory codebase. The areas to look at:

1. **`tools/write_output.py`** — The tool that writes accepted examples to `output/train.jsonl`. Check whether it's constructing the JSON message dicts with string concatenation or template formatting that could introduce leading whitespace in keys.

2. **`prompts/player_prompts.py`** — The Player agent prompt that instructs the model to generate training examples. If the prompt includes example JSON with inconsistent formatting, the model may reproduce whitespace artifacts in its output.

3. **`agents/player.py`** — The Player agent's output parsing. If it's extracting JSON from the model's response using regex or string slicing rather than proper JSON parsing, whitespace could leak through.

4. **Coach validation (`agents/coach.py` / `prompts/coach_prompts.py`)** — The Coach should be catching malformed output structure. Check whether the Coach's evaluation criteria include structural validation of the message format, or only assess content quality.

## Expected Fix

1. **Root cause fix** — Ensure the `write_output` tool constructs message dicts programmatically (not from raw model text) with validated keys.

2. **Validation gate** — Add a structural validation step in the `write_output` tool that checks all message dict keys match the expected set (`role`, `content`) before writing to JSONL. Reject and log any records with unexpected keys.

3. **Coach prompt update** — If the Coach doesn't already validate output structure, add a structural check to the evaluation criteria so malformed records are caught during generation, not downstream.

## Acceptance Criteria

- [ ] Root cause identified and documented
- [ ] Fix prevents whitespace in JSON keys in future runs
- [ ] Validation gate added to `write_output` tool
- [ ] Existing `output/train.jsonl` is not modified (the training workaround handles it)
- [ ] No regression in generation throughput or acceptance rate
