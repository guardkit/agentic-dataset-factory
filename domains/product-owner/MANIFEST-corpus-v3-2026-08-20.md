# The PO training corpus v3 — manifest
## Assembled 2026-08-20 (Rich's word, §10 item 1 of `ai-transition/docs/po-lane-state-2026-08-18.md`)
## All six gates PASS · v3 becomes the corpus of record on Rich's acceptance · training remains behind his training word

## The corpus: 255 rows, three components (all under `corpora/v3-2026-08-20/`, gitignored by design)

| Component | File | Rows | sha256 (full) | Provenance |
|---|---|---:|---|---|
| Harvest (real, Feb–May sessions) | `harvest/train_harvest.jsonl` | 13 | `c03fee06e096e45ffb669f8436389c6e2c197cb68d202510d7a5b85ee96f7178` | Unchanged since v1 (`corpora/harvest/`, 08-12). Deterministic answers from real artifacts; teacher wrote only reasoning; 5 gates + leakage discard |
| Trace export (real, July production) | `trace-export/po_player_filtered.jsonl` | 84 | `fff2c1a6dbcead69e099fd560c8f1d98660459086e0c811420b00fad2650d6ae` | The **v2 surviving slice** (`corpora/v2-2026-08-18/`): v1's 93 rows − 6 defective drops − 3 filename-fabrication quarantine; `wrap_list` repairs on 2 rows |
| Synthetic (gpt-oss-120b, 08-19/20 regen) | `synthetic/train_synthetic.jsonl` | 158 | `78e521b9f67698e85305b552d526cfac8fe95d22c7874dabc0b9343d637adc41` | The regeneration under the serving-schema acceptance gate. Byte-identical to `output/train.jsonl` and to the snapshot `corpora/synthetic-mirror/train.regen-final-2026-08-20.jsonl` |

**Total 255.** Copies are byte-identical to their sources (sha256 verified before and after).

Never-train sidecars (stay where they are, not in `v3/`): `corpora/harvest/quarantine_golden_overlap.jsonl` (12) ·
`corpora/v2-2026-08-18/{dropped,quarantine_filename_fabrication,needs_review}.jsonl` ·
`output/rejected.jsonl` (99) · `output/rejected_metadata.jsonl` (11, the topic-fallback sidecar) ·
`output/rag_index/knowledge.jsonl` (43 knowledge rows — **the deferred RAG index, NOT train**) ·
`corpora/synthetic-mirror/` (run-time safety mirror).

## Combined coverage by shape

| Shape | Real (harvest + trace) | Synthetic | Total |
|---|---:|---:|---:|
| feature-spec | 39 | — | 39 |
| feature-plan | 31 | — | 31 |
| idea | 3 | 34 | 37 |
| greenfield | 8 | 28 | 36 |
| scope | 2 | 33 | 35 |
| evolve | 1 | 33 | 34 |
| impact | 0 | 30 | 30 |
| extract (7 phase-b + 6 full) | 13 | — | 13 |
| **total** | **97** | **158** | **255** |

Real:synthetic ≈ 38:62. Every row base-model-neutral (no chat template baked), stamped with
source + generator + provenance.

## Gate results (2026-08-20, every number from a command run on `promaxgb10-41b1`)

Harness: `specialist-agent/.venv/bin/python` with `PYTHONPATH=specialist-agent/src`;
`<think>` stripped via `specialist_agent.orchestrator.think_block.strip_think_blocks`;
roadmaps through `ProductOwnerOutputHandler.parse(..., normalize_greenfield_sources=(mode=="greenfield"))`;
harvest phase-b through `handler._extract_json` → `truncate_overlong_quotes` → `EnrichmentBatch.model_validate`
(serving is fence-tolerant since `e33f157`).

| # | Gate | Result |
|---|---|---|
| 1 | **Serving parse** (REAL parser) | **185 / 185 PO-JSON rows PASS** — harvest 13/13 (7 phase-b + 6 roadmap) · synthetic 158/158 · trace PO-JSON 14/14. The 70 trace **file-bundle** rows (39 feature-spec + 31 feature-plan) are not PO JSON and were counted, not parsed. |
| 2 | **Exam leakage** | **0 hits** across all 255 rows. Terms (case-insensitive, from `filter_trace_export.py` `LEAKAGE_TERMS`, verified against the real `fleet-evals/tasks/po-held-00*/input/` names): `finproxy`, `roundroute`, `homestretch`, `kiln-firing`, `kiln firing`, `member-directory-search`, `member directory search`, `po-held-0`. |
| 3 | **Duplicates** | **0** — 255 distinct sha1 hashes of assistant content (`messages[-1].content`) / `completion` over 255 rows. |
| 4 | **Credential scan** | **0 hits** — openai key, AWS AKID, GitHub PAT, Slack token, PEM private key, bearer token, `key/secret/password/token=…` assignment. |
| 5 | **Per-mode** | synthetic: idea 34 · evolve 33 · scope 33 · impact 30 · greenfield 28 (= 158, matching the expected table exactly) · harvest: extract 13 (phase b 7 / full 6) · trace (`harvest.shape`): feature-spec 39 · feature-plan 31 · greenfield 8 · idea 3 · scope 2 · evolve 1. |
| 6 | **Greenfield grounding** | **28 / 28** synthetic greenfield rows have `request:`-refs on **every** feature. Zero rows short. This is the C3 inversion **closed**: v1 taught empty `source_documents` on all 42 greenfield rows; v3 teaches the deployed convention the untuned seat already follows. |

## Provenance — the regeneration run (`run_logs/po-regen-2026-08-18.log`)

Player `gpt-oss-120b` · Coach `gemma4-coach` (both over the existing `:9000` seat) · 300-target
interleaved curriculum (cap 300 from 1,210) · per-domain output validator
`domains/product-owner/po_schemas.py:validate_assistant_content` — the 08-18 addition that runs the
**vendored serving models** (ProductRoadmap / EpicPlan / EnrichmentBatch by mode+phase) on the
assistant content exactly as `ProductOwnerOutputHandler.parse` would. The v1 corpus was only 17 %
serve-valid under `json.loads` alone; this gate is why v3 is 100 %.

Run shape: start 2026-08-19T05:41:41Z, three resumes (index 13, 33, 45), end 2026-08-20T16:57:10Z.
Knobs raised for the co-tenanted box (`985fdbc`): `llm_timeout` 300→720, `target_timeout` 900→2700 —
llama-swap set-swaps make a Player turn 1.5–3 min including reload.

| Window | Accepted / targets | Rate |
|---|---:|---:|
| Pre-fix, index 0–44 | 19 / 45 | **42.2 %** |
| Post-fix, index 45–299 | 182 / 255 | **71.4 %** |
| — final 50 (250–299) | 38 / 50 | 76.0 % |
| **Whole run** | **201 / 300** | **67.0 %** |

The fix at target 45 is `986ced5` — GOAL.md behaviour guidelines stating the two serving rules the
Player kept failing (every feature description = 2–3 sentences; every epic ≥ 1 feature); of the first
run's 47 refusals, 38 were single-sentence descriptions alone and 9 were empty-feature epics.
Committed 2026-08-19 18:25 BST; the resume from index 45 opened at 18:26 BST.

**201 accepted = 158 train rows + 43 knowledge rows.** The knowledge rows go to
`output/rag_index/knowledge.jsonl` and are the deferred RAG index — *not* training data.
99 rejected (2 Coach refusals, 6 structured-outputs fallback recoveries, 689 turns,
elapsed 84,654 s in the final segment; pipeline tokens 12,029,542).

**The v1 ledgered defect is discharged in behaviour:** `write_output` used to drop Coach-ACCEPTED
rows when the Player invented a `metadata.topic` outside the GOAL enum (41 rows lost in the 08-13/14
run, banked nowhere). This run banked 11 such rows to the topic-fallback sidecar
`output/rejected_metadata.jsonl` instead — each recording field, original value, fallback value,
strategy and destination file. No accepted row vanished on a metadata label.

## Sequence length (measured on v3, both candidate tokenizers, offline HF cache)

`transformers` 5.5.0, `add_special_tokens=False`, prompt+completion concatenated.

| Slice | max tokens (Gemma 4 26B-A4B) | max tokens (Qwen3.8-27B) | rows > 6,144 |
|---|---:|---:|---:|
| harvest (13) | 5,921 | 5,507 | 0 |
| synthetic (158) | 3,731 | 3,657 | 0 |
| trace PO-JSON (14) | 2,327 | — | 0 |
| trace file bundles (70) | 38,204 | 36,785 | **68** |

**A correction to §1.5 of the state doc as it applies to v3:** every **PO-JSON** row fits in 6,144
on both tokenizers (max 5,921 / 5,507), but **68 of the 70 trace file-bundle rows do not** —
38 feature-spec (max 17,079) and 30 feature-plan (max 38,204). A seq-6144 training run therefore
truncates 68 of the 255 rows (27 %) unless the bundles are excluded or a longer sequence is used.
This is a decision the training sitting must take deliberately; it is reported here, not fixed.

## Lineage — v1 → v2 → v3

* **v1 (`MANIFEST-corpus-of-record-2026-08-14.md`, 323 rows)** — 13 harvest + 93 trace + 217 synthetic.
  Stays on disk under `corpora/{harvest,trace-export,synthetic}/`, unaltered. Its recorded weakness:
  only 17 % of its PO-JSON rows parsed the way serving parses them, and all 42 greenfield rows taught
  empty `source_documents` — the inversion against the deployed prompt and Coach.
* **v2 (`MANIFEST-corpus-v2-2026-08-18.md`, 178 rows)** — the *teacher-repair* answer: mechanical +
  teacher repairs to v1's synthetic half (523 `desc_2sent`, 133 `request_ref`), then a fact-check pass
  that moved 134 rows to `needs_review`, leaving 81 synthetic. Its **trace work stands and is carried
  forward whole** (93 → 84: 6 defective rows dropped, 3 quarantined for filename fabrication, 2 repaired).
  Its **synthetic half is superseded**: regeneration under the serving-schema gate beats repair —
  158 rows born valid against 81 repaired-and-surviving.
  v2 stays on disk in full, including `train_synthetic.pre-factcheck-2026-08-18.jsonl`.
* **v3 (this manifest, 255 rows)** — harvest unchanged from v1 · trace = the v2 surviving slice ·
  synthetic = the 08-19/20 regeneration. Nothing was edited during assembly: the three files were
  copied byte-for-byte and then gated.

## Status

**v3 becomes the corpus of record on Rich's acceptance.** v1 and v2 stay on disk as the
lineage record. Nothing has been trained: the next act is §10 item 2 — the Qwen3.8-27B sequence
smoke, then the two-student bake-off (Gemma 4 refreshed `60941ad6` · Qwen3.8-27B) against the
frozen `po-heldout` exam, with the untuned baseline as the bar.

Off-box copy: `spark-fcf6:~/factory-corpora/2026-08-18-po-corpus/corpora-v3/` (sha256 verified both
sides) and the nightly NAS unit `factory-corpora-sync.service`.
