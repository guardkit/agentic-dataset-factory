# PO training corpus v2 (`corpora/v2-2026-08-18/`) — repair-pass manifest
## Built 2026-08-18 · v1 (the 08-14 corpus of record) stays the corpus of record until Rich accepts v2

## What v2 is

A file-for-file repair of the 323-row v1 corpus (`corpora/harvest/train_harvest.jsonl`,
`corpora/trace-export/po_player_filtered.jsonl`, `corpora/synthetic/train_synthetic.jsonl`) so that
**every PO-JSON row parses through the REAL serving parser** (specialist-agent
`ProductOwnerOutputHandler.parse` for roadmaps; `handler._extract_json` → `truncate_overlong_quotes` →
`EnrichmentBatch.model_validate` for extract Phase B — the fence-tolerant Phase-B path being landed by the
sibling lane tonight, so fenced Phase-B rows stay fenced) and greenfield rows teach the deployed
`request:<verbatim brief fragment>` grounding convention. v1 was 17% serve-valid (harvest 6/13 under
bare Phase-B loads, synthetic 22/217, trace PO-JSON 15/17). Edits were the smallest possible: deterministic
where possible, teacher-assisted only where a human sentence or a brief fragment was needed, every teacher
edit mechanically verified. v1 files are byte-identical (sha256 below); v2 lives beside them, gitignored,
host-local, with a verified off-box copy on `spark-fcf6:~/factory-corpora/2026-08-18-po-corpus/corpora-v2/`.

Baseline reproduced by the harness before any edit (same harness re-run on v2 afterwards):
harvest full 6/6 pass, harvest Phase-B 0/7 bare `json.loads` / 7/7 fence-tolerant; synthetic 22/217;
trace PO-JSON 15/17 loadable (18 with the broken-JSON row).

## Counts per component / mode, before → after

| Component | v1 rows | v2 train rows | dropped | quarantined | needs_review | note |
|---|---:|---:|---:|---:|---:|---|
| harvest (`train_harvest.jsonl`) | 13 (extract:full 6, extract:b 7) | 13 (6 + 7) | 0 | 0 | 0 | untouched apart from `metadata.repairs=[]` + `metadata.corpus_version` |
| trace-export (`po_player_filtered.jsonl`) | 93 (feature-spec 39, feature-plan 34, greenfield 11, idea 4, scope 2, evolve 1, other 2) | 84 (feature-spec 39, feature-plan 31, greenfield 8, idea 3, scope 2, evolve 1) — of which 14 PO-JSON + 70 file-bundle rows passed through unchanged | 6 | 3 | 0 | only `completion` edited (2 rows); prompt/mask fields untouched |
| synthetic (`train_synthetic.jsonl`) | 217 (idea 44, greenfield 42, evolve 46, impact 43, scope 42) | 215 (idea 44, greenfield 42, evolve 46, impact 41, scope 42) | 1 | 0 | 1 | 197 rows carry ≥1 repair; 18 rows byte-identical assistant content |
| **total** | **323** | **312** | **7** | **3** | **1** | 312 + 7 + 3 + 1 = 323 |

## Serve-validity (the REAL serving parser, run over the written v2 files)

| Set | pass |
|---|---|
| harvest roadmap (extract full) | **6/6** |
| harvest Phase-B (fence-tolerant path) | **7/7** (bare `json.loads` still 0/7 — they stay fenced by design) |
| synthetic roadmap | **215/215** |
| trace PO-JSON | **14/14** |
| trace file-bundle rows (not PO JSON) | 70 passed through unchanged, not parsed |
| **PO-JSON rows in the v2 train files** | **242/242** |

The one synthetic row that still failed (line 82, impact) is in `needs_review.jsonl`, not in train.

## Repairs applied (per kind; full per-row log in `repairs.jsonl`, 701 entries)

| Kind | Count | What |
|---|---:|---|
| `desc_2sent` (teacher) | 523 features / 189 rows | one-sentence feature description → original sentence verbatim + ONE teacher sentence; written to BOTH `epics[].features[]` and `feature_spec_inputs[]` (593/593 pairs identical after) |
| `request_ref` (teacher) | 125 features | greenfield feature `source_documents = ["request:<4–14-word phrase verbatim from the brief>"]`, both places |
| `request_ref_bare` | 8 features | fallback bare token `request` after 2 failed attempts (model returned 2-word phrases; rule requires 3–20). Legal to prompt/Coach/gate, weakest |
| `empty_epic_dropped` | 24 rows (evolve 10, impact 14) | zero-feature epics removed — read 4 (lines 4, 30, 116, 173): they are the brief's existing untouched epics; `feature_spec_inputs` already listed only populated features |
| `add_empty_key` | 13 | synthetic lines 62, 76: missing `depends_on`/`suggested_context_files` (76 also `source_documents`) = `[]` |
| `wrap_list` | 6 | synthetic line 64 `acceptance_criteria` str→[str] (4 = features F1, F2 in both epics[] and feature_spec_inputs[]); trace lines 52, 69 `constraints_and_dependencies` str→[str] |
| `fsi_sync` | 1 | synthetic line 96: epic feature F-A1 absent from `feature_spec_inputs` — copied in (no invention) |
| `fsi_extra_unfixed` | 1 | synthetic line 82: `feature_spec_inputs` carries F-SS1 with no parent epic — NOT repaired (would need an invented epic) → needs_review |
| trace roadmap `coverage_score` | 0 | `ProductRoadmap.coverage_score` is `float | None = None` in types.py — optional, left as-is |
| greenfield epic/roadmap-level `source_documents` / `coverage_score` | 0 | already `[]` / `null` on all 42 rows — asserted, nothing to change |

Idea rows: `source_documents` left empty (deployed idea convention). Trace greenfield survivors (lines 20, 27,
29, 34, 45, 59, 81, 82) already carry `request:` refs — untouched.

## Dropped (`dropped.jsonl`, 7) and quarantined (`quarantine_filename_fabrication.jsonl`, 3)

Trace (0-based idx / 1-based line): idx 7/line 8 prompt-completion mismatch (architect Coach feedback answered
with a feature-plan bundle); idx 13/line 14 broken JSON (invalid control char); idx 23/line 24 and idx 42/line 43
dash-degenerate (197,869 and 251,013 `-` chars); idx 24/line 25 broken JSON (invalid `\escape`, a feature_yaml
object); idx 92/line 93 hallucinated tool transcript (`<call:read_product_docs(...)>`). Synthetic line 127:
literal ``` inside a JSON string defeats serving's non-greedy fence regex.
Quarantine (never-train): trace lines 3, 67, 71 — greenfield rows citing the filename `problem-statement.md`
at feature level (deployed convention: `request:` refs only; a filename in greenfield is fabrication).

## Teacher pass (the ONLY model used)

Seat: `http://promaxgb10-41b1:9000/v1/chat/completions`, model alias `product-owner-agent` → served
`qwen36-workhorse` (Qwen3.6-35B-A3B), `chat_template_kwargs.enable_thinking=false`, temperature 0.2,
max_tokens 200 (pass 1) / 60 (pass 2), strictly sequential. Probe: content `ready`, `reasoning_content` null —
**thinking was off**; across all 670 calls `reasoning_content` was empty (0 fallbacks to it).

| Pass | Targets | Calls | Accepted | Rate | Mean s/call | Wall |
|---|---:|---:|---:|---:|---:|---:|
| 1 descriptions (`desc_2sent`) | 523 | 527 (2 wasted on an over-broad first draft of the `I ` rule that matched "AI ", re-run) | 523 targets (521 attempt 1 same-first-sentence, 2 attempt 2 append-only) | 100% of targets; 523/527 calls | 0.98 | 395 s + 101 s |
| 2 greenfield refs (`request_ref`) | 133 | 143 | 125 verbatim (123 attempt 1, 2 attempt 2) + 8 bare-token | 94% verbatim | 0.36 | 51 s |
| total | 656 | 670 | | | | ≈ 9 min |

Accept rules, mechanically enforced per call (`teacher_calls.jsonl` holds every input/output/verdict):
pass 1 — original sentence is a whitespace-normalised prefix; exactly 2 sentences by the SERVING regex
`[.!?]\s+|[.!?]$` (stricter than the ≥2 the lane allowed); ≤90 words; no newline/markdown/JSON chars;
no first-person `I ` / `As an AI`. Pass 2 — phrase is a whitespace-normalised substring of the brief and 3–20 words.

**Honest note:** the Coach did NOT re-review the teacher-edited sentences or refs — only the serving parser and the
mechanical accept rules above did. Spot-reads show most added sentences are acceptance-relevant, some are
restatements of the first sentence. `no new product facts` was instructed, not verified.

## Gates on the v2 train files

Exam-leakage: 0 hits (`filter_trace_export.LEAKAGE_TERMS` — finproxy, roundroute, homestretch, kiln firing/-firing,
member(-)directory(-)search, po-held-0 — the frozen fleet-evals task identifiers, case-insensitive over the whole
row). Duplicate assistant/completion contents: 0. Credential-pattern scan (sk-/AKIA/ghp_/xox/PEM/Bearer/JWT/
api_key=…): 0 hits. Structure: 228/228 sharegpt rows are `<think>…</think>` + ONE ```json fence + nothing after,
think blocks byte-identical to v1, non-assistant messages untouched, metadata untouched except new
`metadata.repairs` (list of kinds) + `metadata.corpus_version = "v2-2026-08-18"`. Trace rows: every field except
`completion` byte-identical to v1.

## Files (`corpora/v2-2026-08-18/`, sha256 in `RECEIPT.json`)

`train_harvest.jsonl` (13) · `po_player_filtered.jsonl` (84) · `train_synthetic.jsonl` (215) · `repairs.jsonl` (701)
· `dropped.jsonl` (7) · `quarantine_filename_fabrication.jsonl` (3) · `needs_review.jsonl` (1) ·
`teacher_calls.jsonl` (670) · `RECEIPT.json`. Off-box copy: `spark-fcf6:~/factory-corpora/2026-08-18-po-corpus/corpora-v2/`,
sha256 verified identical on both sides for all 9 files.

v1 sha256 (unchanged): harvest `c03fee06…f7178`, trace `dee766fb…af34ed`, synthetic `f0669635…9d5f`.
v2 train sha256: harvest `82379547…be3c0`, trace `fff2c1a6…d6ae`, synthetic `ae5d5c47…2090`.

## Still owed / not done here

- Line 82 (synthetic, impact) needs a human decision (orphan feature F-SS1 needs an epic or removal).
- The 8 bare-token `request` refs are legal but weakest; a human could pick the 2-word phrases.
- ADF loop fix still owed: `write_output` drops Coach-accepted rows on an invalid `metadata.topic` (41 lost 08-13/14).
- GOAL.md still says greenfield `source_documents` "MUST be empty at every level" — right for idea, wrong for
  greenfield (deployed prompt requires feature-level `request:` refs). Not edited by this lane.
- v2 was not Coach-re-reviewed and was not run against the frozen exam; v1 remains the corpus of record.
