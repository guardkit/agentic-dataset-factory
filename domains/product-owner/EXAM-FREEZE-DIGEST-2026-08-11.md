# The product-owner exam — the one-page freeze digest
## 2026-08-11 · for Rich's freeze word (job 3 of the dataset-generation lane)

## The one-minute version

fleet-evals has carried a complete product-owner exam since 3rd July — eight held-out
tasks that between them cover the whole job of turning an intent into a specification
and a plan. It has never been run against any candidate. Before anything is graded
against it (the teacher bake-off next, tuned candidates much later), the pass bar needs
your freeze word. **After the word, the bar is immutable and may only ever be raised —
the same law that governed the coach exam.** Freezing changes nothing about training:
that stays parked behind your separate word.

## The eight tasks and what each one demands to pass

| # | Task (plain name) | What the candidate gets | What passing means |
|---|---|---|---|
| 1 | **Read the documents, draft the plan** | 14 pinned research documents | One strict-JSON epic plan: cites only files that really exist, covers every required area, at least 5 epics / 18 feature stubs |
| 2 | **Enrich one epic** | The task-1 plan + only the documents one epic cites | A valid enrichment delta: real citations only, stays inside that epic's stub list, enriches every stub, drops none |
| 3 | **The whole roadmap in one pass** | The full document corpus | One complete roadmap JSON: full schema, zero invented filenames, same coverage floors as task 1 |
| 4 | **Honest greenfield** | A thin brief with deliberate unknowns | A roadmap whose grounding is honestly EMPTY — no fake citations anywhere — plus ≥3 falsifiable assumptions with impact-if-wrong |
| 5 | **Honest idea** | A 3-sentence idea, 5 deliberate unknowns | Everything task 4 demands, PLUS: any specific detail asserted in the output must be licensed by a stated assumption or open question — unlicensed invention fails |
| 6 | **Cut to a constraint** | An existing roadmap + "6 weeks, 2 engineers, MVP-first" | A strict subset of the original: nothing renamed, dependencies still closed, the constraint visibly carried through |
| 7 | **Write a feature spec** | A thin brief (6 deliberate unknowns) | The real three-file spec package (Gherkin + assumptions + summary): structurally valid, ≥8 scenarios, no implementation language in steps, every count agreeing, every assumption licensed |
| 8 | **Plan a feature** | A pinned, frozen spec package | The full plan tree that passes guardkit's own validator: ≥3 tasks over ≥2 waves, correct task metadata, required diagrams, scenario↔task links coherent, the input spec preserved byte-for-byte |

**How it's marked:** tasks 1–6 are driven by one HTTP call each against the candidate's
endpoint, three attempts per task, graded by deterministic pytest gates (no human
judgment, no LLM judge). Tasks 7–8 are graded as dropped file trees produced by the real
/feature-spec and /feature-plan tools. The graders validated clean against the frozen
gold solutions.

## What the stock-take says (job 1, completed today — the fact you should see before freezing)

213 clean production traces are banked (11th–31st July; none since — no spec-chain runs
in August). Against the eight shapes:

| Exam shape | Real captures | Survive quality filters |
|---|---|---|
| 1–3 Document extraction (×3) | **0** | **0** |
| 4 Greenfield | 64 | 52 |
| 5 Idea | 34 | 31 |
| 6 Scope | 9 (wrong input shape — prose asks, not roadmap+constraint) | 9, weak fit |
| 7 Feature-spec | 39 | 39 |
| 8 Feature-plan | 35 | 35 |

**The consequence:** the generative half of the corpus rests on real production examples
(157 usable). The extraction shapes have no captured *runs*, but they are not empty-handed:
a separate 91-record harvest (`~/po-dataset/`, built 2nd July) is already designated as
extract-mode seed in adf's product-owner plan — teacher-authored extract rows will reshape
that real material. Only the scope shape's input contract (roadmap + constraint) has
nothing real behind it; those rows would be **fully synthetic, every row marked synthetic**
(the handoff provides for this; the exam stays the arbiter of whether the specialist
actually learned the skill).

**Venue readiness (job 2, completed today):** adf's ledgered bundle-generator fix list
was swept — zero of the six defects are inherited by this lane (all live behind the
coach-corpus boundary; four carry over as design lessons, adopted). The full adf test
suite is green: 2,796 passed, 0 failed.

## The word being asked for

One word freezes the eight pass bars exactly as they stand. If instead you want any bar
adjusted (or an extraction task de-scoped given the zero real coverage), that happens
NOW — after the freeze it can only be raised, never lowered.
