# Implementation Guide — gemma4-moe-switch

## Source

Generated from [/task-review TASK-REV-G4MOE → I]mplement](../TASK-REV-G4MOE-review-gemma4-moe-vs-dense-choice.md). Full review with benchmark evidence, option matrix, and sunk-cost analysis: [.claude/reviews/TASK-REV-G4MOE-review-report.md](../../../.claude/reviews/TASK-REV-G4MOE-review-report.md).

## Problem (1-line)

On GB10's 273 GB/s memory bus, 31B Dense is bandwidth-capped at ~7 tok/s (unusable for interactive tutoring), while 26B A4B MoE runs at 52 tok/s with a <1 pt AIME quality delta.

## Fix (1-line)

Switch primary fine-tune to `unsloth/Gemma-4-26B-A4B-it` with `load_in_16bit=True`, preserve the existing 31B Dense script and artifacts as an offline quality tier.

## Confidence

**HIGH.** Bandwidth math is mechanical. Published quality gap is <1 pt AIME. Unsloth first-party support is documented. The in-practice GCSE quality is checked informally by the TASK-G4MOE-004 Step 7 smoke test — same bar the Dense run had to clear. Dense artifacts stay archived as a fallback if subtle regressions surface in real use later.

## Execution Strategy

### Wave 1 — Script + docs prep (parallelisable, 3 tasks)

These three tasks touch different files and have no overlap. They can be done in parallel in separate Conductor workspaces, or serially in one worktree. There is no technical dependency between them — the MoE script doesn't import from the Dense script, and the doc update doesn't require the script changes to have landed.

| Task | File | Mode | Workspace | Depends on |
|---|---|---|---|---|
| [TASK-G4MOE-001](TASK-G4MOE-001-split-training-script.md) | [train_gemma4.py](../../../docs/research/train_gemma4.py) → `train_gemma4_dense.py` | direct | `gemma4-moe-switch-wave1-1` | — |
| [TASK-G4MOE-002](TASK-G4MOE-002-moe-script-config.md) | `train_gemma4_moe.py` (new) | task-work | `gemma4-moe-switch-wave1-2` | G4MOE-001 (file-rename ordering only) |
| [TASK-G4MOE-003](TASK-G4MOE-003-update-getting-started-doc.md) | [fine-tuning-getting-started.md](../../../docs/research/fine-tuning-getting-started.md) | direct | `gemma4-moe-switch-wave1-3` | — |

**Recommended flow (serial in one worktree)**: G4MOE-001 → G4MOE-002 → G4MOE-003. The rename in G4MOE-001 is one-shot; once done, G4MOE-002 creates the sibling file; G4MOE-003 is doc-only and can run any time.

**Parallel option**: G4MOE-001 and G4MOE-003 can run concurrently in different workspaces. G4MOE-002 should wait until G4MOE-001 lands so the new MoE script starts from a freshly-named `train_gemma4_dense.py` baseline rather than needing a subsequent rebase.

### Wave 2 — Training execution (sequential, 1 task, blocks on Wave 1)

| Task | Hardware | Mode | Depends on |
|---|---|---|---|
| [TASK-G4MOE-004](TASK-G4MOE-004-moe-training-run.md) | GB10 (unattended) | manual | G4MOE-002 |

This is a real training run on GB10 — not codemod work. Allow 3–6 hours wall-clock after a 15-minute `--max-steps 30` sanity check passes. The Step 7 smoke-test at the end of this task (send a GCSE Shakespeare prompt, inspect the response) is the quality check — same informal gate the Dense run went through. No separate eval wave.

## Out of Scope

Explicitly excluded from this feature:

1. **Deleting the 31B Dense artifacts** — archived as a fallback, not actively maintained.
2. **Formal eval harness** — the Dense run didn't get one; the MoE run doesn't need one either. Smoke-test in TASK-G4MOE-004 Step 7 is the gate.
3. **Migrating to a different inference framework** — vLLM + Unsloth stack stays.
4. **Tensor parallelism across multiple Sparks** — single-Spark MoE already exceeds the latency target.
5. **Third-party NVFP4 quantised checkpoints** — review §5 explicitly excludes them after the forum failure analysis.
6. **Deploying the MoE behind the study-tutor UI** — follow-up feature after TASK-G4MOE-004 smoke-test passes.

## Validation Checklist

After all waves land:

- [ ] `train_gemma4_dense.py` exists and is byte-identical (modulo filename) to the pre-rename `train_gemma4.py`
- [ ] `train_gemma4_moe.py` exists with `load_in_16bit=True`, `load_in_4bit=False`, `model_name="unsloth/Gemma-4-26B-A4B-it"`
- [ ] `train_gemma4_moe.py --max-steps 30` runs cleanly on GB10 with loss in 1–3 range
- [ ] Full MoE training run completes and produces LoRA adapter, merged-16bit, and GGUF outputs under `~/fine-tuning/output/gcse-tutor-gemma4-26b-moe/`
- [ ] Inference smoke test on merged-16bit: produces coherent GCSE-tone response with `<think>` block, feels fluent in real time
- [ ] `fine-tuning-getting-started.md` rationale section references the MoE benchmark numbers and the review report

## Expected Diff Surface

- `docs/research/train_gemma4.py` → renamed to `train_gemma4_dense.py` (0 byte content change)
- `docs/research/train_gemma4_moe.py`: new file, ~365 lines (essentially a copy of dense with ~10 lines different in `DEFAULTS` and the loader call)
- `docs/research/fine-tuning-getting-started.md`: ~60 lines changed (rationale rewrite, memory numbers, vLLM flags, troubleshooting updates)

No source-tree changes under `src/` or `tests/`. This feature lives entirely under `docs/research/`.

## Risk Register (copied from review §9 for quick reference)

| Risk | P | I | Mitigation |
|---|---|---|---|
| First MoE fine-tune hits an Unsloth bug | M | M | Pin Unsloth version; sanity-run `--max-steps 30` before full run |
| MoE quality regresses on real tutor use | L–M | M | Step 7 smoke-test catches obvious failures; Dense artifacts archived as fallback if subtle regressions surface later |
| Training hang (known Spark long-run issue) | M | L | Same workaround as Dense: `--save-steps 100` + `--resume` |
| `--moe-backend marlin` vLLM flag drifts | L | L | Pin `vllm/vllm-openai:gemma4-cu130` tag explicitly |
