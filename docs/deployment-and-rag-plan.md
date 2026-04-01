# Deployment & RAG Plan — Getting Early Value

## Context

The agentic dataset factory is generating fine-tuning data. Once complete, the goal is to
get the fine-tuned model into the hands of the end user (daughter, homework help) as quickly
as possible, then layer on RAG and eventually the full agent system.

## Stage 1: Fine-Tuned Model + Chat Interface

### Pipeline

1. Fine-tune with **Unsloth** once the dataset run completes
2. Export to **GGUF** format (Unsloth supports this directly)
3. Host on the **GB10 (DGX Spark)** via **Ollama**
4. Deploy **Open WebUI** — provides a ChatGPT-like interface accessible from phone or laptop
5. Access via `http://<gb10-tailscale-ip>:8080` in a browser

### What the model does well without RAG

- Responds in the right tone/style for the target user
- Understands domain vocabulary
- Follows pedagogical patterns baked into the training data (scaffolding, encouragement, age-appropriate explanations)

### What it won't do well without RAG

- Reference specific curriculum content currently being studied
- Track progress over time
- Adapt to what was got wrong last week

The fine-tuned model provides the **personality and teaching style**. RAG provides the **specific knowledge and memory**.

## Stage 2: Adding RAG (No Agent Required)

Open WebUI has **built-in RAG** capabilities. No custom agent is needed for this stage.

### Open WebUI Native RAG Features

- **Document upload** — PDFs, Word docs, text files
- **Knowledge collections** — group documents by subject (Maths, Science, English, etc.)
- Built-in chunking and embedding
- Uses a local embedding model via Ollama (e.g. `nomic-embed-text`)

### Setup

1. Ollama running the fine-tuned model + an embedding model (`nomic-embed-text`)
2. Open WebUI pointed at Ollama
3. Upload textbooks/revision guides as "Knowledge" collections
4. User picks the relevant collection when chatting

### Using Docling for Better Quality

Open WebUI's built-in PDF parsing is decent but basic. Since Docling is already working
in this project, the recommended approach is:

- **Simple path**: Upload PDFs directly into Open WebUI, let it handle everything
- **Better path** (recommended): Use Docling to extract clean text/markdown from PDFs first,
  then upload those into Open WebUI — better chunking, better retrieval results, especially
  for textbooks with tables/diagrams

### Practical Steps (achievable in an afternoon once the fine-tune is ready)

1. Deploy Ollama + Open WebUI on GB10
2. Run textbook PDFs through Docling for clean extraction
3. Upload extracted content into Open WebUI Knowledge collections
4. RAG is working — user can chat with the model about her actual curriculum

## Stage 3: Custom Agent (Future)

An agent becomes valuable when the limits of Open WebUI are reached. Specifically:

- **Progress tracking** — "what does she struggle with?"
- **Adaptive difficulty / gamification** — adjust challenge level over time
- **Multi-step tutoring workflows** — Socratic method, not just Q&A
- **Integration with Ricci Mini robot** — physical interaction layer
- **Knowledge graph for long-term memory** — context that persists across sessions
- **Mobile app** — custom interface beyond what Open WebUI provides

## Summary: Incremental Value Path

| Stage | What the user gets | Effort |
|-------|-------------------|--------|
| **1. Chat** | Fine-tuned model + Open WebUI chat interface | Low — just deploy |
| **2. Document upload** | Drag in homework/notes, ask questions about them | Zero — built into Open WebUI |
| **3. RAG** | Textbooks/revision guides as searchable Knowledge collections | Low — Docling + upload |
| **4. Full system** | Deep agent + knowledge graph + progress tracking + gamification + Ricci Mini | Full build |

Each stage is independently useful. Feedback from early stages directly improves later ones.
