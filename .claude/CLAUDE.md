# deepagents-tutor-exemplar

## Project Overview

This is a Python project using DeepAgents >=0.4.11, LangChain >=1.2.11, LangChain-Core >=1.2.18, LangGraph >=0.2, LangChain-Community >=0.3.
Architecture: Adversarial Cooperation (Player-Coach multi-agent orchestration)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Start development
# See project documentation
```

## Detailed Guidance

For detailed code style, testing patterns, architecture patterns, and agent-specific
guidance, see the `.claude/rules/` directory. Rules load automatically when you
work on relevant files.

- **Code Style**: `.claude/rules/code-style.md`
- **Testing**: `.claude/rules/testing.md`
- **Patterns**: `.claude/rules/patterns/`
- **Guidance**: `.claude/rules/guidance/`

## Knowledge Graph (Graphiti)

This project has a Graphiti MCP server providing a persistent knowledge graph.
**When searching, always pass `group_ids: ["product_knowledge", "command_workflows", "architecture_decisions"]`** —
searching without group_ids returns empty results.

For full usage details, see `.claude/rules/graphiti-knowledge-graph.md`.

## Technology Stack

**Language**: Python 3.11+ (open upper bound — see portfolio-python-pinning guide)
**Frameworks**: DeepAgents >=0.5.3,<0.6, LangChain >=1.2,<2, LangChain-Core >=1.3,<2, LangChain-Community >=0.4,<1, LangGraph >=1.1,<2
**Architecture**: Adversarial Cooperation (Player-Coach multi-agent orchestration)

> Pin alignment policy: this project tracks the portfolio canonical (coherent
> langchain 1.x with `<2` caps, `deepagents>=0.5.3,<0.6`, `requires-python =
> ">=3.11"`). See `guardkit/docs/guides/portfolio-python-pinning.md` and
> `docs/architecture/decisions/ADR-ARCH-011-langchain-1x-portfolio-alignment.md`.