# Architect Fine-Tune Dataset — Remaining Work

**Date:** 2026-04-29
**Goal:** Create production `domains/architect-agent/` in agentic-dataset-factory with all 19 books, run Docling ingestion, then generate the training dataset.

---

## 1. Book Inventory — What's Available

Mapped against the 19-book curated library (3 tiers):

### Tier 1 — The Modern Canon

| # | Book | File | Docling Mode | Status |
|---|---|---|---|---|
| 1 | A Philosophy of Software Design (Ousterhout) | `john-ousterhout-a-philosophy-of-software-design.pdf` | standard | ✅ |
| 2 | Tidy First? (Beck) | `tidy_first_scanned.pdf` | **VLM** | ✅ scanned |
| 3 | Code That Fits in Your Head (Seemann) | `code-that-fits-in-your-head.pdf` | standard | ✅ |
| 4 | Your Code as a Crime Scene (Tornhill) | — | — | ❌ **MISSING** |
| 5 | Modern Software Engineering (Farley) | `modern_software_engineering_scanned.pdf` | **VLM** | ✅ scanned |
| 6 | Software Architecture: The Hard Parts (Ford et al.) | `Software_Architecture_The_Hard_Parts_Neal_Ford_OReilly_9781492086895.pdf` | standard | ✅ |
| 7 | Architecture for Flow (Kaiser) | `architecture_for_flow_scanned.pdf` | **VLM** | ✅ scanned |
| 8 | Crafting Engineering Strategy (Larson) | `Crafting_Engineering_Strategy_-_Will_Larson.pdf` | standard | ✅ |

### Tier 2 — Architectural Thinking

| # | Book | File | Docling Mode | Status |
|---|---|---|---|---|
| 9 | Team Topologies (Skelton & Pais) | `team-topologies-organizing-business-and-technology-teams-for-fast-flow-by-matthew-skelton-manuel-pais-skelton-matthew-z-liborgepub.pdf` | standard | ✅ (verify it's a valid PDF despite "epub" in filename) |
| 10 | Domain-Driven Design (Evans) | `Eric Evans 2003 - Domain-Driven Design - Tackling Complexity in the Heart of Software.pdf` | standard | ✅ |
| 11 | Implementing DDD (Vernon) | `Implementing Domain-Driven Design.pdf` | standard | ✅ |
| 12 | Designing Data-Intensive Applications (Kleppmann) | `designing-data-intensive-applications-the-big-ideas-behind-reliable-scalable-and-maintainable-systems.pdf` | standard | ✅ |
| 13 | Building Evolutionary Architectures 2nd Ed (Ford) | `Building_Evolutionary_Architectures_2nd_Ed_-_Neal_Ford.pdf` | standard | ✅ |
| 14 | Facilitating Software Architecture (Harmel-Law) | `Facilitating_Software_Architecture_-_Andrew_Harmel-Law.pdf` | standard | ✅ |
| 15 | The Software Architect Elevator (Hohpe) | `The_Software_Architect_Elevator_-_Gregor_Hohpe.pdf` | standard | ✅ |
| 16 | Observability Engineering (Majors et al.) | `Observability-Engineering.pdf` | standard | ✅ |
| 17 | Architecture Modernization (Tune) | `Architecture_Modernization.pdf` | standard | ✅ |
| 18 | Accelerate (Forsgren et al.) | `Accelerate - Building and Scaling High Performing Technology Organisations - Nicole Fergrson.pdf` | standard | ✅ |
| 19 | Threat Modeling (Shostack) | `Threat Modeling - Shostack, Adam.pdf` | standard | ✅ |

**Summary:** 18/19 books present. 3 scanned (need Docling VLM mode). 1 missing (Your Code as a Crime Scene).

---

## 2. Decisions Needed Before Writing GOAL.md

### D1: Drop or restructure `type=direct` categories?

The probe found 13.3% provider-side refusals on `type=direct` targets vs 0% on `type=reasoning`. Three options:

| Option | Impact | Recommendation |
|---|---|---|
| **A: Drop direct-type entirely** | Simplest. All examples get `<think>` blocks. 100% reasoning. | ✅ Recommended unless direct-type is load-bearing |
| B: Restructure direct → reasoning | Add minimal `<think>` block to all categories. Changes the feel of short factual answers. | Viable fallback |
| C: Keep direct, accept refusal rate | ~13% of direct targets wasted. Pipeline handles it via retry. | Only if Qwen3.6 has lower refusal rate |

**Recommendation:** Option A for the first production run. If the downstream eval shows the model needs short factual responses, add them back as reasoning-type with a thin `<think>` block in a follow-up run.

### D2: Proceed without "Your Code as a Crime Scene"?

It's a Tier 1 book (behavioural analysis of codebases, hotspots, temporal coupling). Options:

| Option | Impact |
|---|---|
| **A: Proceed with 18 books, add Tornhill later** | Loses the behavioural-analysis-of-code perspective. Can be added as a supplementary run. |
| B: Wait until scanned | Blocks the entire pipeline. |

**Recommendation:** Option A. The book's unique contribution (using change patterns to understand architecture) is valuable but not blocking. The other 18 books cover the core architectural thinking. Add it as a ChromaDB collection update when available.

### D3: Scale of the production run

The probe ran 110 targets in ~2 hours. The GCSE tutor GOAL.md has 2,575 targets. For the architect, the question is how many examples do we need.

| Scale | Targets | Estimated Time | Notes |
|---|---|---|---|
| Probe (done) | 110 | 2 hours | Diagnostic only |
| Medium | 500-800 | 10-16 hours | Enough for a meaningful fine-tune |
| Large | 1,500-2,000 | 30-40 hours | Comparable to GCSE tutor |
| Full | 2,500+ | 50+ hours | Maximum coverage |

**Recommendation:** Start with Medium (500-800). The architect domain has 18 books vs GCSE's handful of guides — the RAG corpus is much richer, so fewer generation targets per category can still produce diverse examples. Run eval, check quality, scale up in a follow-up.

### D4: Category design — what should the architect know?

The probe used 7 categories across 2 books. Production needs to cover 18 books across these architectural thinking dimensions:

| Dimension | Example categories | Books that feed it |
|---|---|---|
| **Strategic design** | Bounded contexts, context maps, domain events, ubiquitous language | Evans, Vernon, Team Topologies |
| **Tactical patterns** | Aggregates, entities, value objects, repositories, domain services | Evans, Vernon |
| **Trade-off analysis** | Service granularity, data decomposition, distributed transactions | Ford Hard Parts, Building Evolutionary Architectures |
| **Complexity management** | Deep modules, cognitive load, information hiding, tidying economics | Ousterhout, Beck, Seemann |
| **Evolutionary architecture** | Fitness functions, guided change, architecture as options | Ford BEA, Farley, Beck |
| **Team & org design** | Conway's Law, team topologies, flow optimisation | Skelton & Pais, Kaiser, Forsgren |
| **Data architecture** | Partitioning, replication, consistency models, stream processing | Kleppmann |
| **Operational thinking** | Observability, threat modeling, modernisation strategies | Majors, Shostack, Tune |
| **Communication & facilitation** | Architecture decision records, stakeholder communication, elevator pitch | Hohpe, Harmel-Law, Larson |

---

## 3. Remaining Task List

In execution order. Tasks marked 🤖 can be done by Claude Code on the GB10. Tasks marked 🧑 need Rich.

| # | Task | Who | Depends On | Estimated Time |
|---|---|---|---|---|
| **T1** | Decide D1-D4 above | 🧑 Rich | — | 10 min |
| **T2** | Write production `GOAL.md` for `domains/architect-agent/` | Claude Desktop (this session) | T1 | 30 min |
| **T3** | Create `domains/architect-agent/sources/` and symlink books from `architecture_books/` | 🤖 Claude Code GB10 | T2 | 5 min |
| **T4** | Run Docling ingestion (Stage 0) — 15 standard + 3 VLM mode | 🤖 Claude Code GB10 | T3 | 2-4 hours |
| **T5** | Verify ChromaDB collection has expected chunk counts | 🤖 Claude Code GB10 | T4 | 5 min |
| **T6** | Widen `metadata.topic` enum (probe finding) | Claude Desktop or 🤖 | T2 | Already in GOAL.md |
| **T7** | Run production generation pipeline (Stage 1) | 🤖 Claude Code GB10 | T5 | 10-40 hours (scale-dependent) |
| **T8** | Review output quality: spot-check `train.jsonl` + `knowledge.jsonl` | 🧑 Rich | T7 | 30 min |
| **T9** | Fine-tune Gemma 4 with architect LoRA (`train_gemma4_moe.py --chat-template gemma-4`) | 🤖 Claude Code GB10 | T8 | 2-4 hours |
| **T10** | Deploy architect adapter to llama-swap | 🤖 Claude Code GB10 | T9 | 15 min |

**Critical path:** T1 → T2 → T3 → T4 → T5 → T7 → T9 → T10

**Total estimated time to production architect model:** ~15-50 hours depending on scale choice (D3), with most of that being unattended GB10 pipeline time.

---

## 4. Notes for GOAL.md Authoring

Things to carry forward from the probe findings and GCSE tutor GOAL.md:

- **System prompt:** The probe's system prompt is good — keep it with minor refinements for the full book set
- **75/25 think ratio:** The probe was designed for refusal testing so had a different split. Production should follow the GCSE pattern: 75% reasoning (with `<think>`), 25% direct. But if D1 = Option A (drop direct), then 100% reasoning.
- **Evaluation criteria:** Keep `technical_precision`, `terminology_correct`, `reasoning_shown`, `no_verbatim_reproduction`, `completeness` from the probe. Add `trade_off_acknowledged` for categories where trade-offs exist.
- **Metadata schema:** Widen `pattern_family` and `topic` enums significantly. The probe had 7 pattern families and 13 topics — production needs ~15 pattern families and 40+ topics to cover 18 books.
- **Layer routing:** Same as probe — `behaviour` → `train.jsonl`, `knowledge` → `rag_index/knowledge.jsonl`
- **Chat template fix:** Use `--chat-template gemma-4` (not `gemma-4-thinking`) for the fine-tune to avoid the template-token leak. Enforce via the fail-fast check from `DATASET-FIX-tutor-template-leak.md`.

---

*Prepared: 2026-04-29*
*Cross-references: probe-findings.md, DATASET-FIX-tutor-template-leak.md, architecture-books-research-output.md*
