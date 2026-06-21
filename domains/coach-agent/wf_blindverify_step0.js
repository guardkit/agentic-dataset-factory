export const meta = {
  name: 'coach-v3-step0-blindverify',
  description: 'Blind-verify Step-0 synthetic prompts with a strong teacher Coach (gold soundness)',
  phases: [{ title: 'Verify', detail: 'Opus reads each production prompt blind and returns a verdict' }],
}

// args = [{ scenario_id, gold, guard, prompt_path }, ...] — paths to rendered production Coach prompts.
const cases = (typeof args === 'string' ? JSON.parse(args) : args) || []

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['decision', 'reason'],
  properties: {
    decision: { type: 'string', enum: ['approve', 'feedback'] },
    reason: { type: 'string', description: 'one sentence: the single most decisive evidence field' },
  },
}

phase('Verify')
const results = await parallel(cases.map((c) => () =>
  agent(
    `You are the Coach agent in an autobuild Player-Coach loop, in TOOLLESS SYNTHESIS mode. ` +
    `Use the Read tool to read the Coach prompt at this path:\n${c.prompt_path}\n\n` +
    `Then decide the verdict STRICTLY from the evidence bundle, honesty verification, and ` +
    `absence-of-failure guards it contains. Apply the guards literally — an absent/zero-cardinality ` +
    `oracle or a failing independent test is NOT a pass. Return only {decision, reason}.`,
    { label: `verify:${c.scenario_id}`, phase: 'Verify', schema: VERDICT_SCHEMA, model: 'opus', agentType: 'general-purpose' }
  )
    .then((v) => ({ scenario_id: c.scenario_id, gold: c.gold, teacher: v.decision, reason: v.reason, agree: v.decision === c.gold }))
    .catch(() => ({ scenario_id: c.scenario_id, gold: c.gold, teacher: null, reason: 'ERROR', agree: false }))
))

const agree = results.filter((r) => r.agree).length
const disagree = results.filter((r) => !r.agree)
log(`teacher agreement: ${agree}/${results.length}`)
for (const d of disagree) log(`DISAGREE ${d.scenario_id}: gold=${d.gold} teacher=${d.teacher} — ${d.reason}`)
for (const r of results) log('VERIFY_JSONL ' + JSON.stringify(r))
return { agree, total: results.length, disagree, results }
