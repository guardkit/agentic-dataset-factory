# GB10 Rsync Cheat Sheet

Quick reference for syncing between Mac and GB10. Run all commands from the Mac.

## Sync code (excludes data)

```bash
rsync -avz --exclude '.venv' --exclude '__pycache__' \
    --exclude 'chroma_data' --exclude 'output' \
    ~/Projects/appmilla_github/agentic-dataset-factory/ \
    promaxgb10-41b1:~/Projects/appmilla_github/agentic-dataset-factory/
```

## Sync ChromaDB (run after every code sync)

```bash
rsync -avz ~/Projects/appmilla_github/agentic-dataset-factory/chroma_data/ \
    promaxgb10-41b1:~/Projects/appmilla_github/agentic-dataset-factory/chroma_data/
```

Verify: `ssh promaxgb10-41b1 'ls -lh ~/Projects/appmilla_github/agentic-dataset-factory/chroma_data/chroma.sqlite3'`
Expected: ~16MB. If 184K, the collection is empty — re-sync or re-ingest.

## Sync output data (Mac to GB10)

```bash
rsync -avz ~/Projects/appmilla_github/agentic-dataset-factory/output/ \
    promaxgb10-41b1:~/Projects/appmilla_github/agentic-dataset-factory/output/
```

## Pull results back (GB10 to Mac)

```bash
rsync -avz promaxgb10-41b1:~/Projects/appmilla_github/agentic-dataset-factory/output/ \
    ~/Projects/appmilla_github/agentic-dataset-factory/output/
```

## Full deploy (all three in sequence)

```bash
# 1. Code
rsync -avz --exclude '.venv' --exclude '__pycache__' \
    --exclude 'chroma_data' --exclude 'output' \
    ~/Projects/appmilla_github/agentic-dataset-factory/ \
    promaxgb10-41b1:~/Projects/appmilla_github/agentic-dataset-factory/

# 2. ChromaDB
rsync -avz ~/Projects/appmilla_github/agentic-dataset-factory/chroma_data/ \
    promaxgb10-41b1:~/Projects/appmilla_github/agentic-dataset-factory/chroma_data/

# 3. Output (only if seeding GB10 with existing data)
rsync -avz ~/Projects/appmilla_github/agentic-dataset-factory/output/ \
    promaxgb10-41b1:~/Projects/appmilla_github/agentic-dataset-factory/output/
```
