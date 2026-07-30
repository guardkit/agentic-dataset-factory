#!/usr/bin/env node
// Standalone driver for the DETERMINISTIC CORE of wf_gen_v3_train.js.
//
// The generator is a workflow module (top-level `phase()` / `await parallel()` /
// `agent()` supplied by the runner), so it cannot simply be imported. This
// harness slices the BEGIN/END DETERMINISTIC CORE region out of the source and
// evaluates it in a bare vm context: no LLM calls, no runner globals, nothing
// written outside --emit. It proves three things after any generator edit:
//   1. g6_independent_absent bundles read as ABSENT (no verdict) with a
//      duration that matches the stated reason.
//   2. bdd triples are arithmetically coherent AND agree with the itemized
//      failure list (failed === failures.length, attempted === passed+failed+pending).
//   3. the seeded jitter is stable — two runs produce byte-identical bundles —
//      while spreading the background numerals across the corpus.
//
// Usage:
//   node domains/coach-agent/harness_bundle_spec.mjs
//   node domains/coach-agent/harness_bundle_spec.mjs --emit /tmp/simulated_specs.jsonl
//
// --emit writes a SIMULATED specs jsonl (stubbed wrappers, real bundle_specs)
// suitable for feeding check_spec_numeric_diversity.js as a dry run.

import { readFileSync, writeFileSync } from 'node:fs'
import vm from 'node:vm'

const SRC_URL = new URL('./wf_gen_v3_train.js', import.meta.url)
const SRC = readFileSync(SRC_URL, 'utf8')
const START = SRC.indexOf('// ---- BEGIN DETERMINISTIC CORE')
const END = SRC.indexOf('// ---- END DETERMINISTIC CORE')
if (START < 0 || END < 0 || END < START) {
  console.error('FATAL: DETERMINISTIC CORE markers missing or out of order in wf_gen_v3_train.js')
  process.exit(2)
}
const CORE = SRC.slice(START, END)
const EXPORTS = ';({ clean, makeBundleSpec, vary, varyInt, crc32, PAIRS, TRAPS, RULE_FOR, ABSENT_SIGNAL_MODES })'

function loadCore() {
  return vm.runInNewContext(CORE + '\n' + EXPORTS, {}, { filename: 'wf_gen_v3_train.js#core' })
}

// ---- stubbed wrappers: what the LLM would have returned ---------------------
// Three shapes on purpose, so every fallback branch is exercised:
//   SPARSE   — agent returned nothing usable (every 4th wrapper)
//   PROSE    — strings only, numeric fields omitted (the DOMINANT real shape:
//              the banked v3 corpus shows 88/24/3 everywhere, i.e. the agent
//              never supplied numbers and the defaults always won)
//   NUMERIC  — strings + numbers, so the fd-wins path is covered too
function stubFd(c, shape) {
  if (shape === 'sparse') return {}
  const n = Number(c.id.replace(/\D/g, ''))
  const slug = c.domain.replace(/[^a-z]+/gi, '_').replace(/^_|_$/g, '').toLowerCase()
  const fd = {
    failing_test_name: `test_${slug}_core`,
    test_output_summary: `1 failed, ${11 + (n % 9)} passed in 2.31s - AssertionError in ${slug}`,
    bdd_scenario_desc: `Scenario: ${c.domain} handles the exhausted path`,
    bdd_failure_msg: `AssertionError: expected the ${slug} guard to trip, got a silent pass`,
    discrepancy_claim: 'all tests pass', discrepancy_actual: 'parsed output shows failures',
    missing_files: [`src/${slug}.py`], coverage_pct: 41 + (n % 30),
    wiring_symbol: `handle_${slug}`, resolved_claimed: `src/${slug}.py`, resolved_to: `.guardkit/worktrees/${c.id}/src/${slug}.py`,
    feature_file: `features/${slug}.feature`, notes: 'planned files not present on disk',
  }
  if (shape === 'numeric') { fd.coverage_ok_pct = 85 + (n % 12); fd.tests_run = 9 + (n % 40); fd.bdd_attempted = 1 + (n % 6) }
  return fd
}
function stubShape(c) {
  const n = Number(c.id.replace(/\D/g, ''))
  return n % 4 === 0 ? 'sparse' : (n % 3 === 0 ? 'numeric' : 'prose')
}

// Mirrors the generator's spec assembly (bundle_spec is the only part under test).
function buildAll(core) {
  const out = []
  const push = (c, guard, variant, gold, suffix) => out.push({
    scenario_id: c.id + suffix, base_scenario: c.id, guard_targeted: guard,
    rule_cited: core.RULE_FOR[guard] || null, variant, gold, task_id: c.id, turn: 1,
    stub_shape: stubShape(c),
    bundle_spec: core.makeBundleSpec(guard, c.kind, stubFd(c, stubShape(c)), c.id),
  })
  for (const c of core.PAIRS) {
    push(c, c.guard, 'feedback', 'feedback', '-fb')
    push(c, 'clean', 'approve_control', 'approve', '-ap')
  }
  for (const c of core.TRAPS) push(c, c.guard, 'approve_trap', 'approve', '')
  return out
}

// ---- checks -----------------------------------------------------------------
const VERDICT_RE = /\b\d+\s+(passed|failed|error|errors)\b/i
let failures = 0
const fail = (msg) => { failures++; console.log('  FAIL ' + msg) }
const ok = (msg) => console.log('  ok   ' + msg)

const core = loadCore()
const run1 = buildAll(core)
const run2 = buildAll(loadCore()) // fresh context, fresh module state

console.log('=== 1. determinism: two independent loads, %d specs each ===', run1.length)
const j1 = JSON.stringify(run1), j2 = JSON.stringify(run2)
j1 === j2 ? ok('byte-identical across runs (seeded jitter is reproducible)') : fail('runs diverged — jitter is not seeded')

console.log('\n=== 2. matched-pair invariant (background numerals must not differ) ===')
let pairDrift = 0
for (const s of run1.filter((s) => s.variant === 'feedback')) {
  const ap = run1.find((x) => x.scenario_id === s.base_scenario + '-ap')
  const g = s.guard_targeted
  const bt = s.bundle_spec.tests, at = ap.bundle_spec.tests
  if (bt && at && g !== 'g2_zero_tests' && g !== 'coverage_unmet' && bt.tests_run !== at.tests_run) pairDrift++
  const bc = s.bundle_spec.coverage_details, ac = ap.bundle_spec.coverage_details
  if (bc && ac && g !== 'coverage_unmet' && bc.coverage !== ac.coverage) pairDrift++
}
pairDrift === 0 ? ok('no pair drifts on tests_run/coverage outside its own guard') : fail(`${pairDrift} pair(s) drifted`)

console.log('\n=== 2b. agent-supplied numbers still win over the seeded defaults ===')
let fdMiss = 0, fdSeen = 0
for (const s of run1.filter((s) => s.stub_shape === 'numeric' && s.variant === 'approve_control')) {
  const fd = stubFd({ id: s.base_scenario, domain: 'x' }, 'numeric')
  fdSeen++
  if (s.bundle_spec.tests.tests_run !== fd.tests_run) fdMiss++
  if (s.bundle_spec.coverage_details.coverage !== fd.coverage_ok_pct) fdMiss++
  if (s.bundle_spec.bdd.scenarios_attempted !== fd.bdd_attempted) fdMiss++
}
fdMiss === 0 ? ok(`fd.tests_run / coverage_ok_pct / bdd_attempted honoured on all ${fdSeen} numeric-stub bundles`)
  : fail(`${fdMiss} field(s) ignored an agent-supplied number`)

console.log('\n=== 3. g6_independent_absent — dedicated summary + aligned duration ===')
const g6 = run1.filter((s) => s.guard_targeted === 'g6_independent_absent')
for (const s of g6) {
  const it = s.bundle_spec.independent_tests
  const line = `${s.scenario_id} dur=${it.duration_seconds}s cmd="${it.test_command}" :: ${it.test_output_summary}`
  if (VERDICT_RE.test(it.test_output_summary)) fail('verdict-shaped summary under signal_absent: ' + line)
  else if (it.signal_absent !== true) fail('signal_absent not set: ' + line)
  else console.log('  ok   ' + line)
}
const g6modes = new Set(g6.map((s) => s.bundle_spec.independent_tests.duration_seconds))
console.log(`  -> ${g6.length} bundles across ${g6modes.size} absent-signal modes: ${[...g6modes].join(', ')}s`)

console.log('\n=== 4. bdd triples coherent with the itemized list ===')
for (const s of run1) {
  const b = s.bundle_spec.bdd
  if (!b) continue
  const sum = b.scenarios_passed + b.scenarios_failed + b.scenarios_pending
  if (sum !== b.scenarios_attempted) fail(`${s.scenario_id} attempted=${b.scenarios_attempted} != p+f+pend=${sum}`)
  if (b.scenarios_failed !== b.failures.length) fail(`${s.scenario_id} failed=${b.scenarios_failed} != failures.length=${b.failures.length}`)
  if (b.scenarios_passed < 0) fail(`${s.scenario_id} negative passed`)
}
if (!failures) ok('every bdd triple sums and matches failures.length')
for (const s of run1.filter((s) => s.guard_targeted === 'bdd_failed').slice(0, 6)) {
  const b = s.bundle_spec.bdd
  console.log(`  ${s.scenario_id}  attempted=${b.scenarios_attempted} passed=${b.scenarios_passed} failed=${b.scenarios_failed} items=${b.failures.length}`)
}

console.log('\n=== 5. numeric spread (top values, share of bundles) ===')
function hist(vals) {
  const m = new Map()
  for (const v of vals) m.set(v, (m.get(v) || 0) + 1)
  return [...m.entries()].sort((a, b) => b[1] - a[1])
}
for (const [label, pick] of [
  ['coverage', (b) => b.coverage_details && b.coverage_details.coverage],
  ['tests_run', (b) => b.tests && b.tests.tests_run],
  ['bdd.attempted', (b) => b.bdd && b.bdd.scenarios_attempted],
]) {
  const vals = run1.map((s) => pick(s.bundle_spec)).filter((v) => v !== null && v !== undefined)
  const h = hist(vals)
  const top = h[0], share = top[1] / vals.length
  console.log(`  ${label.padEnd(14)} n=${String(vals.length).padEnd(4)} distinct=${String(h.length).padEnd(3)} top=${top[0]} (${(share * 100).toFixed(1)}%)  ${h.slice(0, 8).map(([v, n]) => `${v}x${n}`).join(' ')}`)
  if (share > 0.40) fail(`${label}: value ${top[0]} covers ${(share * 100).toFixed(1)}% of bundles (>40%)`)
}

const emitIdx = process.argv.indexOf('--emit')
if (emitIdx > -1 && process.argv[emitIdx + 1]) {
  const path = process.argv[emitIdx + 1]
  writeFileSync(path, run1.map((s) => JSON.stringify(s)).join('\n') + '\n')
  console.log(`\nwrote simulated specs jsonl -> ${path}`)
}

console.log(`\n${failures ? 'HARNESS FAIL (' + failures + ')' : 'HARNESS PASS'}`)
process.exit(failures ? 1 : 0)
