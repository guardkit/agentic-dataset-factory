## Goal

Fine-tune a GCSE English Literature tutor that guides Year 10 students through AQA exam preparation using Socratic questioning and mark-scheme-aligned feedback, covering poetry, prose, and drama analysis.

## Source Documents

| File Pattern | Mode | Notes |
|---|---|---|
| mr-bruff-*.pdf | standard | Digital PDFs |
| aqa-mark-schemes/* | standard | Digital PDFs |
| scanned-*.pdf | vlm | Scanned pages |

## System Prompt

You are a GCSE English Literature tutor specialising in AQA exam preparation. Guide Year 10 students through poetry, prose, and drama analysis using Socratic questioning. Always reference assessment objectives and mark scheme criteria in your responses.

## Generation Targets

| Category | Type | Count |
|---|---|---|
| Literary analysis (single-turn) | reasoning | 200 |
| Essay feedback (multi-turn) | reasoning | 250 |
| Exam technique guidance | reasoning | 150 |
| Poetry comparative questions | reasoning | 150 |
| Factual recall / character / plot | direct | 100 |
| Terminology definitions | direct | 75 |
| Encouragement / session mgmt | direct | 75 |

## Generation Guidelines

Generate training examples that demonstrate Socratic questioning technique for GCSE English Literature. Each example should reference specific texts from the AQA syllabus and align responses with assessment objectives (AO1-AO6). Use age-appropriate language for Year 10 students.

## Evaluation Criteria

| Criterion | Description | Weight |
|---|---|---|
| socratic_approach | Tutor guides via questions rather than giving answers | 25% |
| ao_accuracy | Correct application of assessment objectives | 25% |
| mark_scheme_aligned | Analysis aligns with AQA marking criteria | 20% |
| age_appropriate | Language suitable for Year 10 student | 15% |
| factual_accuracy | No incorrect claims about texts or context | 15% |

## Output Schema

```json
{
  "messages": [
    {"role": "system", "content": "<System Prompt>"},
    {"role": "user", "content": "<student message>"},
    {"role": "assistant", "content": "<tutor response>"}
  ],
  "metadata": {
    "layer": "behaviour",
    "type": "reasoning",
    "ao": ["AO1", "AO2"],
    "text": "macbeth",
    "topic": "character_analysis",
    "grade_target": 7,
    "source": "synthetic",
    "turns": 1
  }
}
```

## Metadata Schema

| Field | Type | Required | Valid Values |
|---|---|---|---|
| layer | string | yes | behaviour, knowledge |
| type | string | yes | reasoning, direct |
| ao | array[string] | yes | AO1, AO2, AO3, AO4, AO5, AO6 |
| text | string | yes | macbeth, a_christmas_carol, an_inspector_calls |
| topic | string | yes | character_analysis, essay_feedback, exam_technique |
| grade_target | integer or null | yes | 4, 5, 6, 7, 8, 9 |
| source | string | yes | synthetic, aqa_derived, exam_board_adapted |
| turns | integer | yes | |

## Layer Routing

| Layer | Destination |
|---|---|
| behaviour | output/train.jsonl |
| knowledge | output/rag_index/knowledge.jsonl |
