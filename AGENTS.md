# Agent Boundaries — agentic-dataset-factory

## Player Agent

### ALWAYS
- Use `rag_retrieval` tool to find relevant curriculum content before generating any training example
- Use `write_output` tool to persist every accepted training example
- Include `<think>` blocks in all reasoning-type examples (75% of dataset)
- Follow the ShareGPT conversation format: system → user → assistant
- Include all required metadata fields as defined in GOAL.md Metadata Schema
- Ground training examples in AQA specification content and mark scheme criteria

### NEVER
- Generate training examples without first consulting source material via RAG
- Skip metadata fields or use values outside the defined valid values
- Include `<think>` blocks in direct-type examples
- Generate content that is factually incorrect about literary texts or AQA criteria
- Produce content inappropriate for Year 10 students (age 14-15)

### ASK
- If unsure about the correct AO (Assessment Objective) for a given question type
- If the RAG retrieval returns insufficient context for the target category

## Coach Agent

### ALWAYS
- Return structured JSON verdict matching the CoachVerdict schema exactly
- Evaluate against ALL criteria from GOAL.md Evaluation Criteria section
- Check layer routing correctness (behaviour vs knowledge)
- Check type correctness (reasoning vs direct) matches think block presence
- Provide actionable feedback in the quality_assessment field when rejecting

### NEVER
- Write files or call any tools (Coach has no tools by design — D5 invariant)
- Accept examples with missing or invalid metadata fields
- Accept examples where metadata.type does not match think block presence
- Return unstructured text instead of JSON verdict

### ASK
- N/A — Coach operates autonomously within its evaluation rubric
