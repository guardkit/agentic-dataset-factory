---
id: TASK-DOC-A180
title: "Write user guide for the Phase 1 synthesis script"
status: in_review
created: 2026-03-17T00:00:00Z
updated: 2026-03-17T12:00:00Z
priority: normal
tags: [documentation, synthesis, phase1]
task_type: documentation
complexity: 2
dependencies:
  - TASK-GTS-005
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Write user guide for the Phase 1 synthesis script

## Description

Create `synthesis/README.md` — a practical guide for anyone running the Phase 1 synthesis
script. Covers installation, prerequisites, how to configure the generation plan, run the
script, interpret output, resume interrupted runs, and troubleshoot common errors.

Depends on TASK-GTS-005 being complete so the actual CLI interface is known.

## Scope

Create `synthesis/README.md` covering the following sections:

### Prerequisites
- Python 3.11+
- `pip install -e .` from repo root
- `ANTHROPIC_API_KEY` environment variable set
- `domains/gcse-english-tutor/generation-plan.yaml` in place

### Quick start
```bash
export ANTHROPIC_API_KEY=sk-ant-...
python -m synthesis.synthesise
```
Show expected console output (progress log lines, final summary).

### Generation plan format
- Describe the `generation-plan.yaml` structure with a short example (3-4 targets)
- Fields: `text`, `topic`, `grade_target`, `layer`, `type`, optional `ao`
- Valid values for each field (reference the metadata schema in the format spec)

### CLI options
- `--plan-path` — path to generation plan YAML (default: `domains/gcse-english-tutor/generation-plan.yaml`)
- `--output-dir` — output directory (default: `output/`)
- Document all flags from the actual `argparse` setup in `synthesise.py`

### Output files
| File | Purpose |
|------|---------|
| `output/train.jsonl` | Behaviour layer examples — fine-tuning input |
| `output/rag_index/knowledge.jsonl` | Knowledge layer examples — RAG seed |
| `output/rejected.jsonl` | Invalid/malformed outputs with reason code |
| `output/.checkpoint.json` | Resumption checkpoint (last completed index) |

### Resuming an interrupted run
- Explain how the checkpoint file works
- How to resume: just re-run the same command
- How to start fresh: delete `output/.checkpoint.json`

### 75/25 split
- Explain what it is and why it matters for Nemotron 3 Nano
- How the script enforces it (warn at ±5% drift)
- What to do if the split drifts (adjust generation plan)

### Running tests
```bash
pytest synthesis/tests/ -v
pytest synthesis/tests/ -v --cov=synthesis
```

### Common errors
| Error | Likely cause | Fix |
|-------|-------------|-----|
| `FileNotFoundError: generation-plan.yaml` | Plan file missing | Create or point `--plan-path` to correct location |
| `anthropic.AuthenticationError` | API key not set | Export `ANTHROPIC_API_KEY` |
| `anthropic.RateLimitError` (not retrying) | Exceeded 3 retries | Wait and re-run (resumption picks up where it left off) |
| High rejection rate | Prompt/model mismatch | Check `output/rejected.jsonl` reason codes |

## Acceptance Criteria

- [ ] File created at `synthesis/README.md`
- [ ] Quick start section works end-to-end when followed literally
- [ ] All CLI flags documented
- [ ] Output file table accurate
- [ ] Resumption instructions correct
- [ ] Common errors table covers all reason codes from `synthesise.py`
- [ ] No references to Phase 2 internals (agents/, tools/, ChromaDB)

## Implementation Notes

Write this after TASK-GTS-005 is complete so the real CLI interface can be documented
accurately. Keep it under 200 lines — this is a practical how-to, not a spec document.
