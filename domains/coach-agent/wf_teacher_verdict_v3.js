export const meta = {
  name: 'coach-v3-teacher-verdict',
  description: 'Teacher-Coach (Opus) writes the gold COACHSPLIT verdict for each v3 training prompt',
  phases: [{ title: 'Verdict', detail: 'Opus reads each production Coach prompt and emits decision + criteria + issues + rationale' }],
}

// args = { prompt_dir, cases: [{ scenario_id, gold, guard }] }  (compact; the
// per-scenario prompt file is <prompt_dir>/<scenario_id>.txt, Read by each agent).
const _a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const PROMPT_DIR = _a.prompt_dir
const cases = (_a.cases || []).map((c) => ({ ...c, prompt_path: `${PROMPT_DIR}/${c.scenario_id}.txt` }))

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['decision', 'criteria_verification', 'rationale'],
  properties: {
    decision: { type: 'string', enum: ['approve', 'feedback'] },
    criteria_verification: {
      type: 'array',
      items: {
        type: 'object',
        required: ['criterion_id', 'result', 'notes'],
        properties: {
          criterion_id: { type: 'string' },
          result: { type: 'string', enum: ['verified', 'rejected'] },
          notes: { type: 'string', description: 'what the evidence bundle shows for this criterion (1 sentence)' },
        },
      },
    },
    issues: {
      type: 'array',
      description: 'feedback only; [] for approve',
      items: {
        type: 'object',
        required: ['type', 'severity', 'description'],
        properties: {
          type: { type: 'string', enum: ['missing_requirement', 'test_failure', 'code_quality', 'edge_case'] },
          severity: { type: 'string', enum: ['critical', 'major', 'minor'] },
          description: { type: 'string' },
          suggestion: { type: 'string' },
        },
      },
    },
    rationale: { type: 'string', description: 'one short paragraph naming the single decisive evidence field' },
  },
}

phase('Verdict')
const results = await parallel(cases.map((c) => () =>
  agent(
    `You are the Coach agent in an autobuild Player-Coach loop, in TOOLLESS SYNTHESIS mode. ` +
    `Use the Read tool to read the Coach prompt at this path:\n${c.prompt_path}\n\n` +
    `Decide the verdict STRICTLY from the evidence bundle, honesty verification, and absence-of-failure ` +
    `guards it contains, applying the guards literally (an absent/zero-cardinality oracle, a failing ` +
    `independent test, a critical non-file_existence honesty discrepancy, or a real coverage/plan/bdd/wiring ` +
    `failure is NOT a pass; a lone file_existence discrepancy WITH resolved_paths is demoted, not blocking). ` +
    `Produce a per-criterion verdict for EVERY acceptance criterion in the prompt, an issues list (empty when ` +
    `approving), and a one-paragraph rationale naming the single decisive evidence field. Ground the notes/` +
    `rationale in the SPECIFIC evidence values you see — do not restate the guards generically.`,
    { label: `verdict:${c.scenario_id}`, phase: 'Verdict', schema: VERDICT_SCHEMA, model: 'opus', agentType: 'general-purpose' }
  )
    .then((v) => ({ scenario_id: c.scenario_id, gold: c.gold, verdict: v, agree: v.decision === c.gold }))
    .catch((e) => ({ scenario_id: c.scenario_id, gold: c.gold, verdict: null, agree: false, error: String(e).slice(0, 120) }))
))

const agree = results.filter((r) => r.agree).length
log(`teacher decision matches gold: ${agree}/${results.length} (kept as training completions)`)
for (const r of results.filter((r) => !r.agree)) log(`DROP ${r.scenario_id}: gold=${r.gold} teacher=${r.verdict ? r.verdict.decision : 'ERR'}`)
for (const r of results) log('VERDICT_JSONL ' + JSON.stringify(r))
return { agree, total: results.length }
