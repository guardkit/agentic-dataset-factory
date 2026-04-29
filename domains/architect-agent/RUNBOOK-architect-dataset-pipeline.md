# Runbook: Architect Agent Dataset Factory — Full Pipeline

**Purpose:** Ingest 19 architecture books via Docling, then run the agentic-dataset-factory generation pipeline to produce ~2,200 training examples for the architect agent fine-tune.
**Machine:** Dell DGX Spark GB10 (`promaxgb10-41b1`), 128 GB unified memory
**Duration:** ~35-45 hours total (2-4h ingestion + 30-40h generation)
**Unattended:** Yes — all long-running processes run inside `tmux` sessions that survive SSH disconnect.

**Remote monitoring from MacBook:**
```bash
# Quick status check (run from MacBook terminal at any time)
ssh promaxgb10-41b1 'cat /tmp/architect-pipeline-status.txt'

# Watch generation progress live
ssh promaxgb10-41b1 'tail -f ~/Projects/appmilla_github/agentic-dataset-factory/run_logs/architect-*.log'

# Attach to the running tmux session (full interactive)
ssh -t promaxgb10-41b1 'tmux attach -t architect-pipeline'

# Detach from tmux without killing it: press Ctrl+B then D
```

---

## Phase 0: Transfer Files from MacBook to GB10

**Run these commands on the MacBook terminal (not Claude Code).**

### 0.1 Create target directories on GB10

```bash
ssh promaxgb10-41b1 'mkdir -p ~/Projects/appmilla_github/agentic-dataset-factory/domains/architect-agent/sources'
```

### 0.2 Transfer books

```bash
rsync -avP --partial \
  ~/Projects/appmilla_github/architecture_books/*.pdf \
  promaxgb10-41b1:~/Projects/appmilla_github/agentic-dataset-factory/domains/architect-agent/sources/
```

### 0.3 Transfer GOAL.md

```bash
rsync -avP --partial \
  ~/Projects/appmilla_github/agentic-dataset-factory/domains/architect-agent/GOAL.md \
  promaxgb10-41b1:~/Projects/appmilla_github/agentic-dataset-factory/domains/architect-agent/
```

### 0.4 Verify transfer

```bash
ssh promaxgb10-41b1 'ls -la ~/Projects/appmilla_github/agentic-dataset-factory/domains/architect-agent/sources/ | wc -l && echo "files transferred"'
# Expect: 20 (19 PDFs + header line)

ssh promaxgb10-41b1 'ls ~/Projects/appmilla_github/agentic-dataset-factory/domains/architect-agent/GOAL.md'
# Expect: file exists
```

**Phase 0 is complete when all 19 PDFs and GOAL.md are on the GB10. Everything below runs on the GB10.**

---

## Phase 1: Pre-flight Checks

### 1.1 Verify llama-swap is serving all models

```bash
echo "=== Checking llama-swap ==="
curl -s http://localhost:9000/v1/models | python3 -c "
import sys, json
resp = json.load(sys.stdin)
models = [m['id'] for m in resp.get('data', [])]
print(f'Models loaded: {len(models)}')
for m in models:
    print(f'  - {m}')
" 2>/dev/null || echo "ERROR: llama-swap not responding on :9000"
```

### 1.2 Verify source files arrived

```bash
echo "=== Checking source files ==="
SOURCES_DIR="$HOME/Projects/appmilla_github/agentic-dataset-factory/domains/architect-agent/sources"

PDF_COUNT=$(ls "$SOURCES_DIR"/*.pdf 2>/dev/null | wc -l)
echo "PDFs found: $PDF_COUNT (expect 19)"

if [ "$PDF_COUNT" -lt 19 ]; then
    echo "WARNING: Expected 19 PDFs, found $PDF_COUNT"
    echo "Missing files — compare with GOAL.md Source Documents table"
    ls "$SOURCES_DIR"/*.pdf
fi

# Check GOAL.md
[ -f "$HOME/Projects/appmilla_github/agentic-dataset-factory/domains/architect-agent/GOAL.md" ] && echo "GOAL.md: present" || echo "GOAL.md: MISSING"
```

### 1.3 Verify Docling is available

```bash
echo "=== Checking Docling ==="
python3 -c "from docling.document_converter import DocumentConverter; print('Docling: available')" 2>/dev/null || {
    echo "Docling not installed — installing..."
    pip install docling --break-system-packages
}
```

### 1.4 Verify ChromaDB is available

```bash
echo "=== Checking ChromaDB ==="
python3 -c "import chromadb; print('ChromaDB: available')" 2>/dev/null || {
    echo "ChromaDB not installed — installing..."
    pip install chromadb --break-system-packages
}
```

### 1.5 Check disk space

```bash
echo "=== Disk space ==="
df -h ~/Projects
# Need ~5 GB free for ChromaDB collection + output files
```

---

## Phase 2: Set Up tmux Session

Everything from here runs inside a tmux session so it survives SSH disconnect.

```bash
# Kill any existing session with this name
tmux kill-session -t architect-pipeline 2>/dev/null || true

# Create new session
tmux new-session -d -s architect-pipeline -x 200 -y 50

# Create named windows for different concerns
tmux rename-window -t architect-pipeline:0 'pipeline'
tmux new-window -t architect-pipeline -n 'monitor'
tmux new-window -t architect-pipeline -n 'logs'

# Set up the monitor window with a status loop
tmux send-keys -t architect-pipeline:monitor 'watch -n 30 "cat /tmp/architect-pipeline-status.txt 2>/dev/null || echo No status yet"' Enter

# Set up the logs window
tmux send-keys -t architect-pipeline:logs 'echo "Waiting for pipeline to start..." && sleep 5' Enter

echo "tmux session 'architect-pipeline' created with 3 windows: pipeline, monitor, logs"
echo "Attach with: tmux attach -t architect-pipeline"
echo "Detach with: Ctrl+B then D"
```

---

## Phase 3: Docling Ingestion (Stage 0)

### 3.1 Write the ingestion script

This handles both standard and VLM mode PDFs as specified in GOAL.md.

```bash
cat > /tmp/run-architect-ingestion.sh << 'INGESTION_SCRIPT'
#!/bin/bash
set -e

cd ~/Projects/appmilla_github/agentic-dataset-factory

DOMAIN="architect-agent"
SOURCES_DIR="domains/$DOMAIN/sources"
LOG_FILE="run_logs/architect-ingestion-$(date +%Y%m%d-%H%M%S).log"
STATUS_FILE="/tmp/architect-pipeline-status.txt"

mkdir -p run_logs

echo "=== Architect Agent Docling Ingestion ===" | tee "$LOG_FILE"
echo "Start time: $(date)" | tee -a "$LOG_FILE"
echo "Domain: $DOMAIN" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Write initial status
echo "STAGE: Ingestion (Stage 0)" > "$STATUS_FILE"
echo "Started: $(date)" >> "$STATUS_FILE"
echo "Status: Running" >> "$STATUS_FILE"

# VLM-mode files (scanned books)
VLM_FILES=(
    "tidy_first_scanned.pdf"
    "modern_software_engineering_scanned.pdf"
    "architecture_for_flow_scanned.pdf"
)

# Count files
TOTAL_FILES=$(ls "$SOURCES_DIR"/*.pdf 2>/dev/null | wc -l)
PROCESSED=0
FAILED=0

echo "Total PDFs to ingest: $TOTAL_FILES" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Check if the pipeline has its own ingestion command
if python3 -c "from ingestion import ingest" 2>/dev/null; then
    echo "Using pipeline's built-in ingestion module" | tee -a "$LOG_FILE"
    
    # Run the pipeline's ingestion for the domain
    PYTHONPATH=src python3 -c "
from ingestion.ingest import ingest_domain
ingest_domain('$DOMAIN')
" 2>&1 | tee -a "$LOG_FILE"

elif [ -f "ingestion/ingest.py" ]; then
    echo "Using ingestion/ingest.py script" | tee -a "$LOG_FILE"
    
    # Try running the ingestion script directly
    PYTHONPATH=src python3 ingestion/ingest.py --domain "$DOMAIN" 2>&1 | tee -a "$LOG_FILE"

elif [ -f "scripts/ingest.py" ]; then
    echo "Using scripts/ingest.py" | tee -a "$LOG_FILE"
    PYTHONPATH=src python3 scripts/ingest.py --domain "$DOMAIN" 2>&1 | tee -a "$LOG_FILE"

else
    echo "No ingestion script found — running Docling directly" | tee -a "$LOG_FILE"
    
    # Direct Docling ingestion with ChromaDB storage
    for PDF in "$SOURCES_DIR"/*.pdf; do
        FILENAME=$(basename "$PDF")
        PROCESSED=$((PROCESSED + 1))
        
        # Determine mode
        MODE="standard"
        for VLM in "${VLM_FILES[@]}"; do
            if [ "$FILENAME" = "$VLM" ]; then
                MODE="vlm"
                break
            fi
        done
        
        echo "[$PROCESSED/$TOTAL_FILES] Ingesting: $FILENAME (mode: $MODE)" | tee -a "$LOG_FILE"
        echo "STAGE: Ingestion | Progress: $PROCESSED/$TOTAL_FILES | Current: $FILENAME ($MODE)" > "$STATUS_FILE"
        
        # Run Docling
        if [ "$MODE" = "vlm" ]; then
            python3 -c "
from docling.document_converter import DocumentConverter
from docling.pipeline.vlm_pipeline import VlmPipeline
converter = DocumentConverter(pipeline_cls=VlmPipeline)
result = converter.convert('$PDF')
chunks = []
for item in result.document.iterate_items():
    text = item.export_to_text() if hasattr(item, 'export_to_text') else str(item)
    if text.strip():
        chunks.append(text.strip())
print(f'Chunks extracted: {len(chunks)}')
# Write chunks to a staging file for ChromaDB loading
import json
with open('$PDF.chunks.jsonl', 'w') as f:
    for i, chunk in enumerate(chunks):
        json.dump({'id': f'${FILENAME}-{i}', 'text': chunk, 'source': '$FILENAME', 'mode': 'vlm'}, f)
        f.write('\n')
" 2>&1 | tee -a "$LOG_FILE" || {
                echo "  FAILED: $FILENAME" | tee -a "$LOG_FILE"
                FAILED=$((FAILED + 1))
            }
        else
            python3 -c "
from docling.document_converter import DocumentConverter
converter = DocumentConverter()
result = converter.convert('$PDF')
chunks = []
for item in result.document.iterate_items():
    text = item.export_to_text() if hasattr(item, 'export_to_text') else str(item)
    if text.strip():
        chunks.append(text.strip())
print(f'Chunks extracted: {len(chunks)}')
import json
with open('$PDF.chunks.jsonl', 'w') as f:
    for i, chunk in enumerate(chunks):
        json.dump({'id': f'${FILENAME}-{i}', 'text': chunk, 'source': '$FILENAME', 'mode': 'standard'}, f)
        f.write('\n')
" 2>&1 | tee -a "$LOG_FILE" || {
                echo "  FAILED: $FILENAME" | tee -a "$LOG_FILE"
                FAILED=$((FAILED + 1))
            }
        fi
    done
    
    echo "" | tee -a "$LOG_FILE"
    echo "=== Loading chunks into ChromaDB ===" | tee -a "$LOG_FILE"
    echo "STAGE: Ingestion | Loading chunks into ChromaDB..." > "$STATUS_FILE"
    
    python3 -c "
import json, glob, os
import chromadb

client = chromadb.PersistentClient(path='chromadb')
collection = client.get_or_create_collection(
    name='architect-agent',
    metadata={'hnsw:space': 'cosine'}
)

chunk_files = sorted(glob.glob('$SOURCES_DIR/*.chunks.jsonl'))
total_chunks = 0

for cf in chunk_files:
    with open(cf) as f:
        chunks = [json.loads(line) for line in f if line.strip()]
    
    if chunks:
        # Batch insert (ChromaDB max batch = 5000)
        for i in range(0, len(chunks), 5000):
            batch = chunks[i:i+5000]
            collection.add(
                ids=[c['id'] for c in batch],
                documents=[c['text'] for c in batch],
                metadatas=[{'source': c['source'], 'mode': c['mode']} for c in batch]
            )
        total_chunks += len(chunks)
        print(f'  {os.path.basename(cf)}: {len(chunks)} chunks')

print(f'Total chunks loaded: {total_chunks}')
print(f'Collection count: {collection.count()}')
" 2>&1 | tee -a "$LOG_FILE"
    
    # Clean up staging files
    rm -f "$SOURCES_DIR"/*.chunks.jsonl
fi

echo "" | tee -a "$LOG_FILE"
echo "=== Ingestion Complete ===" | tee -a "$LOG_FILE"
echo "End time: $(date)" | tee -a "$LOG_FILE"
echo "Processed: $PROCESSED | Failed: $FAILED" | tee -a "$LOG_FILE"

# Update status
echo "STAGE: Ingestion COMPLETE" > "$STATUS_FILE"
echo "Finished: $(date)" >> "$STATUS_FILE"
echo "Processed: $PROCESSED / $TOTAL_FILES | Failed: $FAILED" >> "$STATUS_FILE"

# Verify collection
python3 -c "
import chromadb
client = chromadb.PersistentClient(path='chromadb')
try:
    coll = client.get_collection('architect-agent')
    print(f'ChromaDB collection \"architect-agent\": {coll.count()} chunks')
except Exception as e:
    print(f'ERROR: {e}')
" 2>&1 | tee -a "$LOG_FILE"
INGESTION_SCRIPT

chmod +x /tmp/run-architect-ingestion.sh
echo "Ingestion script written to /tmp/run-architect-ingestion.sh"
```

### 3.2 Run ingestion inside tmux

```bash
# Send the ingestion command to the pipeline window
tmux send-keys -t architect-pipeline:pipeline '/tmp/run-architect-ingestion.sh' Enter

# Point the logs window at the ingestion log
tmux send-keys -t architect-pipeline:logs 'sleep 5 && tail -f ~/Projects/appmilla_github/agentic-dataset-factory/run_logs/architect-ingestion-*.log' Enter

echo "Ingestion running in tmux session 'architect-pipeline'"
echo "Monitor: ssh promaxgb10-41b1 'cat /tmp/architect-pipeline-status.txt'"
echo "Attach:  ssh -t promaxgb10-41b1 'tmux attach -t architect-pipeline'"
```

### 3.3 Wait for ingestion to complete

```bash
# Poll until ingestion is done
while ! grep -q "Ingestion COMPLETE" /tmp/architect-pipeline-status.txt 2>/dev/null; do
    echo "$(date +%H:%M:%S) — $(cat /tmp/architect-pipeline-status.txt 2>/dev/null | head -1)"
    sleep 60
done

echo "Ingestion complete!"
cat /tmp/architect-pipeline-status.txt
```

### 3.4 Verify ChromaDB collection

```bash
cd ~/Projects/appmilla_github/agentic-dataset-factory

python3 -c "
import chromadb

client = chromadb.PersistentClient(path='chromadb')
coll = client.get_collection('architect-agent')

print(f'Collection: architect-agent')
print(f'Total chunks: {coll.count()}')

# Sample a query to verify retrieval works
results = coll.query(
    query_texts=['What is a Bounded Context in Domain-Driven Design?'],
    n_results=3
)

print(f'Test query returned: {len(results[\"documents\"][0])} results')
for i, doc in enumerate(results['documents'][0]):
    source = results['metadatas'][0][i].get('source', 'unknown')
    print(f'  [{i+1}] {source}: {doc[:100]}...')
"
```

**Pass:** Collection has 3,000+ chunks (19 books × ~150-300 chunks avg). Test query returns Evans DDD content.

---

## Phase 4: Run Generation Pipeline (Stage 1)

### 4.1 Write the generation launcher script

```bash
cat > /tmp/run-architect-generation.sh << 'GENERATION_SCRIPT'
#!/bin/bash
set -e

cd ~/Projects/appmilla_github/agentic-dataset-factory

DOMAIN="architect-agent"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="run_logs/architect-generation-${TIMESTAMP}.log"
STATUS_FILE="/tmp/architect-pipeline-status.txt"

mkdir -p run_logs output output/rag_index

echo "=== Architect Agent Generation Pipeline ===" | tee "$LOG_FILE"
echo "Start time: $(date)" | tee -a "$LOG_FILE"
echo "Domain: $DOMAIN" | tee -a "$LOG_FILE"
echo "Model endpoint: http://localhost:9000" | tee -a "$LOG_FILE"
echo "Expected targets: ~2,200" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Update status
echo "STAGE: Generation (Stage 1)" > "$STATUS_FILE"
echo "Started: $(date)" >> "$STATUS_FILE"
echo "Status: Running" >> "$STATUS_FILE"
echo "Targets: ~2,200" >> "$STATUS_FILE"
echo "Log: $LOG_FILE" >> "$STATUS_FILE"

# Set environment for local inference
export LLM_BASE_URL="http://localhost:9000/v1"
export LLM_MODEL="qwen36-workhorse"
export COACH_MODEL="qwen36-workhorse"
export EMBEDDING_BASE_URL="http://localhost:9000/v1"
export EMBEDDING_MODEL="nomic-embed"

# Enable LangSmith tracing if API key is available
if [ -n "$LANGSMITH_API_KEY" ]; then
    export LANGSMITH_TRACING=true
    export LANGSMITH_PROJECT="architect-agent-dataset-$(date +%Y%m%d)"
    echo "LangSmith tracing: enabled (project: $LANGSMITH_PROJECT)" | tee -a "$LOG_FILE"
else
    echo "LangSmith tracing: disabled (no API key)" | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"

# Run the pipeline
# Try the standard entry point patterns
if [ -f "agent.py" ]; then
    echo "Running via agent.py" | tee -a "$LOG_FILE"
    PYTHONPATH=src python3 agent.py --domain "$DOMAIN" 2>&1 | tee -a "$LOG_FILE"
elif [ -f "entrypoint/run.py" ]; then
    echo "Running via entrypoint/run.py" | tee -a "$LOG_FILE"
    PYTHONPATH=src python3 entrypoint/run.py --domain "$DOMAIN" 2>&1 | tee -a "$LOG_FILE"
elif [ -f "src/agentic_dataset_factory/main.py" ]; then
    echo "Running via src module" | tee -a "$LOG_FILE"
    PYTHONPATH=src python3 -m agentic_dataset_factory.main --domain "$DOMAIN" 2>&1 | tee -a "$LOG_FILE"
else
    echo "ERROR: Could not find pipeline entry point" | tee -a "$LOG_FILE"
    echo "Available files:" | tee -a "$LOG_FILE"
    find . -name "*.py" -maxdepth 2 -not -path "./.venv/*" | sort | tee -a "$LOG_FILE"
    exit 1
fi

# Update status on completion
echo "STAGE: Generation COMPLETE" > "$STATUS_FILE"
echo "Finished: $(date)" >> "$STATUS_FILE"

# Report results
echo "" | tee -a "$LOG_FILE"
echo "=== Generation Complete ===" | tee -a "$LOG_FILE"
echo "End time: $(date)" | tee -a "$LOG_FILE"

if [ -f "output/train.jsonl" ]; then
    BEHAVIOUR_COUNT=$(wc -l < output/train.jsonl)
    echo "Behaviour examples (train.jsonl): $BEHAVIOUR_COUNT" | tee -a "$LOG_FILE"
    echo "Behaviour examples: $BEHAVIOUR_COUNT" >> "$STATUS_FILE"
fi

if [ -f "output/rag_index/knowledge.jsonl" ]; then
    KNOWLEDGE_COUNT=$(wc -l < output/rag_index/knowledge.jsonl)
    echo "Knowledge examples (knowledge.jsonl): $KNOWLEDGE_COUNT" | tee -a "$LOG_FILE"
    echo "Knowledge examples: $KNOWLEDGE_COUNT" >> "$STATUS_FILE"
fi

if [ -f "output/rejected.jsonl" ]; then
    REJECTED_COUNT=$(wc -l < output/rejected.jsonl)
    echo "Rejected targets: $REJECTED_COUNT" | tee -a "$LOG_FILE"
    echo "Rejected: $REJECTED_COUNT" >> "$STATUS_FILE"
fi

TOTAL=$((${BEHAVIOUR_COUNT:-0} + ${KNOWLEDGE_COUNT:-0}))
echo "Total accepted: $TOTAL" | tee -a "$LOG_FILE"
echo "Total accepted: $TOTAL" >> "$STATUS_FILE"
GENERATION_SCRIPT

chmod +x /tmp/run-architect-generation.sh
echo "Generation script written to /tmp/run-architect-generation.sh"
```

### 4.2 Back up any existing output from the probe run

```bash
cd ~/Projects/appmilla_github/agentic-dataset-factory

if [ -f "output/train.jsonl" ] || [ -f "output/rag_index/knowledge.jsonl" ]; then
    BACKUP_DIR="output_backup_pre_architect_$(date +%Y%m%d)"
    echo "Backing up existing output to $BACKUP_DIR"
    cp -r output "$BACKUP_DIR"
    # Clear for the new run
    > output/train.jsonl 2>/dev/null || true
    > output/rag_index/knowledge.jsonl 2>/dev/null || true
    > output/rejected.jsonl 2>/dev/null || true
fi
```

### 4.3 Launch generation inside tmux

```bash
# Send the generation command to the pipeline window
tmux send-keys -t architect-pipeline:pipeline '/tmp/run-architect-generation.sh' Enter

# Update the logs window to follow the new log
tmux send-keys -t architect-pipeline:logs 'C-c' ''
tmux send-keys -t architect-pipeline:logs 'sleep 5 && tail -f ~/Projects/appmilla_github/agentic-dataset-factory/run_logs/architect-generation-*.log' Enter

echo "Generation running in tmux session 'architect-pipeline'"
echo ""
echo "=== REMOTE MONITORING FROM MACBOOK ==="
echo ""
echo "Quick status:"
echo "  ssh promaxgb10-41b1 'cat /tmp/architect-pipeline-status.txt'"
echo ""
echo "Watch progress live:"
echo "  ssh promaxgb10-41b1 'tail -f ~/Projects/appmilla_github/agentic-dataset-factory/run_logs/architect-generation-*.log'"
echo ""
echo "Check output counts:"
echo "  ssh promaxgb10-41b1 'wc -l ~/Projects/appmilla_github/agentic-dataset-factory/output/train.jsonl ~/Projects/appmilla_github/agentic-dataset-factory/output/rag_index/knowledge.jsonl ~/Projects/appmilla_github/agentic-dataset-factory/output/rejected.jsonl 2>/dev/null'"
echo ""
echo "Full interactive (attach to tmux):"
echo "  ssh -t promaxgb10-41b1 'tmux attach -t architect-pipeline'"
echo "  (Detach: Ctrl+B then D)"
echo ""
echo "Estimated completion: ~30-40 hours from now"
```

---

## Phase 5: Write Status Updater (runs alongside generation)

This script updates the status file every 60 seconds with live output counts so Rich can check remotely.

```bash
cat > /tmp/architect-status-updater.sh << 'STATUS_SCRIPT'
#!/bin/bash
cd ~/Projects/appmilla_github/agentic-dataset-factory

while true; do
    # Only update if generation is running
    if pgrep -f "architect-agent" > /dev/null 2>&1 || pgrep -f "agent.py" > /dev/null 2>&1; then
        BEHAVIOUR=$(wc -l < output/train.jsonl 2>/dev/null || echo 0)
        KNOWLEDGE=$(wc -l < output/rag_index/knowledge.jsonl 2>/dev/null || echo 0)
        REJECTED=$(wc -l < output/rejected.jsonl 2>/dev/null || echo 0)
        TOTAL=$((BEHAVIOUR + KNOWLEDGE))
        
        # Estimate completion
        ELAPSED_HOURS=$(python3 -c "
import os, time
log_files = sorted([f for f in os.listdir('run_logs') if f.startswith('architect-generation')])
if log_files:
    mtime = os.path.getmtime(f'run_logs/{log_files[0]}')
    hours = (time.time() - os.path.getctime(f'run_logs/{log_files[0]}')) / 3600
    rate = $TOTAL / max(hours, 0.01)
    remaining = max(0, (2200 - $TOTAL) / max(rate, 0.1))
    print(f'{hours:.1f}h elapsed, ~{rate:.0f}/h, ~{remaining:.1f}h remaining')
else:
    print('calculating...')
" 2>/dev/null || echo "calculating...")
        
        cat > /tmp/architect-pipeline-status.txt << EOF
STAGE: Generation (Stage 1)
Updated: $(date '+%Y-%m-%d %H:%M:%S')
Progress: $TOTAL / 2200 targets ($((TOTAL * 100 / 2200))%)
  Behaviour (train.jsonl):     $BEHAVIOUR
  Knowledge (knowledge.jsonl): $KNOWLEDGE
  Rejected:                    $REJECTED
Timing: $ELAPSED_HOURS
EOF
    fi
    sleep 60
done
STATUS_SCRIPT

chmod +x /tmp/architect-status-updater.sh

# Run the status updater in the background within tmux
tmux send-keys -t architect-pipeline:monitor 'C-c' ''
tmux send-keys -t architect-pipeline:monitor '/tmp/architect-status-updater.sh' Enter

echo "Status updater running — check with: ssh promaxgb10-41b1 'cat /tmp/architect-pipeline-status.txt'"
```

---

## Phase 6: Post-Generation Validation (run after Stage 1 completes)

### 6.1 Output summary

```bash
cd ~/Projects/appmilla_github/agentic-dataset-factory

echo "=== Generation Results ==="
echo ""

BEHAVIOUR=$(wc -l < output/train.jsonl 2>/dev/null || echo 0)
KNOWLEDGE=$(wc -l < output/rag_index/knowledge.jsonl 2>/dev/null || echo 0)
REJECTED=$(wc -l < output/rejected.jsonl 2>/dev/null || echo 0)
TOTAL=$((BEHAVIOUR + KNOWLEDGE))

echo "Behaviour examples (train.jsonl):     $BEHAVIOUR"
echo "Knowledge examples (knowledge.jsonl): $KNOWLEDGE"
echo "Rejected targets:                     $REJECTED"
echo "Total accepted:                       $TOTAL"
echo "Acceptance rate:                      $(python3 -c "print(f'{$TOTAL/max($TOTAL+$REJECTED,1)*100:.1f}%')")"
```

### 6.2 Spot-check quality

```bash
echo "=== Sample behaviour example ==="
head -1 output/train.jsonl | python3 -c "
import sys, json
ex = json.loads(sys.stdin.readline())
msgs = ex['messages']
meta = ex.get('metadata', {})
print(f'Dimension: {meta.get(\"dimension\", \"unknown\")}')
print(f'Topic: {meta.get(\"topic\", \"unknown\")}')
print(f'Books: {meta.get(\"source_books\", [])}')
print(f'Turns: {meta.get(\"turns\", 1)}')
print()
for m in msgs:
    role = m['role']
    content = m['content'][:300]
    print(f'[{role}]: {content}...')
    print()
"

echo ""
echo "=== Sample knowledge example ==="
head -1 output/rag_index/knowledge.jsonl | python3 -c "
import sys, json
ex = json.loads(sys.stdin.readline())
msgs = ex['messages']
meta = ex.get('metadata', {})
print(f'Dimension: {meta.get(\"dimension\", \"unknown\")}')
print(f'Topic: {meta.get(\"topic\", \"unknown\")}')
print(f'Books: {meta.get(\"source_books\", [])}')
print()
for m in msgs:
    role = m['role']
    content = m['content'][:300]
    print(f'[{role}]: {content}...')
    print()
"
```

### 6.3 Check for template-token leaks

```bash
echo "=== Checking for template-token leaks ==="
LEAK_COUNT=$(grep -c '<|channel>\|<channel|>\|<|turn>\|<turn|>' output/train.jsonl 2>/dev/null || echo 0)
echo "Template token leaks in train.jsonl: $LEAK_COUNT"

LEAK_COUNT_K=$(grep -c '<|channel>\|<channel|>\|<|turn>\|<turn|>' output/rag_index/knowledge.jsonl 2>/dev/null || echo 0)
echo "Template token leaks in knowledge.jsonl: $LEAK_COUNT_K"

if [ "$LEAK_COUNT" -gt 0 ] || [ "$LEAK_COUNT_K" -gt 0 ]; then
    echo "WARNING: Template tokens found in output. Review before fine-tuning."
else
    echo "CLEAN: No template token leaks."
fi
```

### 6.4 Check think block presence

```bash
echo "=== Checking <think> block presence ==="
TOTAL_EXAMPLES=$(wc -l < output/train.jsonl 2>/dev/null || echo 0)
THINK_COUNT=$(grep -c '<think>' output/train.jsonl 2>/dev/null || echo 0)
echo "Behaviour examples with <think> blocks: $THINK_COUNT / $TOTAL_EXAMPLES"

TOTAL_K=$(wc -l < output/rag_index/knowledge.jsonl 2>/dev/null || echo 0)
THINK_K=$(grep -c '<think>' output/rag_index/knowledge.jsonl 2>/dev/null || echo 0)
echo "Knowledge examples with <think> blocks: $THINK_K / $TOTAL_K"

# All should have think blocks (100% reasoning type)
if [ "$THINK_COUNT" -eq "$TOTAL_EXAMPLES" ] && [ "$THINK_K" -eq "$TOTAL_K" ]; then
    echo "PASS: All examples have <think> blocks"
else
    echo "WARNING: Some examples missing <think> blocks"
fi
```

### 6.5 Rejection analysis

```bash
echo "=== Rejection analysis ==="
if [ -f output/rejected.jsonl ] && [ -s output/rejected.jsonl ]; then
    python3 -c "
import json
with open('output/rejected.jsonl') as f:
    rejected = [json.loads(line) for line in f if line.strip()]

reasons = {}
for r in rejected:
    reason = r.get('reason', 'unknown')
    reasons[reason] = reasons.get(reason, 0) + 1

print(f'Total rejected: {len(rejected)}')
for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
    print(f'  {reason}: {count}')
"
else
    echo "No rejections (or rejected.jsonl is empty)"
fi
```

### 6.6 Update final status

```bash
cat > /tmp/architect-pipeline-status.txt << EOF
STAGE: PIPELINE COMPLETE
Finished: $(date)
Behaviour examples: $(wc -l < output/train.jsonl 2>/dev/null || echo 0)
Knowledge examples: $(wc -l < output/rag_index/knowledge.jsonl 2>/dev/null || echo 0)
Rejected: $(wc -l < output/rejected.jsonl 2>/dev/null || echo 0)
Template leaks: $(grep -c '<|channel>' output/train.jsonl 2>/dev/null || echo 0)
Think blocks: $(grep -c '<think>' output/train.jsonl 2>/dev/null || echo 0) / $(wc -l < output/train.jsonl 2>/dev/null || echo 0)
NEXT: Review output quality, then fine-tune with train_gemma4_moe.py --chat-template gemma-4
EOF

echo ""
cat /tmp/architect-pipeline-status.txt
```

---

## Quick Reference — Remote Monitoring Commands

Copy these to a note on your phone or laptop for checking while away:

```bash
# One-liner status check
ssh promaxgb10-41b1 'cat /tmp/architect-pipeline-status.txt'

# Output counts
ssh promaxgb10-41b1 'wc -l ~/Projects/appmilla_github/agentic-dataset-factory/output/*.jsonl ~/Projects/appmilla_github/agentic-dataset-factory/output/rag_index/*.jsonl 2>/dev/null'

# Last 20 log lines
ssh promaxgb10-41b1 'tail -20 ~/Projects/appmilla_github/agentic-dataset-factory/run_logs/architect-generation-*.log 2>/dev/null | tail -20'

# Is the pipeline still running?
ssh promaxgb10-41b1 'pgrep -fa "architect\|agent.py" || echo "Pipeline not running"'

# GPU status
ssh promaxgb10-41b1 'nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv'

# Full interactive session
ssh -t promaxgb10-41b1 'tmux attach -t architect-pipeline'
# Detach: Ctrl+B then D
```

---

## Appendix: If Pipeline Fails Mid-Run

The agentic-dataset-factory pipeline writes accepted examples incrementally to `train.jsonl` and `knowledge.jsonl`. If it crashes mid-run:

1. Check the log: `tail -100 run_logs/architect-generation-*.log`
2. Existing accepted output is preserved — the pipeline appends, not overwrites
3. Re-running should resume from where it left off (check pipeline's `--resume` flag or equivalent)
4. If llama-swap crashed, the keep-alive timer should have revived it (check `systemctl --user status llama-swap`)

---

*Runbook: Architect Dataset Factory Pipeline*
*Prepared: 2026-04-29*
*Cross-references: domains/architect-agent/GOAL.md, probe-findings.md, RUNBOOK-v3-production-deployment.md*
