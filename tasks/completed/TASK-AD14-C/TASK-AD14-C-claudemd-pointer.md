---
id: TASK-AD14-C
title: Add portfolio-pinning guide pointer to .claude/CLAUDE.md
status: completed
task_type: documentation
implementation_mode: direct
parent_review: TASK-REV-AD14
feature_id: FEAT-AD14
feature_slug: langchain-1x-portfolio-alignment
wave: 1
created: 2026-04-29T00:00:00Z
updated: 2026-04-29T00:00:00Z
completed: 2026-04-29T00:00:00Z
priority: low
tags: [documentation, portfolio-coherence, claude-md]
complexity: 1
estimated_minutes: 5
related:
  - .claude/reviews/TASK-REV-AD14-report.md
  - docs/architecture/decisions/ADR-ARCH-011-langchain-1x-portfolio-alignment.md
optional: true
---

# Add portfolio-pinning guide pointer to .claude/CLAUDE.md

## Context

TASK-REV-AD14 noted that `.claude/CLAUDE.md` lists the technology stack with versions but does not cross-reference the GuardKit portfolio-pinning policy ([`guardkit/docs/guides/portfolio-python-pinning.md`](`/Users/richardwoollcott/Projects/appmilla_github/guardkit/docs/guides/portfolio-python-pinning.md`)). Without the pointer, a future maintainer touching `pyproject.toml` in isolation has no signal that the open-floor-on-Python / `<2`-cap-on-langchain pattern is portfolio-canonical and not arbitrary.

This is a soft AC — file as part of the implementation feature or skip if the portfolio convention is that consumer-project CLAUDE.md files should not cross-link into GuardKit docs.

## Acceptance criteria

- [ ] `.claude/CLAUDE.md` Technology Stack section references the portfolio-pinning guide.
- [ ] OR: explicit decision to skip (annotate the TASK-REV-AD14 report's "CLAUDE.md Recommendation" section noting the skip rationale).

## Suggested edit

```diff
--- .claude/CLAUDE.md
+++ .claude/CLAUDE.md
 ## Technology Stack

-**Language**: Python
+**Language**: Python 3.11+ (open upper bound — see portfolio-python-pinning guide)
 **Frameworks**: DeepAgents >=0.4.11, LangChain >=1.2.11, LangChain-Core >=1.2.18, LangGraph >=0.2, LangChain-Community >=0.3
 **Architecture**: Adversarial Cooperation (Player-Coach multi-agent orchestration)
+
+> Pin alignment policy: this project tracks the portfolio canonical (coherent
+> langchain 1.x with `<2` caps, `deepagents>=0.5.3,<0.6`, `requires-python =
+> ">=3.11"`). See `guardkit/docs/guides/portfolio-python-pinning.md` and
+> `docs/architecture/decisions/ADR-ARCH-011-langchain-1x-portfolio-alignment.md`.
```

Note that the existing **Frameworks** line lists pre-TASK-AD14-A versions (`DeepAgents >=0.4.11`, `LangChain >=1.2.11`, etc.). Updating that line to match the post-TASK-AD14-A pin shape (`DeepAgents >=0.5.3,<0.6`, `LangChain >=1.2,<2`, `LangChain-Core >=1.3,<2`, `LangChain-Community >=0.4,<1`, `LangGraph >=1.1,<2`) is in scope for this task — it's literally the same documentation drift the pin diff fixes.

## Wave assignment

Wave 1 (parallel with TASK-AD14-A) — different files, no merge conflict risk.

## Out of scope

- Updating CLAUDE.md sections other than Technology Stack.
- Mirror-editing the portfolio-pinning guide in GuardKit (cross-repo change explicitly excluded by TASK-REV-AD14's brief).

## Notes

- This task is `optional: true` — the pin alignment work doesn't depend on it.
- If your portfolio convention is that `.claude/CLAUDE.md` is template-driven, the more durable home for the cross-reference may be the README.md or `docs/architecture/decisions/ADR-ARCH-011-...`. The ADR already cites the guide; the question is just whether CLAUDE.md needs the prompt-context-time pointer too. Ship if useful, skip if redundant.
