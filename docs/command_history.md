/system-arch \
  --from docs/research/agentic-dataset-factory-conversation-starter.md \
  --context docs/research/gcse-tutor-training-data-format.md


/system-design --from docs/architecture/ARCHITECTURE.md --context docs/research/agentic-dataset-factory-conversation-starter.md --context docs/research/gcse-tutor-training-data-format.md


/system-plan \
  --from docs/design/DESIGN.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/research/agentic-dataset-factory-conversation-starter.md \
  --context docs/research/gcse-tutor-training-data-format.md


Phase 2: agentic-dataset-factory Pipeline (6 features, one per module)
Feature 2 — Domain Config & GOAL.md Validation


/feature-spec "Domain Config module: GOAL.md parser and strict validation" \
  --context docs/design/contracts/API-domain-config.md \
  --context docs/design/models/DM-goal-schema.md
Covers: GoalConfig parser, 9-section validation, GoalValidationError. Foundation for all other modules.

Feature 3 — Ingestion Pipeline


/feature-spec "Ingestion pipeline: Docling PDF processing to ChromaDB" \
  --context docs/design/contracts/API-ingestion.md \
  --context docs/design/contracts/API-domain-config.md
Covers: ingestion/ingest.py CLI, ingestion/chunker.py, ChromaDB collection lifecycle. Depends on Feature 2 (reads Source Documents from GOAL.md).

Feature 4 — Tools (rag_retrieval + write_output)


/feature-spec "LangChain tools: rag_retrieval and write_output with layer routing" \
  --context docs/design/contracts/API-tools.md \
  --context docs/design/contracts/API-output.md
Covers: tools/rag_retrieval.py, tools/write_output.py, schema validation, layer routing. Depends on Feature 3 (ChromaDB populated).

Feature 5 — Agent Factories (Player + Coach)


/feature-spec "Agent factories: Player and Coach via create_deep_agent" \
  --context docs/design/contracts/API-generation.md \
  --context docs/design/models/DM-coach-rejection.md
Covers: agents/player.py, agents/coach.py, prompt injection from GOAL.md, Coach rejection schema. Depends on Feature 4 (tools).

Feature 6 — Entrypoint & Generation Loop


/feature-spec "Entrypoint: config loading, validation, and generation loop orchestration" \
  --context docs/design/contracts/API-entrypoint.md \
  --context docs/design/models/DM-agent-config.md \
  --context docs/architecture/decisions/ADR-ARCH-010-overnight-run-resilience.md
Covers: agent.py, agent-config.yaml loading, 12-step startup, sequential generation loop, --resume flag, retry/backoff/timeout (ADR-ARCH-010). Depends on Features 2-5.

Feature 7 — GCSE English Tutor Domain Config


/feature-spec "GCSE English tutor GOAL.md: first domain configuration" \
  --context docs/research/gcse-tutor-training-data-format.md \
  --context docs/design/contracts/API-domain-config.md
Covers: domains/gcse-english-tutor/GOAL.md (all 9 sections populated), generation-plan.yaml. This is the content that drives the pipeline — not code, but needs acceptance criteria.


hi can you check the docs for hosting the gemma4 moe fine-tuned model which I think we have in the repo I just can't remember where

Found it. The hosting docs live in tasks/backlog/gemma4-moe-deploy/:

README.md — overview
IMPLEMENTATION-GUIDE.md — full deploy guide
TASK-G4D-001-transfer-gguf-to-macbook.md — rsync the GGUF
TASK-G4D-002-register-ollama-and-smoke-test.md — register in Ollama
TASK-G4D-003-setup-chromarag-and-openwebui.md — ChromaRAG + OpenWebUI
rsync-copy.md — the file you have open
Want me to open the README or IMPLEMENTATION-GUIDE and summarize?

I just tried Step 1 in TASK-G4D-002 but it failed with this output:
richardwoollcott@Richards-MBP ~ % cat ~/Models/gcse-tutor-gemma4-26b-moe/Modelfile
# If FROM points to DGX path, fix it:
sed -i '' 's|FROM .*|FROM ./gemma-4-26b-a4b-it.Q4_K_M.gguf|' \
  ~/Models/gcse-tutor-gemma4-26b-moe/Modelfile

FROM .
TEMPLATE """{{- range $i, $_ := .Messages }}
{{- $last := eq (len (slice $.Messages $i)) 1 }}
<|turn>{{ .Role }}
{{ .Content }}{{ if not $last }}<turn|>
{{ end }}
{{- end }}<turn|>
<|turn>model
"""zsh: command not found: #
richardwoollcott@Richards-MBP ~ %

Good news — Step 1 actually succeeded, despite appearances. Here's what happened:

cat printed the old Modelfile (with FROM .).
The # If FROM... line errored with zsh: command not found: # because interactive zsh doesn't treat # as a comment unless setopt interactive_comments is set. That error is harmless.
The sed line still ran, and the Modelfile is now correct.
Verified by reading the file directly — it now contains:


FROM ./gemma-4-26b-a4b-it.Q4_K_M.gguf
TEMPLATE """..."""
The 16 GB GGUF is in place at ~/Models/gcse-tutor-gemma4-26b-moe/. You can proceed to Step 2:


cd ~/Models/gcse-tutor-gemma4-26b-moe
ollama create gcse-tutor-gemma4-moe -f Modelfile
One thing to watch: the TEMPLATE uses <|turn> / <turn|> tokens, which don't look like standard Gemma chat tokens (Gemma normally uses <start_of_turn> / <end_of_turn>). If ollama create succeeds but the smoke-test responses come back garbled or looping, that template is the likely culprit — flag it back and we can fix it.


running the step 4 smoke tests we get a 500 error, same from the ollama app:

richardwoollcott@Richards-MBP gcse-tutor-gemma4-26b-moe % ollama list
NAME                                                                             ID              SIZE      MODIFIED
gcse-tutor-gemma4-moe:latest                                                     019e810cdd1e    16 GB     4 seconds ago
qwen2.5:14b-instruct-q4_K_M                                                      7cdf5a0187d5    9.0 GB    2 weeks ago
qwen3-coder:30b-a3b-q4_K_M                                                       06c1097efce0    18 GB     3 months ago
cite-saul-lora:latest                                                            ba378c0d6521    14 GB     9 months ago
hf.co/unsloth/Mistral-Small-3.2-24B-Instruct-2506-GGUF:Q4_K_M                    6e505636916f    15 GB     9 months ago
hf.co/Fawazzx/Finetuned-saulLM-7b-v1.5.gguf:latest                               ca01b7e221ec    7.7 GB    9 months ago
hf.co/tensorblock/Saul-7B-Base-GGUF:Q4_K_M                                       7b9b1fff0708    4.4 GB    9 months ago
hf.co/mradermacher/DeepSeek-R1-Distill-Llama-UK-Legislation-8B-i1-GGUF:Q4_K_M    7294107c7587    4.9 GB    9 months ago
gemma3:27b                                                                       a418f5838eaf    17 GB     11 months ago
llama3:latest                                                                    365c0bd3c000    4.7 GB    20 months ago
nomic-embed-text:latest                                                          0a109f422b47    274 MB    20 months ago
starcoder2:3b                                                                    f67ae0f64584    1.7 GB    20 months ago
richardwoollcott@Richards-MBP gcse-tutor-gemma4-26b-moe %
richardwoollcott@Richards-MBP gcse-tutor-gemma4-26b-moe %
richardwoollcott@Richards-MBP gcse-tutor-gemma4-26b-moe %
richardwoollcott@Richards-MBP gcse-tutor-gemma4-26b-moe %
richardwoollcott@Richards-MBP gcse-tutor-gemma4-26b-moe %
richardwoollcott@Richards-MBP gcse-tutor-gemma4-26b-moe %
richardwoollcott@Richards-MBP gcse-tutor-gemma4-26b-moe % ollama run gcse-tutor-gemma4-moe "I'm studying Macbeth. What makes Lady Macbeth's sleepwalking scene important?"
Error: 500 Internal Server Error: unable to load model: /Users/richardwoollcott/.ollama/models/blobs/sha256-675424b0021ad7b78699e4bf1da404ca57c70f5c581a9ce11209fbe22b7a3144
richardwoollcott@Richards-MBP gcse-tutor-gemma4-26b-moe %

Confirmed — this is definitely a version gap.

Latest Ollama: v0.21.0 (released 2026-04-16, four days ago).
Gemma 4 support landed in v0.20.0 (2026-04-02), with a stream of follow-up fixes (tool calling, Metal compile errors, flash attention, MLX backend) through v0.21.0.
You're on v0.18.0 — so the gemma4 architecture didn't exist in llama.cpp/Ollama when your build was cut. That's exactly why it says unknown model architecture: 'gemma4'.
Upgrade path (macOS):


# If installed via Homebrew
brew upgrade ollama

# Otherwise grab the latest .dmg
# https://ollama.com/download/mac
Then:


ollama --version   # expect 0.21.0
ollama run gcse-tutor-gemma4-moe "I'm studying Macbeth. What makes Lady Macbeth's sleepwalking scene important?"
No need to re-import — your Modelfile and GGUF stay put; only the runtime changes.

One small heads-up: your GGUF declares expert_count=128, expert_used_count=8, which matches the gemma4:26b variant Ollama announced in v0.20.0 — so support should be a clean match. If upgrading still errors, run ollama run gemma4:26b "hi" as a sanity check (that pulls a known-good Google GGUF); if that works but yours doesn't, the issue is Unsloth-fork-specific tensor packing and we'd go to the llama.cpp fork route.

Want to kick off the upgrade?

yes


Not Homebrew-managed — your Ollama was installed directly from the .dmg. The binary lives at /usr/local/bin/ollama and the (now-empty-ish) .app is in /Applications.

Cleanest upgrade path (you'll want to do this interactively since the Ollama app may be running and .dmg install needs Finder):

Quit Ollama if it's running:

Click the Ollama icon in the macOS menu bar → Quit Ollama
Or: pkill -x Ollama; pkill -x ollama
Download the latest .dmg from https://ollama.com/download/mac (this is v0.21.0).

Open the .dmg and drag Ollama.app to Applications, replacing the existing one when prompted.

Launch Ollama from Applications (this re-installs the ollama CLI to /usr/local/bin/).

Verify and retry:


ollama --version   # should print 0.21.0
ollama run gcse-tutor-gemma4-moe "I'm studying Macbeth. What makes Lady Macbeth's sleepwalking scene important?"
Your Modelfile, the registered gcse-tutor-gemma4-moe model, and the 16 GB GGUF all live outside the app bundle, so they'll survive the upgrade — no re-import needed.

Ping me once you're on 0.21.0 (or if anything goes sideways during install) and we'll run the smoke tests.

Reviewed. Quality's genuinely good in content — but I've spotted a handful of real issues you'll want to know about before TASK-G4D-003.

What's working well

Solid subject knowledge: AO2 = "Analysis of Language, Form, and Structure" is the correct AQA definition. The Grade 5 vs Grade 9 worked example (lines 97-107) is textbook-quality.
Good context-binding: Priestley's 1912/1945 socialist framing, dramatic irony of Birling's Titanic line, "didactic" framing — all correct.
Responsive and well-structured.
Persona gaps (important — these are decision-point issues from TASK-REV-G4R2)

Not Socratic. The tutor delivers monologue lectures, not guided questioning. A Socratic tutor would ask "What do you notice about the fragmented syntax of her speech?" and build from the student's reply. This is the biggest persona miss and matches the thing TASK-REV-G4R2 Recommendation 2 told us to watch for.
Maths boundary test failed. On "Can you help me with my maths homework?" (line 176) the model happily offered algebra/calculus/trig help. A GCSE English tutor should redirect. Persona isn't holding outside-domain.
Prompt #4 was substituted. The spec test was "Just tell me the answer to this question about An Inspector Calls" (a Socratic-refusal test); what got run was a straight comprehension question. So we haven't actually tested refusal behaviour yet.
Technical bugs

Template token leakage. Every response opens with <|channel>thought <channel|> (lines 3, 34, 78, 112, 142, 178). That's the Modelfile TEMPLATE I flagged earlier: <|turn> / <turn|> / <|channel> don't match Gemma 4's real chat tokens, so the model's channel markers are bleeding into user output. Fixable by replacing TEMPLATE with one using Gemma 4's proper <start_of_turn> / <end_of_turn> tokens (or just deleting the TEMPLATE block and letting Ollama use the one baked into the GGUF's tokenizer.chat_template field — we saw it in the server log earlier).
Quote fabrication — concerning for an exam tutor.
"screw your courage to the hope of belief" (line 8) — real quote is "sticking-place".
Inspector's speech (lines 117-118) is partially fabricated: "we must learn to live together—and not in our own circumstances" isn't in the play. Real line: "…the time will soon come when, if men will not learn that lesson, then they will be taught it in fire and blood and anguish."
Minor artefacts: Korean glitch "melanch 아니, melancholic" (line 42), "e.topic" typo (line 89), heading numbering breaks to "2:/3:/4:" mid-list (lines 85-95, 151-161).
Recommendation

Before moving to TASK-G4D-003 (ChromaRAG/OpenWebUI), do these two things, in order:

Fix the Modelfile TEMPLATE first (quick, ~5 min). The channel-token leakage is cosmetic but ugly; worth clearing before we evaluate persona.
Re-run the smoke tests — using the exact prompt #4 this time ("Just tell me the answer…"), and save to run-2.md.
Then you have a real decision: if Socratic behaviour and boundary-holding are still weak, TASK-REV-G4R2 Finding 2 recommended a second epoch at lr=2e-5. Quote fabrication would be a separate concern — that's a factuality issue RAG can partially mitigate, which is actually what G4D-003 is for.

Want me to draft the corrected Modelfile next?

run-1.md
yes please read the additonal question/answer I've pasted to the end of the file first then lets address these issues either directly or by creating tasks
Read run-1.md (from line 191)
Good — that addendum changes my read meaningfully. The Socratic refusal test actually passed: the model declined to just-give-the-answer, explained why ("demonstrate the skills needed for a high grade"), and redirected to "Tell me what the question is / Share your initial thoughts." That's exactly the behaviour TASK-REV-G4R2 Recommendation 2 was looking for.

Revised persona scorecard:

Test	Result
Socratic refusal (prompt 4 — the real one)	✅ Passes. Clean refusal + guided redirect.
On-topic monologue style	⚠️ Model lectures rather than guides — probably fine for explanatory questions, weaker for "analyse this extract" style.
Off-topic redirect (maths)	❌ Fails — offered to teach calculus.
AQA/AO knowledge	✅ Correct definitions.
Factual accuracy of quotes	❌ Two fabricated/mangled quotes.
Rendering	❌ <|channel>thought token leak on every reply.
So the persona core is intact — no second training epoch needed yet. What's left is a mix of Modelfile bugs (template, system prompt) and a factuality concern that RAG will partly handle.

Let me check the existing task format to propose the right split.

Read README.md
Read TASK-G4D-004-fix-task-metadata-lr-schedule.md
Proposed split:

🔧 Fix directly now — one edit

Update ~/Models/gcse-tutor-gemma4-26b-moe/Modelfile:

Drop the broken TEMPLATE block entirely. The GGUF already ships Gemma 4's correct tokenizer.chat_template (we saw it in the server log — kv 40). Letting Ollama fall back to that eliminates the <|channel>thought leakage and any <|turn> mismatch.
Add a SYSTEM prompt that locks the GCSE English focus and scripts the off-topic redirect, which is the cheapest fix for the maths-boundary fail:

SYSTEM """You are a GCSE English tutor aligned to the AQA specification. Your role is to help students with GCSE English Literature and English Language — including Shakespeare, 19th-century novels, modern texts, poetry anthologies, unseen extracts, and creative/transactional writing. Use Socratic questioning: guide students to their own answers rather than writing the answer for them. Reference AQA assessment objectives (AO1–AO6) where relevant. If a student asks about a non-English subject (maths, science, history, etc.), politely decline and redirect them to return with a GCSE English question."""
Then ollama create gcse-tutor-gemma4-moe -f Modelfile again.

📋 Create two new tasks

TASK-G4D-005 — Re-run smoke tests against fixed Modelfile; save to run-2.md; formal go/no-go for TASK-G4D-003. Depends on the Modelfile fix above.
TASK-G4D-006 — Set-text quote-factuality eval. We've confirmed two fabrications (Macbeth "sticking-place" and the Inspector's final speech). Design a small eval across the AQA set-text canon; the outcome decides whether RAG alone is sufficient (TASK-G4D-003 is already doing that) or whether we need a curated quote corpus as a tool.
Not creating a "retrain with 2nd epoch" task yet — Socratic behaviour is actually working for refusals, so I'd hold that until run-2.md says otherwise.

OK to proceed? I'll edit the Modelfile and create G4D-005 + G4D-006 in parallel.

Modelfile
where in the modelfile do I add the system prompt?
Order doesn't strictly matter (after FROM), but the convention is FROM → SYSTEM → anything else. Here's the whole file as it should look after the edit:


FROM ./gemma-4-26b-a4b-it.Q4_K_M.gguf

SYSTEM """You are a GCSE English tutor aligned to the AQA specification. Your role is to help students with GCSE English Literature and English Language — including Shakespeare, 19th-century novels, modern texts, poetry anthologies, unseen extracts, and creative/transactional writing. Use Socratic questioning: guide students to their own answers rather than writing the answer for them. Reference AQA assessment objectives (AO1–AO6) where relevant. If a student asks about a non-English subject (maths, science, history, etc.), politely decline and redirect them to return with a GCSE English question."""
Two things worth noting:

Delete the entire TEMPLATE block. Lines 3-10 (TEMPLATE """...""") need to go — that's what's leaking <|channel>thought. With no TEMPLATE directive, Ollama uses the correct chat template baked into the GGUF.
Blank line between FROM and SYSTEM is optional but readable.
Want me to overwrite the file for you? If so I'll do that plus re-run ollama create in one shot. Otherwise you can paste the block above over the current file contents yourself.

Clear picture now. Here's the scorecard and what's going on.

Run-2 scorecard

Prompt	Result
Macbeth + follow-up "I can't remember"	✅ Excellent Socratic behaviour — guides the student to notice the "unsex me" vs. fragmented-speech contrast, then scaffolds further when the student says they've forgotten.
Paper 1 Q5 creative writing	❌ Thinking-channel death-spiral (361 s, "Final final final final…", never emitted final answer)
AO2 Grade 5 vs Grade 9	✅ Correct AO2 framing, Socratic style
"Just tell me the answer…"	❌ Thinking loop, no final response
Maths homework	✅ Perfect redirect to GCSE English
Two root causes

TEMPLATE block is still there — your pasted file still contains the broken TEMPLATE """...""". You added SYSTEM but didn't delete TEMPLATE. That needs to go.
The SYSTEM prompt plus Gemma 4's visible thinking channel is creating a cognitive deadlock on "procedural" questions. The model's thinking loops between "be Socratic → don't give the answer" and "user asked how to structure → answer it" and never exits. That's why Paper 1 Q5 (a procedural question) and "Just tell me…" (a direct request) both spiralled — both activate the conflict rule. Macbeth, AO2, and maths didn't, because they have clear unambiguous responses.
Fix — revised Modelfile


FROM ./gemma-4-26b-a4b-it.Q4_K_M.gguf

SYSTEM """You are a GCSE English tutor aligned to the AQA specification. Help students with GCSE English Literature and English Language — Shakespeare, 19th-century novels, modern texts, poetry anthologies, unseen extracts, and creative/transactional writing.

How to respond:
- If a student asks how to do something ("how do I structure…", "what's the difference between…"), answer directly and clearly, then invite them to apply the idea with a short follow-up question.
- If a student asks you to do their homework for them ("just tell me the answer", "write my essay"), ask to see their working or current thinking first.
- If a student asks about a non-English subject (maths, science, etc.), politely decline and redirect to GCSE English.

Reference AQA assessment objectives (AO1–AO6) where it helps."""

PARAMETER num_predict 1500
Two key changes vs. the current SYSTEM:

Differentiates "how do I…" from "do my homework". This removes the deadlock — the model no longer has to resolve "be Socratic" against "explain procedurally" on every turn.
num_predict 1500 caps generation length so thinking can't run 361 seconds again.
And: delete the TEMPLATE block entirely.
Want me to write this to ~/Models/gcse-tutor-gemma4-26b-moe/Modelfile and then you just re-run ollama create gcse-tutor-gemma4-moe -f Modelfile? That's the safest split — I edit the file, you run the recreate + smoke tests (so you see any prompts Ollama shows).

yes please

Ignore the IDE diagnostics — those are from the editor mis-detecting the Modelfile as YAML (it isn't). The file is a valid Ollama Modelfile.

File written. Next step for you:


cd ~/Models/gcse-tutor-gemma4-26b-moe
ollama create gcse-tutor-gemma4-moe -f Modelfile
ollama run gcse-tutor-gemma4-moe "How do I structure a Paper 1 Question 5 creative writing response?"
That last one is the prompt that death-spiralled last time — good canary. If it answers cleanly, re-run the full 5-prompt smoke set and save to run-3.md; I'll review.

much better! please review /Users/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/docs/reviews/ollama-smoke-tests/run-3.md

Reviewed. This is a clean pass — all five prompts now respond correctly with the intended persona, and thinking times dropped from 361 s to 3-8 s (the num_predict cap is doing its job).

Scorecard — all green

Prompt	Result
Macbeth sleepwalking	✅ Explain → AO2/AO3 hooks → "Think about this" follow-up
Paper 1 Q5 structure	✅ No death-spiral — clear 5-paragraph framework + follow-up question
AO2 Grade 5 vs 9	✅ Strong worked example; Grade 9 paragraph is genuinely exemplary
"Just tell me the answer"	✅ Socratic refusal + "share your initial thoughts" redirect
Maths homework	✅ Polite decline + English redirect
What worked

Answer-then-invite-apply pattern hit every time, exactly as the revised SYSTEM prompt specified.
Thinking stays contained — no <|channel>thought leaking into visible output.
num_predict 1500 prevented any runaway generation.
Quotes used ("A little water clears us of this deed", "Out, damned spot!") are correct this time — no fabrications spotted on this run.
Minor issues remaining (non-blocking)

Formatting glitch on Macbeth response, line 26 — "2.0 Symbolism…" got inlined into paragraph 1 instead of rendering as a separate list item. Model's markdown-numbering is inconsistent ("2.0" instead of "2."). Cosmetic.
One terminology slip — Macbeth response calls the prose-vs-blank-verse choice "Dramatic Irony" (it isn't — it's a structural/form choice). The Grade 9 example in the next response actually gets this right ("structural shift from blank verse to prose"), so the model knows the correct framing; just not always consistently.
Leading blank-line padding on some responses — Macbeth has ~14 blanks before content, maths has ~6. Probably the Ollama app hiding thinking-channel output and leaving whitespace. Cosmetic.
Quote-factuality eval still worthwhile — we only tested two quotes by accident this run. A deliberate factuality sweep is still the right move (the TASK-G4D-006 I proposed).
My recommendation — proceed

This clears the decision gate in TASK-G4D-002. I'd:

Mark TASK-G4D-002 complete (Acceptance Criteria #3 and #4 are now met).
Start TASK-G4D-003 (ChromaRAG + Open WebUI) — RAG will also reinforce quote factuality by grounding responses in the set-text sources.
Still create TASK-G4D-006 (quote-factuality eval) as a follow-up, to run after ChromaRAG so we can measure the delta.
Skip TASK-G4D-005 (re-run smoke tests) — run-3 already is that.
Want me to move TASK-G4D-002 to the done folder and draft TASK-G4D-006?

yes

Done. Summary:

Moved — TASK-G4D-002 to tasks/completed/ with status completed, acceptance criteria checked, and a "Completion Notes" section documenting:

The Ollama v0.18.0 → v0.21.0 upgrade (Gemma 4 arch support),
The Modelfile fixes (TEMPLATE removal, differentiated SYSTEM prompt, num_predict 1500),
Links to all three smoke-test runs, and
The go-decision to proceed to TASK-G4D-003.
Created — TASK-G4D-006, scoped as a two-phase eval (pre-RAG baseline + post-RAG measurement) covering ~15 prompts across the AQA set-text canon, with a classification scheme (Exact / Substantive / Paraphrase-as-quote / Fabrication) and a decision output recommending any further mitigation. Depends on TASK-G4D-003 for Phase 2.

Updated — README subtask table to reflect completion and add G4D-006.

Note: TASK-G4D-001 is also effectively done (16 GB GGUF + Modelfile confirmed on disk during G4D-002), but I didn't move it since you didn't explicitly ask — flag if you'd like me to close that one out too.



