# Receipt — PER-REPO TEST-COMMAND PINS (forge / jarvis / nats_core), the cycle-3 28-refusal lever (2026-07-22)

> **ONE OF THE THREE REPOS TAKES A PIN, AND IT SPIKES GREEN; THE OTHER TWO ARE HONEST
> EXPECTED-MISSES, NOT FORCED.** Cycle-3's 28 `evidence_invariant` refusals from the newly-seeded
> consumable-sourced repos were read as "auto-detect never exercised the planted defect → pin a
> command per repo." Investigated at the approved shas: only **jarvis** actually anchors reject
> recipes (R-DC08-{undefstep,pendmask}, on all 4 tasks); **forge (5 tasks) and nats_core (1 task)
> anchor ZERO** — all 11 recipes `ANCHOR_SKIP` (guardkit-shaped probes or non-unique matches), so
> they can produce no reject leg to pin a command against (the study_tutor lesson, replayed). jarvis
> got the pin: a service-free `-k publishes` scope over the one BDD glue file both recipes mutate,
> tokenisation-law-safe (`test_cmd.split()`, shell=False) and warnings-suppressed for determinism.
> **LIVE MICRO-SPIKE (real bridge, integration profile, TASK-JNB-001, run twice): CONTROL green;
> R-DC08-undefstep DIVERGED + real failing-test evidence (`collection_error`) + DETERMINISTIC;
> R-DC08-pendmask DIVERGED (2-skipped vs 2-passed = the masking signature) + DETERMINISTIC.** No
> validator/guard/scrub touched; recipe ids/families/semantics byte-frozen; corpus repos read-only.

Factory HEAD at investigation: `0b76a57` → `8ff7eb6` (a concurrent study_tutor recipe-anchor lane
landed mid-session; this lane rebased onto it and committed path-limited, sweeping no foreign hunk).
Corpus HEADs unchanged: jarvis `1fc7309`, forge `686439c`, nats-core `2c060b2` (detached scratch
worktrees only, removed). `contracts.py`/`recipes.py`/`injector.py`/`scrub.py` untouched by this
lane; the evidence-divergence guard + scrub UNTOUCHED. Flock-guard held on every regeneration; the
keepalive timer never touched (CPU-only bridge — no fleet/GPU/model). No push. DF-008.

---

## 1. The per-repo verdicts (the ask)

| repo | seeded tasks @ sha | anchoring reject recipes | verdict |
|---|---|---|---|
| **jarvis** | 4 (JNB-001/002/003/008 @ `736399b`) | R-DC08-undefstep, R-DC08-pendmask (all 4 tasks, same BDD file) | **PINNED + SPIKED GREEN** |
| **forge** | 5 (MP-001/002/003/004A/007 @ `34b17d0`) | none — 11/11 `ANCHOR_SKIP` | **honest expected-miss, NO pin** |
| **nats_core** | 1 (MEP-002 @ `d1f421e`) | none — 11/11 `ANCHOR_SKIP` | **honest expected-miss, NO pin** |

Discovery ran the real `qav.discover.discover_source_tasks` (record-resolved approved shas, the
ratified-consumable seeding lever `943d968`) and `qav.injector.inject` over every active recipe ×
every discovered task (CPU/git/fs only). forge + nats_core skip because the recipe probes are
guardkit-shaped (`chunk_threshold __init__`, `analyze_wiring`, `run_bdd_for_task`,
`quality_gates/__init__.py`, the SMP junit surface) or match ambiguously (plan/step probes hit many
markdown files → `_find` correctly declines non-unique). A repo with zero anchoring reject recipes
has no reject leg to run a pinned command against; pinning it would be config for a dead path
(declined per the no-gold-plating discipline — the exact study_tutor `test_command`-not-pinned call).

## 2. jarvis — the pin, and why the scope is what it is

Both anchoring recipes mutate the **one** BDD glue file
`features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/test_feat_jarvis_004_fleet_registration_and_specialist_dispatch.py`,
at its **shared background step** `@given("Jarvis is starting up with a configured NATS endpoint")`.
That file is **43-failed / 2-passed** at the approved sha — feat-004's other scenarios are honestly
`scenarios_pending` (pytest-bdd `StepDefinitionNotFoundError`, the FEAT-BDDM convention) until their
own tasks land step-defs. So the **whole-file scope is not control-green** and cannot carry an honest
approve. `-k publishes` selects **exactly** the two TASK-J004-007 scenarios that carry the mutated
background step (`test_jarvis_publishes_…` + `test_jarvis_republishes_…`) → **control: 2 passed, 43
deselected**, service-free (drives `nats_core.InMemoryManifestRegistry` via monkeypatch, no broker).

**Pinned command:**
```
pytest features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/test_feat_jarvis_004_fleet_registration_and_specialist_dispatch.py -k publishes -p no:cacheprovider -p no:warnings
```

Two design laws, both learned empirically here:

- **LAYER-2 tokenisation law.** guardkit's `CoachValidator` runs the pinned command via
  `test_cmd.split()` under `shell=False` (`coach_validator.py ~L5422`), **not** a shell. A quoted
  multi-word token (`-k "publishes or republishes"`) tokenises into broken args
  (`['-k', '"publishes', 'or', 'republishes"']`) and silently mis-scopes. `-k publishes` is a **single
  whitespace-free token** that uniquely matches `publishes`/`republishes` across all 45 test names —
  verified — so it needs no quoting.
- **Determinism (a scrub-untouched field).** `-p no:warnings` suppresses pytest's UNKNOWN-MARK
  warnings summary (14 `PytestUnknownMarkWarning` lines from `features/conftest.py:59` iterating tags
  set-wise) whose **line ORDER is non-deterministic across runs** and lands in the scrub-untouched
  `independent_tests.raw_output`. Because the scrub is UNTOUCHABLE in this lane, the non-determinism
  is removed **at source** in the command. (undefstep never hits it — it bails at collection.)

## 3. THE LIVE MICRO-SPIKE — real bridge, `task_type=integration`, TASK-JNB-001, run twice

Real `SubprocessBridgeRegenerator` → `qav_regenerate_bridge` → guardkit `gather_evidence`, jarvis
venv pytest pinned via `--venv-python`, every bundle scrubbed before hashing. **Zero model/GPU/fleet**
(bundle regen is CPU/pytest only); flock-guard held.

| leg | scrubbed bundle content sha256[:16] | evidence |
|---|---|---|
| CONTROL (no-op) | `f7c0f9a6524c415d` | `gathering_status=complete`, `all_gates_passed=true`, `it_passed=true` — honest approve |
| R-DC08-undefstep run 1 | `dfbe579f2fbe71af` | `it_passed=false`, `failure_class=collection_error` (the deleted step-def mangles the module → collection fails) |
| R-DC08-undefstep run 2 | `dfbe579f2fbe71af` | — |
| R-DC08-pendmask run 1 | `77f89cd6d95e4eb1` | `2 skipped, 43 deselected` — the honest masking signature (skip, not fail) |
| R-DC08-pendmask run 2 | `77f89cd6d95e4eb1` | — |

- **(A) DIVERGED** — both recipes ≠ control; the evidence-divergence guard PASSES each (no false
  refusal). undefstep earns it with real failing-test evidence; pendmask earns it with the
  passed→skipped result change that IS the DC-08 pending-mask defect signature.
- **(B) EVIDENCE** — undefstep surfaces the planted defect as a real `collection_error`; the CONTROL
  over the same scope is clean-green (its approve label is honest).
- **(C) DETERMINISTIC** — run 1 == run 2 byte-for-byte for BOTH recipes (pendmask only after
  `-p no:warnings`; the raw two-run diff pre-fix isolated to the permuted warnings-summary block).

**All three gates GREEN for jarvis.** Both anchoring recipes surface cleanly and reproducibly; the
28-refusal lever is real for jarvis's share and honestly empty for forge/nats_core.

## 4. Hermetic tests for config threading (`tests/test_qav_generate.py`, +2)

- `test_config_yaml_loads_multi_repo_test_commands` — `from_yaml` threads a MULTI-repo
  `regeneration.test_commands` block (guardkit + a jarvis-shaped pin) into `GenerateConfig.test_commands`
  per key (a dropped/mis-keyed pin silently falls a repo back to stack-misdetecting auto-detect).
- `test_pinned_test_commands_obey_the_layer2_tokenisation_law` — the executable guard for §2's
  tokenisation footgun: every pinned command starts with `pytest ` and contains NO shell-quote char,
  so `test_cmd.split()` (shell=False) yields intact args.

(The generic threading `from_config → bridge --test-command` is already covered by
`tests/test_qav_regenerate.py::{test_layer2_test_command_selected_per_repo,
test_from_config_threads_regen_task_type_and_test_commands}`.) Full suite:
`uv run --no-sync pytest -q` → **2499 passed** (≥ the 2494 baseline).

## 5. Files (adf-side; path-limited; no push; validators/guard/scrub/recipes byte-frozen)

- `domains/qa-verifier/agent-config.yaml` — the jarvis `regeneration.test_commands` pin + its
  provenance comment (only hunk; the guardkit/study_tutor pins are prior lanes', untouched).
- `tests/test_qav_generate.py` — the two hermetic config-threading tests above.
- `domains/qa-verifier/receipts/per-repo-test-command-pins-2026-07-22.md` — this receipt.
- NOT committed: `manifests/qav-phase1-train.manifest.json` (pre-existing working-tree residue, not
  this lane's). Corpus repos read-only, HEADs unchanged, scratch worktrees removed. Keepalive timer
  never touched; flock-guard held on every regeneration.
