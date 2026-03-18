# Graphiti Knowledge Graph — Usage Guide

## Overview

This project has a Graphiti MCP server connected to a FalkorDB knowledge graph.
The graph contains seeded project knowledge about GuardKit architecture, workflows,
and design decisions. **You must query it correctly to retrieve results.**

## Critical: Always Pass group_ids

Knowledge is partitioned by `group_id`. Searching without `group_ids` returns nothing.
Always pass all three group IDs when searching:

```python
group_ids = ["product_knowledge", "command_workflows", "architecture_decisions"]
```

### What each group contains

| Group ID | Contents |
|----------|----------|
| `product_knowledge` | GuardKit product context, quality gates, target users, installation |
| `command_workflows` | Slash commands, Player-Coach workflow, feature-build pipeline |
| `architecture_decisions` | ADRs (ADR-FB-002, ADR-FB-003), worktree architecture, task delegation |

## Search Tools

Use both search tools together for comprehensive results:

- `mcp__graphiti__search_nodes` — finds entities (concepts, components, roles)
- `mcp__graphiti__search_memory_facts` — finds relationships between entities

Always search with **all three group_ids** unless you have a specific reason to filter.

## Adding Knowledge

Use `mcp__graphiti__add_memory` with:
- `source`: `"text"`, `"json"`, or `"message"`
- `group_id`: one of the three group IDs above (pick the most appropriate)
- Provide descriptive `name` and `source_description` for better retrieval

## Configuration Reference

- Server config: see `.mcp.json` for MCP server launch configuration
- Project config: see `.guardkit/graphiti.yaml` for group_ids and infrastructure details
- Graph database: FalkorDB on `whitestocks:6379` (Synology NAS via Tailscale)
- LLM backend: vLLM on `promaxgb10-41b1` (Qwen2.5-14B for extraction, nomic-embed for embeddings)
