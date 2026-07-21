# RECEIPT — G1: SEEDED-SOURCE DISCOVERY EXPANSION (feature-tracker reader) — 2026-07-21

> **The census answer: 13 INCLUDED source tasks before, 13 after — the approved-sha honesty law
> held.** No repo beyond guardkit + study_tutor supports seeded INCLUSION, because no other repo
> emits an autobuild `merge_summary.json`. The lever this lane actually delivers is a **new
> feature-tracker record-shape reader** that turns ~730 estate-wide approved tracker tasks from
> **silently invisible** into **precisely recorded turn-aways**, and surfaces the two repos
> (fleet-memory, specialist-agent) the discovery had never walked. **0 new run records recovered**
> (PRV-style history mining had nothing new to mine — every resolvable feature's records were
> already in the store; integrity re-verified: 10 records / 90 files / 0 sha256 mismatches).

Factory HEAD at filing: `4921ab9` (concurrent seeded_bundle/render-collapse commits landed under
this lane; changes are additive on top). Discovery machinery only — the ed00704 byte-frozen
validators (contracts/recipes-families/injector/harvest/gold_negatives/contamination/manifest) were
**not touched**. Full suite: **2450 passed** (was 2432 baseline; +18 tests). ruff clean.

---

## 1. One-minute version

| Question | Answer |
|---|---|
| INCLUDED seeded source tasks — **before** | **13** (guardkit 6, study_tutor 7) |
| INCLUDED seeded source tasks — **after** | **13** (unchanged — the honesty law held) |
| Corpus roots — before → after | **6 → 8** (added `fleet_memory`, `specialist_agent`) |
| Repos whose records support the approved-sha law (INCLUSION) | **still only 2** (guardkit, study_tutor — the sole `merge_summary.json` emitters) |
| New record-shape reader added | **feature-tracker** (`.guardkit/features/*.yaml` + `archive/*/feature_state.yaml`) |
| Approved tracker tasks now turned away by a PRECISE recorded exclusion (were silent) | **730** across 8 repos |
| Features that merged (resolvable sha) but have stale/pending tasks — now NAMED | **2** (specialist_agent FEAT-32E7 → `a6da898`, FEAT-8060 → `fc488ce`) |
| Run records recovered this lane (PRV-style git-history mining) | **0** (nothing new resolvable; store already complete) |
| Record-store integrity (existing 10 recovered records) | **10 records / 90 files / 0 sha256 mismatches** |

**Why 13 → 13 is the honest ceiling.** Seeded INCLUSION checks a task out at its **approved sha**
and injects a defect. The approved sha may come ONLY from a committed record — never HEAD, never a
git-log guess. Across the estate, that record is the autobuild `merge_summary.json`, and **only
guardkit and study_tutor emit one**. The other six repos carry the *feature-tracker* shape instead,
which records per-task `result.final_decision: approved` but **no committed approved-sha** — and a
tracker "approved" is **not** an autobuild coach-approve-and-held (see §3, the FEAT-FMDR proof). So
they cannot honestly seed an approve, and the reader excludes them, loudly.

---

## 2. What was built (additive, discovery-side only)

1. **Feature-tracker reader** — `src/qav/discover.py`:
   - `resolve_tracker_approved_sha(repo_root, record)` — resolves a feature's committed merge sha
     from record prose (`completed_evidence` / `execution.note` / `merged`, the "merged/salvaged to
     main `<sha>`" phrasing), **git-`cat-file`-resolving** every candidate. Returns `None` (never
     HEAD, never a guess) when nothing in the record resolves. The regex only *proposes*; git is the
     final authority, so a timestamp or non-commit token fails closed to an exclusion.
   - `_classify_feature_tracker(...)` — classifies one tracker into **precise per-task/feature
     exclusions** (the tracker shape NEVER produces an INCLUSION — inclusion stays merge_summary-
     gated):
     - **completed tracker, tasks with a `result`** → one exclusion per task, naming the claimed
       `final_decision` and the resolvable merge-sha when the record carries one.
     - **merged feature, stale/pending tasks (no per-task result)** → a *distinct* exclusion that
       NAMES the resolvable sha ("feature merged … but per-task ledger records no result … no
       approvable task; never inferred from the feature-level merge") — the FEAT-32E7/8060 case.
     - **planned/spec-only stub (no results, no sha)** → the pre-existing whole-feature "spec-only"
       reason, unchanged (FEAT-SMP-001 regression-guarded).
   - `discover_source_task_refs` now walks the tracker shape (live `features/*.yaml` + archived
     `archive/*/feature_state.yaml`), **skipping any feature already covered by a `merge_summary`**
     (merge_summary wins; no double-count).
2. **Corpus roots extended** — `domains/qa-verifier/agent-config.yaml`: added `fleet_memory` +
   `specialist_agent` (the harvest union census's 7th/8th repos) + their interpreter venvs
   (verified present on disk), with an honest comment that tracker repos contribute **zero** seeded
   source tasks by the honesty law — now audibly, not silently.
3. **Config filter fix** — `src/qav/generate.py` `GenerateConfig.from_yaml`: `corpus_roots` now
   excludes the non-repo keys `bundle_schema_sha` **and** `record_store_roots` and keeps only
   string-valued path entries. Before, `record_store_roots` (a list) leaked in as a stringified
   bogus root — harmless when discovery only globbed `.guardkit/archive`, but the new tracker walk
   reads each root's `.guardkit`, so a fake root would be a real filesystem misread.

Tests: **+11** in `tests/test_qav_discover.py` (resolver: completed_evidence / salvaged-commit
phrasing / unresolvable-never-HEAD / absent; classifier: approved-never-included, the FEAT-FMDR
false-green-with-resolvable-sha trap, merged-but-stale naming, gold-source, spec-only regression,
no-double-count vs merge_summary, archived feature_state walk) + **1** in `test_qav_generate.py`
(the filter fix). All hermetic (temp git repos; no model/seat/network).

---

## 3. The load-bearing finding — why a tracker never seeds an approve

A naive reader keying on (`final_decision == approved` + a resolvable sha) is **unsafe**. The
definitive estate scan found exactly **one** feature with both per-task approved results AND a
git-resolvable sha: **forge `FEAT-FMDR`** (sha `4753b20`) — and it is a **documented autobuild
false-green**. Its own record points at `docs/reviews/FEAT-FMDR-autobuild-false-green-analysis.md`
and notes *"Manual completion (not /feature-complete) … manually salvaged to main."* Census **U1**
already excludes `FEAT-FMDR-004`. Seeding an APPROVE control row from it would inject a known
coach-escape into the approve side. Two more merged-sha features (specialist_agent
FEAT-32E7/8060) turned out **stale** — merged, but every per-task decision still `pending`, no
approval ever recorded. So the honest rule, consistent with the ratified Option-B policy (the
census's A2/A3/U1 and the batch-card's A1-J, which required an *independent* live-gate beyond the
tracker): **tracker evidence alone never justifies an approve.** Inclusion stays gated on a
committed `merge_summary.json`; the instant a repo emits one, the base walk includes it with no new
code.

---

## 4. Census — INCLUDED / EXCLUDED, before → after (factory-side, read-only walk)

**Roots:** 6 → **8** (`api_test, fleet_memory, forge, guardkit, jarvis, nats_core,
specialist_agent, study_tutor`).

| | before | after |
|---|---|---|
| **INCLUDED** | 13 | **13** — guardkit `TASK-QAWE-001..004`@`799cefd0`, `TASK-BDDW-001/002`@`917bcef7`; study_tutor `TASK-PRV-001..007`@`94f3331` |
| EXCLUDED total | 97 | **772** |
| — merge_summary-path (unapproved / no-sha-key / gold) | 7 | 7 |
| — genuine spec-only stubs | ~90 (mislabeled) | 33 |
| — **feature-tracker per-task turn-aways** (were **silent**) | 0 | **730** |
| — merged-but-stale features, sha NAMED | 0 | **2** |

Tracker turn-aways by repo: guardkit 196 · specialist_agent 185 · forge 114 · jarvis 86 ·
study_tutor 59 · fleet_memory 37 · nats_core 35 · api_test 18. (Before this lane, jarvis's
completed FEAT-28FF — 7 approved tasks — was mislabeled a single "spec-only" feature, and
fleet-memory + specialist-agent were not walked at all.)

Decision-relevant read for Rich: there are **~730 approved tracker tasks** across the estate that
would become seedable the moment a per-task **approved-sha source of record** exists (census cap 3
— the open provenance question). The gap is **provenance, not corpus**: the approved tasks lack a
committed sha; the two features that DO record a merged sha lack per-task approval. Neither half is
guessed into an approve.

---

## 5. PRV-style history mining (part 2) — 0 new, store re-verified

The bf30341 pattern (recover a feature's HEAD-missing run records at/near its approved sha in git
history, copy verbatim into `record-store/<repo>/<task>/` with sha256 provenance) is driven by
**resolvable features whose records are absent at HEAD**. Since no new feature resolves an approved
sha (§1), there is **nothing new to mine**. Verified end-to-end instead:

- **All 13 INCLUDED tasks locate a run record** (3 from the corpus live tree, 10 from the factory
  record-store) — **0 missing**.
- **Record-store integrity:** `domains/qa-verifier/record-store/index.json` — **10 records, 90
  files, 0 sha256 mismatches / 0 missing files**. The prior recovery (guardkit TASK-QAWE-003/-004,
  TASK-BDDW-002; study_tutor TASK-PRV-001..007) is complete and authentic.

**Records recovered this lane: 0.** No git-history blob mining was needed; none is honest to add.

---

## 6. Provenance / laws honored

- Corpus repos **read-only** (record walks only; no worktree checkout attempted — tracker repos
  yield zero INCLUDED, so `discover_source_tasks` never checks any of them out).
- Approved-sha honesty preserved: every tracker turn-away is a recorded `ExclusionRecord`; no sha
  defaulted to HEAD; git `cat-file` is the sole resolvability authority.
- ed00704 byte-frozen validators untouched; only discovery machinery (`discover.py`) + config
  parse (`generate.py`) + config data + tests changed.
- Commit **path-limited** to the five changed files + this receipt. `run_logs/*.jsonl` and
  `manifests/` run artifacts **not** committed (untracked by design).
