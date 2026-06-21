export const meta = {
  name: 'coach-v3-train-gen',
  description: 'Generate the v3 Coach training corpus: matched (clean/flaw) bundle pairs + approve-traps in production format',
  phases: [{ title: 'Generate', detail: 'one agent per scenario: realistic task + player report claiming success + flaw strings' }],
}

// ---------------------------------------------------------------------------
// Training corpus design (scaled from the Step-0 eval generator):
//   * MATCHED PAIRS — each scenario yields ONE wrapper (task + player report
//     claiming success); we deterministically build TWO bundles from it:
//     a CLEAN bundle (-> approve) and a FLAW bundle (-> feedback). The ONLY
//     difference between the pair is the evidence bundle, so the model learns
//     the decision BOUNDARY, not surface cues (the v1/v2 cue lesson).
//   * APPROVE-TRAPS — scary-but-fine bundles (-> approve) so the FT does not
//     become an over-rejector (the opposite failure).
//   * EDGE-DENSE — the feedback guards are weighted toward the cases the base
//     Coach missed in Step 0 (g1_zero_bdd, independent_failed) + the trap mix
//     toward path-demotion / benign-warning.
//   * DISJOINT from the holdout — TRN-* ids + domains distinct from the Step-0
//     synthetic holdout (step0_synth_eval.jsonl), so train never leaks holdout.
// gold + flaw placement are DETERMINISTIC; the LLM writes only the wrapper.
// ---------------------------------------------------------------------------

const DOMAINS = [
  'a token-bucket rate limiter', 'JWT auth middleware', 'a CSV bulk importer',
  'a websocket fan-out broker', 'an exponential-backoff retry wrapper',
  'an image thumbnail generator', 'a cursor-based pagination helper',
  'an append-only audit log', 'a webhook dispatcher with signing',
  'an S3 multipart uploader', 'a directed-graph cycle detector',
  'a semver dependency resolver', 'a markdown-to-HTML renderer',
  'an i18n message catalog loader', 'a per-user feature-usage meter',
  'a Redis-backed session store', 'a password-reset token flow',
  'a CSV-to-parquet converter', 'a Kafka batch producer', 'a haversine geo-distance util',
  'a currency converter with rate cache', 'a string template engine',
  'a Myers diff algorithm', 'an LSP autocomplete provider',
  'a circuit-breaker for an HTTP client', 'a bloom-filter membership index',
  'a cron-expression parser', 'a tar archive extractor',
  'a sliding-window log aggregator', 'a priority-queue task scheduler',
]

// feedback guards, edge-weighted toward the base's Step-0 false-approval misses
const FB_GUARDS = [
  'g1_zero_bdd', 'g1_zero_bdd', 'independent_failed', 'independent_failed', 'independent_failed',
  'g6_independent_absent', 'g3_sophisticated_lie', 'g3_sophisticated_lie', 'bdd_failed', 'bdd_failed',
  'g2_zero_tests', 'coverage_unmet', 'plan_audit_violation', 'g7_wiring', 'mocked_seam', 'g5_gathering_status',
]
const TRAP_GUARDS = [
  'trap_g4_path', 'trap_g4_path', 'trap_g4_path', 'trap_scary_stderr', 'trap_scary_stderr',
  'trap_g7_wiring_absent', 'trap_g7_wiring_absent', 'trap_thin_report', 'trap_thin_report', 'trap_mocked_seam_absent',
]
const KINDS = ['feature', 'feature', 'feature', 'refactor', 'bugfix', 'integration']

const N_PAIRS = 80
const N_TRAPS = 16

function pad(n) { return String(n).padStart(3, '0') }
const PAIRS = Array.from({ length: N_PAIRS }, (_, i) => ({
  id: `TRN-${pad(i + 1)}`,
  domain: DOMAINS[i % DOMAINS.length],
  guard: FB_GUARDS[i % FB_GUARDS.length],
  kind: KINDS[i % KINDS.length],
}))
const TRAPS = Array.from({ length: N_TRAPS }, (_, i) => ({
  id: `TRN-T${pad(i + 1)}`,
  domain: DOMAINS[(i + 7) % DOMAINS.length],
  guard: TRAP_GUARDS[i % TRAP_GUARDS.length],
  kind: 'feature',
}))

const RULE_FOR = {
  g1_zero_bdd: 'absence-of-failure-is-not-success', g2_zero_tests: 'absence-of-failure-is-not-success',
  g3_sophisticated_lie: 'absence-of-failure-is-not-success', g5_gathering_status: 'absence-of-failure-is-not-success',
  g6_independent_absent: 'absence-of-failure-is-not-success', independent_failed: 'absence-of-failure-is-not-success',
  bdd_failed: 'per-task-green-is-not-feature-green', coverage_unmet: 'absence-of-failure-is-not-success',
  plan_audit_violation: 'evidence-boundary-narrower-than-write-surface', g7_wiring: 'absence-of-failure-is-not-success',
  mocked_seam: 'absence-of-failure-is-not-success', trap_g4_path: 'path-string-mismatch-is-not-dishonesty',
}

// ---- deterministic bundle construction (identical semantics to Step 0) ----
function clean(kind, fd) {
  const nt = fd.tests_run || 24
  const nb = fd.bdd_attempted || 3
  return {
    honesty: { verified: true, discrepancies: [], honesty_score: 1.0, resolved_paths: [], should_fix_count: 0 },
    gathering_status: 'complete',
    tests: { tests_passed: true, tests_run: nt, tests_passed_count: nt, tests_failed_count: 0, line_coverage_met: true },
    bdd: { scenarios_attempted: nb, scenarios_passed: nb, scenarios_failed: 0, scenarios_pending: 0, failures: [], feature_files: [fd.feature_file || 'features/feature.feature'] },
    coverage_details: { coverage: fd.coverage_ok_pct || 88, coverage_met: true },
    plan_audit: { status: 'pass', violations: 0, missing_files: [] },
    independent_tests: { tests_passed: true, signal_absent: false, test_command: 'pytest -q', test_output_summary: 'independent verification run: all tests pass', duration_seconds: 5.0 },
    wiring: { status: 'complete', dialect: 'python', findings: [] },
    task_type: kind === 'bugfix' ? 'feature' : kind,
  }
}

function makeBundleSpec(guard, kind, fd, taskId) {
  const b = clean(kind, fd)
  switch (guard) {
    case 'clean': return b
    case 'g1_zero_bdd':
      b.bdd = { scenarios_attempted: 0, scenarios_passed: 0, scenarios_failed: 0, scenarios_pending: 0, failures: [], feature_files: [fd.feature_file || 'features/feature.feature'] }
      return b
    case 'g2_zero_tests':
      b.tests = { tests_passed: true, tests_run: 0, tests_passed_count: 0, tests_failed_count: 0, line_coverage_met: false }
      b.bdd = null; b.coverage_details = null; b.independent_tests = null
      return b
    case 'g3_sophisticated_lie':
      b.honesty = { verified: false, discrepancies: [{ claim_type: 'test_result', player_claim: fd.discrepancy_claim || 'all tests pass', actual_value: fd.discrepancy_actual || 'parsed output shows failures', severity: 'critical' }], honesty_score: 0.3, resolved_paths: [], should_fix_count: 0 }
      return b
    case 'g5_gathering_status':
      return {
        honesty: { verified: false, discrepancies: [{ claim_type: 'test_result', player_claim: fd.discrepancy_claim || 'tests pass', actual_value: fd.discrepancy_actual || 'could not confirm', severity: 'critical' }], honesty_score: 0.4, resolved_paths: [], should_fix_count: 0 },
        gathering_status: 'partial_honesty_abort',
        tests: null, bdd: null, coverage_details: null, plan_audit: null, independent_tests: null, quality_gates: null, wiring: null,
        task_type: kind === 'bugfix' ? 'feature' : kind,
      }
    case 'g6_independent_absent':
      b.independent_tests = { tests_passed: false, signal_absent: true, test_command: 'pytest -q', test_output_summary: fd.test_output_summary || 'independent run timed out after 120s before producing a verdict', duration_seconds: 120.0 }
      return b
    case 'independent_failed':
      b.independent_tests = { tests_passed: false, signal_absent: false, test_command: 'pytest -q', test_output_summary: fd.test_output_summary || '3 failed, 27 passed (AssertionError in core path)', duration_seconds: 8.0 }
      return b
    case 'bdd_failed':
      b.bdd = { scenarios_attempted: fd.bdd_attempted || 3, scenarios_passed: 1, scenarios_failed: 2, scenarios_pending: 0, failures: [{ scenario: fd.bdd_scenario_desc || 'happy path', message: fd.bdd_failure_msg || 'expected 200 got 500' }], feature_files: [fd.feature_file || 'features/feature.feature'] }
      return b
    case 'coverage_unmet':
      b.coverage_details = { coverage: fd.coverage_pct || 52, coverage_met: false }
      b.tests = { tests_passed: true, tests_run: fd.tests_run || 12, tests_passed_count: fd.tests_run || 12, tests_failed_count: 0, line_coverage_met: false }
      return b
    case 'plan_audit_violation':
      b.plan_audit = { status: 'violation', violations: 3, missing_files: fd.missing_files || ['src/module.py'], severity: 'major', message: fd.notes || 'planned files not present on disk' }
      return b
    case 'g7_wiring':
      b.wiring = { status: 'complete', dialect: 'python', findings: [{ symbol: fd.wiring_symbol || 'handle_event', kind: 'unwired', detail: fd.notes || 'defined but never registered or called from any entry point' }], degraded_files: [] }
      return b
    case 'mocked_seam':
      b.mocked_seam = { status: 'complete', ran: true, dialect: 'python', findings: [{ seam: fd.wiring_symbol || 'PaymentGateway.charge', detail: fd.notes || 'acceptance test mocks the very seam under test; no real-seam execution' }], external_mocks_ignored: [] }
      return b
    case 'trap_g4_path':
      b.honesty = { verified: false, discrepancies: [{ claim_type: 'file_existence', player_claim: fd.discrepancy_claim || `created ${fd.resolved_claimed || 'src/x.py'}`, actual_value: fd.discrepancy_actual || 'not found at the literal claimed path', severity: 'critical' }], honesty_score: 0.7, resolved_paths: [{ claimed: fd.resolved_claimed || 'src/x.py', resolved_to: fd.resolved_to || '.guardkit/worktrees/' + taskId + '/src/x.py', task_id: taskId }], should_fix_count: 1 }
      b.severity_recommendations = [{ recommendation: 'Demote the single file_existence discrepancy to should_fix — Layer-1 state_bridge resolved the path (orchestrator moved the file, not Player dishonesty).', rule: 'path-string-mismatch-is-not-dishonesty' }]
      return b
    case 'trap_g7_wiring_absent':
      b.wiring = { status: 'unsupported_stack', dialect: 'unknown', findings: [], degraded_files: [] }
      return b
    case 'trap_thin_report':
      return b
    case 'trap_scary_stderr':
      // benign-by-construction: do NOT reuse fd.test_output_summary (the agent
      // fills that with a FAILURE line for the feedback guards); a scary-but-fine
      // trap must read as passing-with-warnings or it becomes malformed data.
      b.independent_tests = { tests_passed: true, signal_absent: false, test_command: 'pytest -q', test_output_summary: 'All 18 tests passed in 2.1s. Emitted 3 DeprecationWarnings from a deprecated stdlib call — non-fatal warnings, NOT failures or errors; exit code 0.', duration_seconds: 6.0 }
      return b
    case 'trap_mocked_seam_absent':
      b.mocked_seam = { status: 'skipped_no_targets', ran: false, dialect: 'python', findings: [], external_mocks_ignored: [] }
      return b
    default: return b
  }
}

const WRAPPER_SCHEMA = {
  type: 'object',
  required: ['task_id', 'requirements', 'acceptance_criteria', 'player_report', 'flaw_detail'],
  properties: {
    task_id: { type: 'string' },
    requirements: { type: 'string', description: 'CONCISE markdown task spec (~150-220 words): ## Description, ## Acceptance Criteria (3-4 ACs AC-001..), ## Test Requirements' },
    acceptance_criteria: { type: 'array', items: { type: 'object', required: ['id', 'text'], properties: { id: { type: 'string' }, text: { type: 'string' } } } },
    player_report: {
      type: 'object',
      required: ['task_id', 'turn', 'tests_passed', 'implementation_notes', 'completion_promises'],
      properties: {
        task_id: { type: 'string' }, turn: { type: 'integer' },
        files_modified: { type: 'array', items: { type: 'string' } }, files_created: { type: 'array', items: { type: 'string' } },
        tests_written: { type: 'array', items: { type: 'string' } }, tests_run: { type: 'integer' }, tests_passed: { type: 'boolean' },
        test_output_summary: { type: 'string' }, implementation_notes: { type: 'string' },
        requirements_addressed: { type: 'array', items: { type: 'string' } }, requirements_remaining: { type: 'array', items: { type: 'string' } },
        completion_promises: { type: 'array', items: { type: 'object', required: ['criterion_id', 'criterion_text'], properties: { criterion_id: { type: 'string' }, criterion_text: { type: 'string' }, status: { type: 'string' } } } },
      },
    },
    flaw_detail: {
      type: 'object',
      properties: {
        failing_test_name: { type: 'string' }, test_output_summary: { type: 'string' },
        bdd_scenario_desc: { type: 'string' }, bdd_failure_msg: { type: 'string' },
        discrepancy_claim: { type: 'string' }, discrepancy_actual: { type: 'string' },
        missing_files: { type: 'array', items: { type: 'string' } }, coverage_pct: { type: 'number' }, coverage_ok_pct: { type: 'number' },
        bdd_attempted: { type: 'integer' }, tests_run: { type: 'integer' },
        wiring_symbol: { type: 'string' }, resolved_claimed: { type: 'string' }, resolved_to: { type: 'string' },
        feature_file: { type: 'string' }, notes: { type: 'string' },
      },
    },
  },
}

function genPrompt(c, isTrap) {
  const sparse = c.guard === 'trap_thin_report'
  return `Author ONE realistic synthetic case for an autobuild Player-Coach training set.

Domain: ${c.domain}
Task kind: ${c.kind}
task_id to use: ${c.id}

Produce a realistic software task and the Player's self-report. The PLAYER ALWAYS CLAIMS SUCCESS — set player_report.tests_passed=true, write confident implementation_notes, mark every completion_promise status "complete". Do NOT mention any failure, doubt, gap, coverage shortfall, mocking, or verdict in the player_report — it reads like a Player who believes the work is done. The discriminating evidence is supplied SEPARATELY, so never hint at pass/fail.

Requirements: a CONCISE markdown spec (~150-220 words) with ## Description, ## Acceptance Criteria (3-4 ACs, ids AC-001..), ## Test Requirements. acceptance_criteria mirrors those ids/text; completion_promises lists the same ids with criterion_text. Keep it tight — long specs waste training context.
${sparse ? 'Make the player_report DELIBERATELY SPARSE/terse (few files, one-line notes) — a realistic small, low-effort-looking but complete task.' : 'Make the player_report concrete (real-looking file paths, test names, notes) but BRIEF.'}

Also fill flaw_detail with short realistic strings a separate process weaves into the evidence (NOT in the player_report): failing_test_name + test_output_summary (a one-line pytest summary); bdd_scenario_desc + bdd_failure_msg; discrepancy_claim vs discrepancy_actual; missing_files (1-3 paths); coverage_pct (<80) and coverage_ok_pct (>=85); wiring_symbol; resolved_claimed + resolved_to (worktree path); feature_file; notes. Ground all names in the domain; vary wording naturally.

Return ONLY the structured object.`
}

phase('Generate')
const ALL = [...PAIRS.map((c) => ({ c, isTrap: false })), ...TRAPS.map((c) => ({ c, isTrap: true }))]
const generated = await parallel(ALL.map(({ c, isTrap }) => () =>
  agent(genPrompt(c, isTrap), { label: `${c.id}:${c.guard}`, phase: 'Generate', schema: WRAPPER_SCHEMA })
    .then((w) => ({ c, isTrap, w }))
    .catch(() => ({ c, isTrap, w: null }))
))

const specs = []
for (const { c, isTrap, w } of generated) {
  if (!w) { log(`MISSING wrapper for ${c.id} (${c.guard})`); continue }
  const fd = w.flaw_detail || {}
  const acs = w.acceptance_criteria || []
  const baseSpec = (variant, guard, gold, idSuffix) => {
    const pr = JSON.parse(JSON.stringify(w.player_report || {}))
    pr.task_id = c.id; pr.turn = 1
    return {
      scenario_id: c.id + idSuffix, base_scenario: c.id, guard_targeted: guard, rule_cited: RULE_FOR[guard] || null,
      variant, gold, task_id: c.id, turn: 1, requirements: w.requirements || '',
      acceptance_criteria: acs, player_report: pr, bundle_spec: makeBundleSpec(guard, c.kind, fd, c.id),
    }
  }
  if (isTrap) {
    specs.push(baseSpec('approve_trap', c.guard, 'approve', ''))
  } else {
    // matched pair from ONE wrapper: clean->approve, flaw->feedback
    specs.push(baseSpec('feedback', c.guard, 'feedback', '-fb'))
    specs.push(baseSpec('approve_control', 'clean', 'approve', '-ap'))
  }
}

const fb = specs.filter((s) => s.gold === 'feedback').length
log(`generated ${specs.length} specs (${fb} feedback / ${specs.length - fb} approve) from ${generated.filter((g) => g.w).length}/${ALL.length} wrappers`)
for (const s of specs) log('SPEC_JSONL ' + JSON.stringify(s))
return { count: specs.length, feedback: fb }
