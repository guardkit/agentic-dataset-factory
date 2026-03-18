# synthesis — Phase 1 script user guide

Generates GCSE English tutor training examples via the Claude API and writes them
to JSONL files ready for fine-tuning and RAG seeding.

---

## Prerequisites

- Python 3.11+
- Anthropic API key
- Generation plan YAML (see [Generation plan format](#generation-plan-format))

```bash
pip install -e .                          # install from repo root
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## Quick start

```bash
python -m synthesis.synthesise
```

The script reads `domains/gcse-english-tutor/generation-plan.yaml` by default and
writes output to `output/`.  Console output is newline-delimited JSON:

```
{"level": "INFO", "message": "{\"event\": \"progress\", \"total_attempted\": 10, \"accepted\": 9, \"rejected\": 1, \"reasoning_pct\": 0.7778, \"direct_pct\": 0.2222}"}
{"level": "INFO", "message": "{\"event\": \"complete\", \"total_attempted\": 20, \"accepted\": 18, \"rejected\": 2, \"reasoning_pct\": 0.75, \"direct_pct\": 0.25}"}
```

Progress is logged every 10 targets; a final summary is emitted at completion.

---

## Generation plan format

The plan is a YAML file with a single `generation_targets` list.  Each entry maps
to one API call and one output example.

```yaml
generation_targets:
  - text: macbeth
    topic: character_analysis
    layer: behaviour
    type: reasoning
    grade_target: 6
    ao: [AO1, AO2]

  - text: language_paper_1
    topic: essay_feedback
    layer: behaviour
    type: reasoning
    grade_target: 7

  - text: general
    topic: terminology
    layer: knowledge
    type: direct
```

### Field reference

| Field | Required | Valid values |
|-------|----------|-------------|
| `text` | yes | `macbeth`, `a_christmas_carol`, `an_inspector_calls`, `power_conflict_poetry`, `language_paper_1`, `language_paper_2`, `general`, `unseen_poetry` |
| `topic` | yes | `character_analysis`, `language_analysis`, `structure_analysis`, `essay_feedback`, `exam_technique`, `comparative`, `factual_recall`, `character_knowledge`, `terminology`, `encouragement` |
| `layer` | yes | `behaviour` (→ fine-tuning), `knowledge` (→ RAG) |
| `type` | yes | `reasoning` (includes `<think>` block), `direct` (no `<think>` block) |
| `grade_target` | no | Integer 4–9 |
| `ao` | no | List of `AO1`–`AO6` strings |
| `turns` | no | Integer ≥ 1 (default `1`; `essay_feedback` with `reasoning` auto-generates multi-turn) |

---

## CLI options

```
python -m synthesis.synthesise [--plan-path PATH] [--output-dir DIR]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--plan-path` | `domains/gcse-english-tutor/generation-plan.yaml` | Path to generation plan YAML |
| `--output-dir` | `output` | Directory for output JSONL files and checkpoint |

---

## Output files

| File | Purpose |
|------|---------|
| `output/train.jsonl` | `layer: behaviour` examples — fine-tuning input |
| `output/rag_index/knowledge.jsonl` | `layer: knowledge` examples — RAG seed |
| `output/rejected.jsonl` | Invalid/malformed outputs with reason code |
| `output/.checkpoint.json` | Resumption checkpoint (last completed index) |

---

## Resuming an interrupted run

The script writes `output/.checkpoint.json` after every target, recording the last
completed index plus running accepted/rejected counts.  If the run is interrupted
(Ctrl-C, network drop, rate-limit exhaustion), simply re-run the same command:

```bash
python -m synthesis.synthesise
```

The script skips all targets up to and including the last completed index and
continues from where it left off.

To start fresh, delete the checkpoint file:

```bash
rm output/.checkpoint.json
```

---

## 75/25 reasoning/direct split

Fine-tuning Nemotron 3 Nano for chain-of-thought requires roughly 75% of examples
to include a `<think>…</think>` block (`type: reasoning`) and 25% to be direct
responses (`type: direct`).

The script tracks the running ratio and emits a warning log line if it drifts
beyond ±5% from the 75/25 target:

```
{"level": "WARNING", "message": "Split ratio drifted: 82.0% reasoning / 18.0% direct (target 75/25, tolerance ±5%)"}
```

If the split drifts, adjust the proportion of `type: reasoning` vs `type: direct`
entries in your generation plan.  The warning does not halt the run.

---

## Running tests

```bash
pytest synthesis/tests/ -v
pytest synthesis/tests/ -v --cov=synthesis
```

---

## Common errors

| Error | Likely cause | Fix |
|-------|-------------|-----|
| `FileNotFoundError: generation-plan.yaml` | Plan file missing or wrong path | Create the file or use `--plan-path` to point to the correct location |
| `anthropic.AuthenticationError` | `ANTHROPIC_API_KEY` not set or invalid | `export ANTHROPIC_API_KEY=sk-ant-...` |
| `anthropic.RateLimitError` (logged, not raised) | Exceeded 3 retries with exponential back-off | Wait, then re-run — resumption picks up from the last completed target |
| High `rejected` count in summary | Prompt/model mismatch or schema drift | Inspect `output/rejected.jsonl`; reason codes: `api_error`, `malformed_content`, `reasoning example missing <think>...</think> block`, `direct example contains unexpected <think> block`, `duplicate content detected` |
| `pydantic.ValidationError` on plan load | Invalid field values in YAML | Check field reference table above; `grade_target` must be 4–9, `ao` codes must match `AO[1-6]` |
