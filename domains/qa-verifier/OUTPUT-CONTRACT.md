# QAV Row Contract — input bundle, label, provenance, manifest

**Status:** WS2-B11 spec half, 2026-07-07. This is the WS4-facing contract: the row shape the
training pipeline consumes and the manifest format the handover carries.
**Pinned by:** `ws2-qa-verifier-and-last-mile-scope-design-2026-07-07.md` §5 (the row shape is
scope-pinned; every realization detail below that goes beyond the scope's words carries a dated
note — none change the pinned fields).

## 1. Row envelope

One row = one JSON object per line (`.jsonl`), ShareGPT-style envelope matching the factory's
existing `train.jsonl` conventions (PO/coach domains):

```json
{
  "messages": [
    {"role": "system",    "content": "<the GOAL.md system prompt>"},
    {"role": "user",      "content": "<the serialized evidence input — §2>"},
    {"role": "assistant", "content": "<think>…reasoning…</think>\n\n```json\n<verdict object — §3>\n```"}
  ],
  "metadata": { … §4 … }
}
```

Chat template at train time: `gemma-4` (not `gemma-4-thinking`). The verdict object inside the
assistant fence is **the label**; the `<think>` block is training-time scaffold authored by the
teacher against the fixed label (GOAL.md generation guidelines).

## 2. Input contract (user message)

The **B-min bundle**: `CoachEvidenceBundle.to_dict()` serialized exactly as
`coach_turn_N.json` records it —
`guardkit/guardkit/orchestrator/quality_gates/coach_evidence.py:172-381`, pinned at guardkit
`41a0ebe457` (file last touched `5ad48fcf`).

> **Dated note (2026-07-07) — field-list realization.** Scope §5 names the bundle fields
> elliptically ("honesty, gathering_status, gathering_error, quality_gates, coverage_details,
> plan_audit, bdd, bdd_authoring_sweep fields"). This contract realizes that as the **complete
> dataclass field set** at the pinned sha — the same additive-realization move B1's F3
> `format_version` note made. No field is invented; the full set is what `to_dict()` emits.
> (The WS4 doc cites the range as `172–420`; at the pinned sha the dataclass ends at line 381 —
> same object, stale end-line in the WS4 doc.)

> **Dated note (2026-07-08) — code half: bundle filename + GN-3 verbatim survival.** This
> section says the bundle is "serialized exactly as `coach_turn_N.json` records it." On disk
> the serialized `CoachEvidenceBundle.to_dict()` is **`coach_evidence_turn_N.json`** —
> `coach_turn_N.json` is the Coach's *decision* record (keys `decision`/`criteria_verification`/
> `rationale`), NOT the evidence bundle. The code half (`src/qav/harvest.py`,
> `gold_negatives.py`) reads `coach_evidence_turn_N.json`; the spec's `coach_turn_N.json`
> naming is retained above as the pinned words with this correction noted rather than silently
> edited. **On-disk survival probe (`qav.gold_negatives.probe_survival`, run 2026-07-08):
> GN-3 (10AC/TASK-QAV-005) survives VERBATIM** as
> `guardkit/.guardkit/worktrees/FEAT-10AC/.guardkit/autobuild/TASK-QAV-005/coach_evidence_turn_2.json`
> (older schema — `behavioural_oracle` present as null, pre-L2/L3 stub_scan/coverage/
> bdd_authoring_sweep — additively compatible per the bundle-schema drift rule; its
> `bundle_schema_sha` is stamped `888906f2`, not `41a0ebe457`). GN-1/GN-2 source dirs hold only
> `progress.log`; GN-4 is a fix commit — those three reconstruct from the SPEC tables. Corpus
> counts on disk 2026-07-08: guardkit 661 + study-tutor 104 + forge 139 = 904 `coach_turn`
> records; `coach_evidence_turn_*` bundles are the harvest input.

Complete field set (all serialized; `None` means what the bundle contract says it means —
read against `gathering_status`):

| Field | Type at serialization |
|---|---|
| `honesty` | dict (HonestyVerification: resolved_paths, should_fix_count, discrepancies…) |
| `gathering_status` | `"complete" \| "partial_exception" \| …` (GatheringStatus) |
| `gathering_error` | str \| null |
| `quality_gates` | dict \| null (tests / coverage / arch_review / plan_audit aggregate) |
| `coverage_details` | dict \| null |
| `plan_audit` | dict \| null |
| `bdd` | dict \| null (scenarios_attempted/failed/passed/pending, failures, feature_files) |
| `bdd_authoring_sweep` | dict \| null (carries sweep-only `scenarios_undefined`) |
| `arch_review` | dict \| null |
| `tests` | dict \| null |
| `wiring` | dict \| null (UNWIRED_PATH analysis) |
| `mocked_seam` | dict \| null |
| `spec_gap` | dict \| null |
| `stub_scan` | dict \| null (L2 anti-stub) |
| `coverage` | dict \| null (L3) |
| `behavioural_oracle` | dict \| null (L4) |
| `independent_tests` | dict \| null (IndependentTestResult) |
| `independent_test_classification` | dict \| null (failure_class/confidence/raw_output_excerpt) |
| `requirements` | dict \| null |
| `runtime_parity` | dict \| null |
| `evidence_repo_tests` | list (EvidenceTestResult dicts; empty when no sibling repos) |
| `severity_recommendations` | list of {recommendation, rule} |
| `advisory_issues` | list |
| `task_type` | str \| null |
| `profile_name` | str \| null |

**User-message layout:**

```
## Evidence bundle
```json
{ …CoachEvidenceBundle.to_dict()… }
```

## Live-gate results
(none available)
```

The **live-gate slot is reserved now** (scope §5: "the L5 layer should learn to read both").
Phase 1 rows all carry `(none available)` — the runner (WS2 B3/B4) does not exist yet; the
envelope extends this section additively when it lands, no row-shape change. The literal
`(none available)` marker is fixed so Phase-2 rows differ only by real content in that section.

**Bundle-schema drift rule:** the bundle is guardkit's dataclass and will grow (live-gate
fields, WS3 seam checks). Rows record the guardkit sha they were serialized under
(`metadata.bundle_schema_sha`); a training manifest may mix shas ONLY when the newer sha is
additive over the older (new fields only) — verified by the manifest validation step.

## 3. Label contract (assistant fenced JSON)

Exactly the scope-§5 pinned shape — three keys, nothing else in the fenced object:

```json
{
  "verdict": "approve" | "reject",
  "findings": [
    {"class": "DC-03", "locus": "cli/main.py:serve — MCPAdapter(...) call site passes retired kwargs"}
  ],
  "ground_truth_source": "coach_correct" | "operator_caught" | "merge_review_caught" | "live_gate_caught" | "seeded"
}
```

- `verdict: approve` ⇒ `findings: []`.
- `verdict: reject` ⇒ ≥1 finding; `class` is a DC id from the documented taxonomy (Phase-1
  admissible set: DC-03, DC-05, DC-08, DC-12, DC-14 — PLAN §3 dated note); `locus` is a free-text
  anchor naming file/symbol/bundle-field where the judgment lands.
- `ground_truth_source` per scope §5's enum, verbatim. Seeded rows: `"seeded"`. Real historical
  rows: whichever layer actually caught (or confirmed) the outcome.
- Rationale prose lives ONLY in `<think>` — the fenced object stays the pinned trio, so the
  serving-time parse contract is trivial and the label never smuggles unpinned fields.

## 4. Row metadata (not shown to the model)

```json
{
  "row_id": "qav-<sha256[:16] of user message content>",
  "provenance": {"repo": "study-tutor", "feature": "FEAT-SMP-003", "task": "TASK-SMP3-06",
                  "run": "<run id or 'reconstructed'>", "sha": "<commit of the evidence record>"},
  "split": "train" | "eval_qav",
  "generation_mode": "seeded_code" | "seeded_bundle" | "harvest" | "gold_negative",
  "dc_class": "DC-03" | … | null,
  "bundle_schema_sha": "41a0ebe457",
  "reconstruction_fidelity": "verbatim" | "reconstructed" | null,
  "injection_recipe": "<recipe id from PLAN §3, seeded rows only>"
}
```

`provenance` is the scope-pinned quintet, verbatim keys. `row_id` is content-addressed on the
user message — this is what the contamination check hashes. `split: eval_qav` rows are named at
creation and never enter a training manifest (PLAN §6).

## 5. Handover manifest format (WS4 consumes this)

`domains/qa-verifier/manifests/qav-phase1-train.manifest.json` (and a sibling
`qav-phase1-eval.manifest.json` owned by B12's process):

```json
{
  "manifest_version": 1,
  "dataset_id": "qav-phase1-train-v1",
  "created": "<date>",
  "factory_sha": "<agentic-dataset-factory commit>",
  "bundle_schema_shas": ["41a0ebe457"],
  "format": {"envelope": "sharegpt-jsonl", "chat_template": "gemma-4",
              "row_contract": "domains/qa-verifier/OUTPUT-CONTRACT.md@<sha>"},
  "files": [{"path": "output/qa-verifier/train.jsonl", "rows": 0, "sha256": "…"}],
  "counts": {
    "by_verdict": {"approve": 0, "reject": 0},
    "by_dc_class": {"DC-03": 0, "DC-05": 0, "DC-08": 0, "DC-12": 0, "DC-14": 0},
    "by_ground_truth_source": {"coach_correct": 0, "operator_caught": 0,
                                "merge_review_caught": 0, "live_gate_caught": 0, "seeded": 0},
    "by_generation_mode": {"seeded_code": 0, "seeded_bundle": 0, "harvest": 0}
  },
  "balance_report": {"approve_share": 0.0, "tolerance": 0.10,
                      "ugly_green_share_of_approves": 0.0, "plan_ref": "PLAN §5"},
  "contamination_check": {"status": "pass", "method": "row_id set intersection vs eval manifest",
                           "eval_manifest": "qav-phase1-eval.manifest.json", "intersection": 0},
  "visibility": "private (DF-008)",
  "consumer": "WS4 training pipeline (WS4-S8 QAV scope doc; gate = FEAT-EVAL-QAV)"
}
```

**Validation against scope-design §5 (2026-07-07):** the manifest carries every element §5
requires of the handover — row shape (via `row_contract` pointer), ground-truth-source
accounting, provenance traceability (per-row, summarized by counts), the seeded/real split,
two-sided balance evidence, and the hold-out contamination proof. Deviations from §5's words:
**none** — everything beyond §5 (`bundle_schema_shas`, `balance_report`, `contamination_check`)
is additive bookkeeping the B11/B12 guardrails themselves demand, noted here rather than
silently added.
