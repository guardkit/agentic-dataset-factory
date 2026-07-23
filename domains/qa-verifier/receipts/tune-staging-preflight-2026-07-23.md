# QAV tune — staging pre-flight (NO-GPU, honest checks)

**Date:** 2026-07-23 · **Seat:** S2 STAGING VERIFICATION · **Corpus:** qav-phase1 108 rows
(train 86 / eval_qav 22) · **Factory sha at run:** `9081dcc` · **Suite:** `2512 passed` (baseline held).

Read-only over the corpus on disk. No corpus bytes modified. The exam-side extractor was
**replicated verbatim** (not imported) from
`fleet-evals/harness/run_qav_heldout.py` (`extract_json` + `_first_balanced_object`, lines 142–194).

---

## The serving contract for QAV (stated exactly, per the S2 charge)

Read the two authorities directly:

- **Runner** `fleet-evals/harness/run_qav_heldout.py` — composes `instruction.md` verbatim + the
  bundle, calls the seat once per bundle, and extracts the verdict via **`extract_json`**:
  1. a fenced object first — `re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)`;
  2. else the **first balanced `{…}` object** (string-/escape-aware brace matcher);
  3. else `ValueError` → the raw bytes are written so the grader surfaces the defect honestly.
  The first candidate that `json.loads` to a **dict** wins. The runner never grades and never retries.
- **Task** `fleet-evals/tasks/qav-held-001-gold-negatives/instruction.md` — the graded output
  contract is `verdicts/{BUNDLE-ID}.json` = `{"verdict": "approve"|"reject", "findings":[{"class","locus"}]}`,
  `class ∈ {DC-03,DC-05,DC-08,DC-12,DC-14}`, extra keys tolerated.

**The staged assistant target format** (from `src/qav/contracts.py::assistant_content`) is:

```
<think>
{reasoning}
</think>

```json
{ "verdict": "...", "findings": [ ... ] }
```
```

**Why it parses under that extractor (catch-3 verification):** the extractor's fenced-object
regex latches the ```` ```json … ``` ```` block. The capture `(\{.*?\})` is non-greedy but is
anchored by a trailing `\s*``` `; the only closing fence in the target follows the **final** `}`
of the verdict object (the inner `findings[{…}]` braces are *not* followed by a closing fence), so
the capture extends to the full balanced verdict object and `json.loads` yields the dict with the
row's own `verdict`. The QAV serving contract **wants** the ```json fence — so QAV is the *inverse*
of DCL catch-3 (where the contract wanted BARE source and the fence broke the lexer). Here the
staged target and the serving parse agree byte-for-byte; the round-trip below proves it on 108/108.

---

## 1. Corpus-on-disk vs receipts — PASS

| file | rows | raw sha256 (`sha256sum`) | canonical/manifest sha256 |
|---|---|---|---|
| `output/qa-verifier/train.jsonl` | 86 | `8bb5bce0e236…` | `5706f19eac0b3e3ec597d20a22b3ee45bfc334cb5db9ee0c197cd2b2ca9d3d7e` |
| `output/qa-verifier/eval_qav.jsonl` | 22 | `c26c9bc5a6a5…` | `66d7d6eb8e78…` |

**Reconciliation note (important — no defect):** the receipt/manifest sha `5706f19e…` (matching
the S2 charge's expected prefix) is the **canonical re-serialization** hash the factory records —
`src/qav/manifest.py::_jsonl_bytes` = `json.dumps(r, ensure_ascii=False, sort_keys=True)` joined by
`\n` + trailing `\n`, computed over parsed rows, **not** the raw file bytes. Reproduced here exactly:
canonical(train)=`5706f19eac0b…` ✅. The raw on-disk bytes hash to `8bb5bce0…`; the disk file is
byte-identical to the `output_backup_qav-growth-cycle6-take2-20260723-002149` snapshot. So "corpus on
disk matches the receipts" holds under the manifest's own hashing convention. Counts **86 / 22 = 108**
match. Corpus is git-untracked (DF-008 private) — confirmed.

- **Re-validation via `qav.contracts.validate_row`: 108/108 PASS.**
- **Standalone contamination gate** (`qav.contamination.check_contamination`, train×eval):
  **status = pass** — row_id intersection 0, sibling-variant violations 0, gold-negative
  source-task violations 0.

## 2. Serve-parse round-trip (all 108) — PASS 108/108

For every row: assistant content → **exam-side `extract_json`** → the parsed `verdict` compared to
the row's own label verdict (via the row contract's `parse_assistant_content`).

- **verdict match: 108/108.**
- **full `verdict`+`findings` object match: 108/108** (findings compared canonicalised, not just verdict).
- 0 rows raised in the exam extractor; 0 rows needed the balanced-object fallback path in a way
  that changed the result.

**No catch-3-class mismatch.** The staged targets byte-match what the serving contract asks the
seat to emit and what its extractor recovers.

## 3. Token-coverage probe (catch-2) — 0 leaked special/added tokens; one FLAG for staging design

Scanned all 108 assistant targets for special/added-token strings outside normal text+json:
`<|im_start|>`, `<|im_end|>`, `<|endoftext|>`, any `<|…|>`, `<start_of_turn>`, `<end_of_turn>`,
`<tool_call>`/`</tool_call>`, `<bos>/<eos>/<pad>/<unk>`, gemma `<0xHH>` byte sentinels, `<|channel|>`.

- **0 hits across every pattern.** No chat-template / tool framing bled into any target.
- **0 rows** carry control chars outside `\n \r \t`.
- **`<think>…</think>` present in 108/108** — this is BY CONTRACT (`assistant_content` wraps a think
  block before the fenced verdict), not a leak.

**FLAG for staging design (not a corpus defect — informational, loud):** the QAV target format bakes
`<think>`/`</think>` into **every** target (108/108). That is exactly the token class DCL **catch-2**
warns about — `<think>`/`</think>` are near-untrained added-vocabulary rows in a non-thinking base
(e.g. Qwen3-4B-**Instruct**-2507), where LoRA leaves `lm_head`/embeddings frozen and free generation
can collapse onto a confusable neighbour (`<tool_call>`). The manifest currently declares
`chat_template: gemma-4` (where `<think>` is ordinary text, not an added token — catch-2 would not
bite); but the DCL pilot **pivoted gemma-4 → Qwen3-2507**, and PLATEAU CARD #2 recommends
pilot-tune-now on that same precedent. **Decision the tune runbook must make explicitly before
training:** either (a) train on a genuinely think-native base whose `<think>` tokens are trained, or
(b) strip `<think>` from staged targets (DCL catch-2 fix) — noting QAV's serving contract does *not*
require think in the emitted answer (the extractor only needs the ```json fence). This is staging's
call, not a fix S2 makes silently.

## 4. Train-side class distribution (n=86)

| verdict | count | share |
|---|---|---|
| approve | 41 | 0.4767 |
| reject | 45 | 0.5233 |

Reject rows by DC class (`label.findings[].class`, equals `metadata.dc_class`):

| DC-03 | DC-05 | DC-08 | DC-12 | DC-14 |
|---|---|---|---|---|
| 27 | 3 | 8 | 0 | 7 |

Approve rows carry `dc_class = null` (41/41) and `findings = []` by contract. `DC-12` has **0** train
rows (unfilled class). Balance `approve_share = 0.4767` within `0.50 ± 0.10` — PASS (matches manifest).

*(Eval side, n=22, for context: verdict approve 5 / reject 17; dc_class DC-03 9, DC-08 4, DC-05 4,
null 5. Eval carries the two live DC classes plus the reject-heavy must-catch shape.)*

---

## Verdict

| check | result |
|---|---|
| counts (86 / 22 = 108) | **PASS** |
| manifest/canonical sha `5706f19e…` reproduced | **PASS** (raw bytes = `8bb5bce0…`; convention noted) |
| `validate_row` re-validation | **108/108 PASS** |
| standalone contamination gate | **PASS** |
| serve-parse round-trip (catch-3) | **108/108 PASS** |
| token-coverage / special-token leak | **0 leaks** — `<think>` catch-2 FLAG raised for staging |
| suite | `2512 passed` (baseline held) |

No corpus-on-disk defect found. One staging-design flag (catch-2 `<think>` targets) is raised loudly
for the tune runbook to resolve before training — S2 does not fix it here (the fix belongs to staging
design).

*Runner replicated read-only; corpus bytes untouched; DF-008 — shas + counts only, no row content.*
