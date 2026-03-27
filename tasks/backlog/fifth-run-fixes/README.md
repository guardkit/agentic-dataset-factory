# Fifth Run Fixes (FEAT-TRF5)

Fixes for findings from the fifth pipeline run (TASK-REV-TRF5). The run failed with two P0 blockers: Coach tool leakage (8 platform tools injected via SDK middleware) and Coach empty content (vLLM reasoning parser strips think blocks, ChatOpenAI discards reasoning_content).

## Tasks

| Wave | Task | Title | Priority | Status |
|------|------|-------|----------|--------|
| 0 | TASK-TRF-011 | Restore langchain-skills from backup | P0 | Backlog |
| 1 | TASK-TRF-012 | Fix Coach tool leakage — bypass create_deep_agent | P0 | Backlog |
| 1 | TASK-TRF-013 | Fix Coach reasoning content extraction | P0 | Backlog |
| 2 | TASK-TRF-014 | Cap Player rag_retrieval loops | P1 | Backlog |
| 2 | TASK-TRF-015 | Investigate example truncation | P2 | Backlog |

## Key Decisions

1. **Restore langchain-skills first** — were active during exemplar build, lost on 2026-03-17
2. **Bypass create_deep_agent for Coach** — SDK has no way to suppress FilesystemMiddleware
3. **Revert Player to FilesystemBackend** — original exemplar design was correct
4. **Preserve Coach thinking** — don't disable reasoning; extract from reasoning_content instead

## See Also

- [Review Report](./../../../.claude/reviews/TASK-REV-TRF5-review-report.md)
- [Implementation Guide](./IMPLEMENTATION-GUIDE-TRF5.md)
- [Previous fixes (TRF4)](./IMPLEMENTATION-GUIDE-TRF4.md)
