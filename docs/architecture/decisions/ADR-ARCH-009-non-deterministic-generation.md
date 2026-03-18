# ADR-ARCH-009: Non-deterministic Generation with Coach Quality Gate

**Status:** Accepted
**Date:** 2026-03-16
**Deciders:** ML Engineer + /system-arch session

## Context

For high-quality fine-tuning datasets, we need to balance reproducibility with diversity. Seeded/deterministic generation produces identical outputs per run (good for debugging) but risks homogeneous training data. Non-deterministic generation produces diverse examples but is harder to reproduce exactly.

## Decision

Use non-deterministic generation with moderate temperature (~0.7 for Player, ~0.3 for Coach) and rely on the Coach as the quality gate. Use LangSmith traces for post-hoc debugging of specific generations.

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|-------------|
| Seeded/deterministic (temperature=0) | Produces repetitive, homogeneous training data; re-runs generate identical output (pointless for scaling dataset); can cause mode collapse in fine-tuning |

## Consequences

- (+) Diverse training data — essential for robust fine-tuning (prevents mode collapse in Nemotron MoE)
- (+) Re-runs generate genuinely new examples — useful for scaling the dataset
- (+) Coach enforces quality regardless of sampling variation
- (+) LangSmith traces provide full reproducibility for debugging any specific generation
- (-) Cannot reproduce exact failures without LangSmith trace context
- (-) Occasional surprising outputs (mitigated by Coach rejection)
