# Graphiti MCP Setup for Claude Code

How to connect Graphiti's knowledge graph to any Claude Code project, enabling
persistent memory across sessions via MCP (Model Context Protocol).

## Prerequisites

- **Graphiti MCP server** cloned locally (e.g. at `~/Projects/appmilla_github/graphiti/`)
- **FalkorDB** running and accessible (we use a Synology NAS at `whitestocks:6379` via Tailscale)
- **vLLM** serving an LLM and embedding model (we use `promaxgb10-41b1` with two endpoints)
- **uv** installed (used to run the MCP server)

### Infrastructure Summary

| Component | Host | Purpose |
|-----------|------|---------|
| FalkorDB | `whitestocks:6379` | Graph database (Redis-compatible, runs on Synology DS918+ NAS) |
| vLLM LLM | `promaxgb10-41b1:8000` | Entity/relationship extraction (Qwen2.5-14B-Instruct-FP8) |
| vLLM Embeddings | `promaxgb10-41b1:8001` | Embedding generation (nomic-embed-text-v1.5, 1024 dims) |

## Step 1: Create the Graphiti Server Config

Create a YAML config for the Graphiti MCP server. This lives in the Graphiti repo,
not your project. Example at `graphiti/mcp_server/config/config-guardkit.yaml`:

```yaml
server:
  transport: "stdio"

llm:
  provider: "openai"
  model: "neuralmagic/Qwen2.5-14B-Instruct-FP8-dynamic"
  max_tokens: 4096
  providers:
    openai:
      api_key: ${OPENAI_API_KEY}
      api_url: ${LLM_API_URL:http://promaxgb10-41b1:8000/v1}

embedder:
  provider: "openai"
  model: "nomic-embed-text-v1.5"
  dimensions: 1024
  providers:
    openai:
      api_key: ${OPENAI_API_KEY}
      api_url: ${EMBEDDING_API_URL:http://promaxgb10-41b1:8001/v1}

database:
  provider: "falkordb"
  providers:
    falkordb:
      uri: "redis://whitestocks:6379"
      password: ""
      database: "default_db"

graphiti:
  group_id: "guardkit"
  user_id: "rich"
  entity_types:
    - name: "Preference"
      description: "User preferences, choices, opinions, or selections"
    - name: "Requirement"
      description: "Specific needs, features, or functionality that must be fulfilled"
    - name: "Procedure"
      description: "Standard operating procedures and sequential instructions"
    - name: "Location"
      description: "Physical or virtual places where activities occur"
    - name: "Event"
      description: "Time-bound activities, occurrences, or experiences"
    - name: "Organization"
      description: "Companies, institutions, groups, or formal entities"
    - name: "Document"
      description: "Information content in various forms (books, articles, reports, etc.)"
    - name: "Topic"
      description: "Subject of conversation, interest, or knowledge domain"
    - name: "Object"
      description: "Physical items, tools, devices, or possessions"
```

Key points:
- `provider: "openai"` is used because vLLM exposes an OpenAI-compatible API
- `OPENAI_API_KEY` is set to a dummy value since vLLM doesn't need a real key
- `group_id` is the default partition — but seeded data may use different group_ids
- `entity_types` define the categories Graphiti uses for entity extraction

## Step 2: Add `.mcp.json` to Your Project

Create `.mcp.json` in your project root. This tells Claude Code to launch the
Graphiti MCP server when opening this project:

```json
{
  "mcpServers": {
    "graphiti": {
      "type": "stdio",
      "command": "/opt/homebrew/bin/uv",
      "args": [
        "--directory",
        "/Users/richardwoollcott/Projects/appmilla_github/graphiti/mcp_server",
        "run",
        "main.py",
        "--transport",
        "stdio",
        "--config",
        "/Users/richardwoollcott/Projects/appmilla_github/graphiti/mcp_server/config/config-guardkit.yaml"
      ],
      "env": {
        "CONFIG_PATH": "/Users/richardwoollcott/Projects/appmilla_github/graphiti/mcp_server/config/config-guardkit.yaml",
        "OPENAI_API_KEY": "not-needed-vllm-local",
        "LLM_API_URL": "http://promaxgb10-41b1:8000/v1",
        "EMBEDDING_API_URL": "http://promaxgb10-41b1:8001/v1",
        "EMBEDDING_DIM": "1024"
      }
    }
  }
}
```

Key points:
- `command` uses the full path to `uv` (adjust for your system)
- `--directory` points to the Graphiti MCP server source
- `--config` points to the server config from Step 1
- Environment variables are passed through to the server process

## Step 3: Create `.guardkit/graphiti.yaml` (Project-Level Config)

This file stores project-specific Graphiti settings, including the `group_ids`
that partition your knowledge:

```yaml
project_id: your-project-name
enabled: true
graph_store: falkordb
falkordb_host: whitestocks
falkordb_port: 6379
timeout: 30.0
max_concurrent_episodes: 3
llm_provider: vllm
llm_base_url: http://promaxgb10-41b1:8000/v1
llm_model: neuralmagic/Qwen2.5-14B-Instruct-FP8-dynamic
embedding_provider: vllm
embedding_base_url: http://promaxgb10-41b1:8001/v1
embedding_model: nomic-embed-text-v1.5
group_ids:
- product_knowledge
- command_workflows
- architecture_decisions
```

## Step 4: Add Graphiti Instructions to CLAUDE.md

This is the critical step that ensures Claude Code **actually uses the correct
group_ids** when searching. Without this, searches return empty results.

Add to your project's `.claude/CLAUDE.md`:

```markdown
## Knowledge Graph (Graphiti)

This project has a Graphiti MCP server providing a persistent knowledge graph.
**When searching, always pass `group_ids: ["product_knowledge", "command_workflows", "architecture_decisions"]`** —
searching without group_ids returns empty results.

For full usage details, see `.claude/rules/graphiti-knowledge-graph.md`.
```

## Step 5: Create the Detailed Rules File

Create `.claude/rules/graphiti-knowledge-graph.md` with search instructions,
group_id descriptions, and usage examples. This file is loaded automatically
by Claude Code when relevant and provides the detailed guidance that CLAUDE.md
points to.

See the working example in this project at
[.claude/rules/graphiti-knowledge-graph.md](../../.claude/rules/graphiti-knowledge-graph.md).

## Verification

Start a new Claude Code session in the project and test:

1. **Check connection**: Ask Claude to call `mcp__graphiti__get_status`
2. **Search with group_ids**: Ask Claude to search for a term you've seeded
3. **Confirm results**: Verify nodes and facts are returned (not empty)

If searches return empty, check:
- Are the `group_ids` being passed? (most common issue)
- Is FalkorDB accessible from your machine?
- Is vLLM running on both ports (8000 for LLM, 8001 for embeddings)?
- Has knowledge actually been seeded into those group_ids?

## Files Created/Modified

| File | Purpose |
|------|---------|
| `.mcp.json` | MCP server launch config (Claude Code reads this) |
| `.guardkit/graphiti.yaml` | Project-level Graphiti config with group_ids |
| `.claude/CLAUDE.md` | Added Graphiti section with group_ids instruction |
| `.claude/rules/graphiti-knowledge-graph.md` | Detailed search/usage guide |

## Gotchas

1. **group_ids are mandatory** — The server config has a `group_id: "guardkit"` default,
   but seeded data uses domain-specific group_ids (`product_knowledge`, etc.).
   Always pass all relevant group_ids when searching.

2. **Episodes may appear empty** — `get_episodes` can return empty even when nodes
   and facts exist. Use `search_nodes` and `search_memory_facts` for retrieval.

3. **Server config vs project config** — The server config (`config-guardkit.yaml`)
   lives in the Graphiti repo and is shared. The project config (`.guardkit/graphiti.yaml`)
   is per-project and defines which group_ids to search.

4. **Paths are absolute** — The `.mcp.json` uses absolute paths to `uv`, the Graphiti
   repo, and the config file. These need adjusting per machine.
