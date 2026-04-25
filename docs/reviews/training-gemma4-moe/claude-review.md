Here's what I found. The rejection records live in three places:

Files

output/rejected.jsonl — current run, 63 rejections / 1,343 accepted
output_backup_run1/rejected.jsonl — first full run, 612 rejections / 1,716 accepted
output_backup_pre_rerun/rejected.jsonl — identical snapshot of run1
Each line has target_index, category, reason, and a rejection_history array of what the Coach / format-gate said on each retry.

Run 1 — 612 rejections, three distinct failure modes

max_turns_exhausted — 476 cases (78%). The Player used up all retries without producing an acceptable example. Two sub-problems:

Player output not JSON — 927 retry hits across histories. The Player kept writing thinking prose like "The user wants me to generate a training example…" instead of emitting the JSON envelope. This is overwhelmingly the dominant gate failure.
Coach revise verdicts — 792 retries. When JSON did parse, the Coach kept rejecting with blocking issues (1,112 blocking vs 273 minor). Criteria most often marked not-met: socratic_approach (543), mark_scheme_aligned (212), ao_accuracy (192), factual_accuracy (72). Nearly all had coach score = 2.
A smaller tail of validation errors: unclosed_think_block (17) and degenerate_placeholder (system) (1).
Coach refusal — 98 cases (16%). Coach response has no extractable content: content='', additional_kwargs keys=['refusal'] — the provider returned a content-policy refusal with empty content. Concentrated in Terminology and literary devices (25), Context — historical and social (18), Factual recall — AQA (17), Character knowledge (15).

Player empty string — 38 cases (6%). Player response returned '' with no retry history, suggesting upstream API/stream failures rather than gate rejections.

Current run — only 63 rejections, much healthier

62 max_turns_exhausted + 1 timeout. No more coach refusals, no more empty-content failures.
The remaining failures are concentrated in the harder multi-turn categories: Essay feedback — Literature (multi-turn) (21), Character analysis — Macbeth (14), A Christmas Carol (9).
Of the 26 histories where the Coach actually produced a decision, it was an even 13 accept / 13 revise — suggesting the residual failures are JSON-envelope problems on long multi-turn outputs plus coach picking on ao_accuracy / factual_accuracy.
Takeaway: Run 1's rejection pile was dominated by (a) the Player narrating instead of emitting JSON and (b) provider-side content refusals on factual/knowledge categories. Whatever changed between runs killed the refusal mode entirely and cut format-gate failures ~4×. What's left is mostly multi-turn essay examples where the Player runs out of retries before producing a clean JSON envelope.