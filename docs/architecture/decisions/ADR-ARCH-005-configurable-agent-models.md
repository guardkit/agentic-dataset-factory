# ADR-ARCH-005: Configurable Model Backends for Both Player and Coach

**Status:** Accepted
**Date:** 2026-03-16
**Deciders:** ML Engineer + /system-arch session

## Context

The original exemplar established `coach-config.yaml` for Coach model selection (D4). During architecture definition, it became clear that the Player agent also needs configurable model backends — especially during development where failing runs on free local inference is strongly preferred over consuming paid API credits.

## Decision

Extend the configuration to cover both Player and Coach via a unified `agent-config.yaml`:

```yaml
player:
  provider: local          # local | anthropic | openai
  model: "model-id"
  endpoint: "http://localhost:8000/v1"
  temperature: 0.7

coach:
  provider: local          # local | anthropic | openai
  model: "model-id"
  endpoint: "http://localhost:8000/v1"
  temperature: 0.3
```

This replaces the exemplar's `coach-config.yaml` with a broader `agent-config.yaml`.

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|-------------|
| Separate `player-config.yaml` + `coach-config.yaml` | Two files for related config; harder to switch the whole pipeline between modes |
| Environment variables only | Less readable, harder to version control, no structured validation |
| Keep `coach-config.yaml` and hardcode Player to API | Prevents free local development iteration; inconsistent configuration model |

## Consequences

- (+) Both agents configurable without code changes
- (+) Easy to switch entire pipeline between local (free) and API (paid) modes
- (+) Single config file — easy to understand and version control
- (+) Development workflow: use local models for iteration, switch to API for quality runs
- (-) Replaces exemplar's `coach-config.yaml` — minor migration from template
- (-) More configuration surface area to validate at startup
