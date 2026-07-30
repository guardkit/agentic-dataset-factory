#!/usr/bin/env node
// REGEN-TIME GATE for the Coach training specs produced by wf_gen_v3_train.js.
//
// Three failure classes it exists to catch, the first two found in the banked
// v3 corpus, the third found by review of the first g6-mode generator cut:
//
//   NUMERIC MONOCULTURE — v3 shipped coverage=88, tests_run=24 and bdd 3-3-0 in
//   literally every bundle. Constant numerals are background the FT can
//   memorise instead of read (the numeric analogue of the v1/v2 cue lesson).
//   FAILS if any single value of a gated field covers more than --max-share
//   (default 40%) of the bundles that carry that field.
//
//   INCOHERENT EVIDENCE — a bdd triple that argues with its own itemized
//   failure list (v3: scenarios_failed=2 beside ONE listed failure), or an
//   absent-signal independent run whose summary states a verdict / an elapsed
//   time that contradicts duration_seconds.
//
//   ABSENT-SIGNAL PROSE MONOCULTURE — build_v4_sft.py derives the g6 locus
//   VERBATIM from independent_tests.test_output_summary, and its corpus-level
//   duplicate-loci check is a hard SystemExit. Two signal_absent bundles
//   sharing a summary therefore collide into duplicate loci downstream (the
//   first mode-table cut: 5 g6 ids crc-landed on 3 of 5 modes -> 3 unique
//   summaries -> the 'duplicate loci across rows' abort at the NEXT regen).
//   FAILS on any test_output_summary shared across signal_absent bundles.
//
// Usage:
//   node domains/coach-agent/check_spec_numeric_diversity.js <specs.jsonl> [--max-share 0.40] [--quiet]
//
// Accepts either a plain specs jsonl or a run log whose lines are prefixed
// "SPEC_JSONL " (the generator's own log form). Exit 0 = safe to bank.

const fs = require('node:fs')

const args = process.argv.slice(2)
const path = args.find((a) => !a.startsWith('--'))
const msIdx = args.indexOf('--max-share')
const MAX_SHARE = msIdx > -1 ? Number(args[msIdx + 1]) : 0.40
const QUIET = args.includes('--quiet')

if (!path || !Number.isFinite(MAX_SHARE) || MAX_SHARE <= 0 || MAX_SHARE > 1) {
  console.error('usage: check_spec_numeric_diversity.js <specs.jsonl> [--max-share 0.40] [--quiet]')
  process.exit(2)
}

let raw
try { raw = fs.readFileSync(path, 'utf8') } catch (e) { console.error(`cannot read ${path}: ${e.message}`); process.exit(2) }

const specs = []
let skipped = 0
for (const line0 of raw.split('\n')) {
  const line = line0.trim().replace(/^SPEC_JSONL\s+/, '')
  if (!line || line[0] !== '{') { if (line0.trim()) skipped++; continue }
  try { specs.push(JSON.parse(line)) } catch { skipped++ }
}
if (!specs.length) { console.error(`no spec objects parsed from ${path}`); process.exit(2) }

const problems = []
const note = (msg) => problems.push(msg)

// ---- 1. numeric diversity ---------------------------------------------------
const GATED = [
  ['coverage_details.coverage', (b) => b.coverage_details && b.coverage_details.coverage],
  ['tests.tests_run', (b) => b.tests && b.tests.tests_run],
  ['bdd.scenarios_attempted', (b) => b.bdd && b.bdd.scenarios_attempted],
  ['independent_tests.duration_seconds', (b) => b.independent_tests && b.independent_tests.duration_seconds],
]
const rows = []
for (const [label, pick] of GATED) {
  const vals = specs.map((s) => pick(s.bundle_spec || {})).filter((v) => typeof v === 'number')
  if (!vals.length) { rows.push([label, 0, 0, '-', '-', 'skip (field absent)']); continue }
  const h = new Map()
  for (const v of vals) h.set(v, (h.get(v) || 0) + 1)
  const sorted = [...h.entries()].sort((a, b) => b[1] - a[1])
  const [topVal, topN] = sorted[0]
  const share = topN / vals.length
  const bad = share > MAX_SHARE
  rows.push([label, vals.length, h.size, String(topVal), `${(share * 100).toFixed(1)}%`,
    bad ? 'FAIL' : 'ok', sorted.slice(0, 6).map(([v, n]) => `${v}x${n}`).join(' ')])
  if (bad) note(`MONOCULTURE ${label}: value ${topVal} covers ${topN}/${vals.length} bundles (${(share * 100).toFixed(1)}% > ${(MAX_SHARE * 100).toFixed(0)}%)`)
}

// ---- 2. evidence coherence --------------------------------------------------
const VERDICT_RE = /\b\d+\s+(passed|failed|error|errors)\b/i
const ELAPSED_RE = /\bin\s+(\d+(?:\.\d+)?)\s*s\b/i
let bddChecked = 0, absChecked = 0
const absSummaryIds = new Map() // test_output_summary -> [scenario ids] over signal_absent bundles
for (const s of specs) {
  const id = s.scenario_id || s.task_id || '<no id>'
  const b = s.bundle_spec || {}
  const bdd = b.bdd
  if (bdd) {
    bddChecked++
    const f = Array.isArray(bdd.failures) ? bdd.failures.length : null
    const sum = (bdd.scenarios_passed || 0) + (bdd.scenarios_failed || 0) + (bdd.scenarios_pending || 0)
    if (sum !== bdd.scenarios_attempted) note(`BDD ${id}: attempted=${bdd.scenarios_attempted} but passed+failed+pending=${sum}`)
    if (f !== null && f !== bdd.scenarios_failed) note(`BDD ${id}: scenarios_failed=${bdd.scenarios_failed} but ${f} failure(s) itemized`)
    if ((bdd.scenarios_passed || 0) < 0 || (bdd.scenarios_failed || 0) < 0) note(`BDD ${id}: negative count`)
  }
  const it = b.independent_tests
  if (it && it.signal_absent === true) {
    absChecked++
    const sm = it.test_output_summary || ''
    absSummaryIds.set(sm, (absSummaryIds.get(sm) || []).concat(id))
    if (VERDICT_RE.test(sm)) note(`ABSENT-SIGNAL ${id}: summary states a verdict while signal_absent=true -> ${JSON.stringify(sm.slice(0, 90))}`)
    const m = ELAPSED_RE.exec(sm)
    if (m && typeof it.duration_seconds === 'number') {
      const elapsed = Number(m[1]), d = it.duration_seconds
      if (Math.abs(elapsed - d) > Math.max(1, 0.5 * d)) note(`ABSENT-SIGNAL ${id}: summary says "in ${elapsed}s" but duration_seconds=${d}`)
    }
  }
  if (it && it.signal_absent === false && it.tests_passed === false && !VERDICT_RE.test(it.test_output_summary || '') && !/fail|error/i.test(it.test_output_summary || '')) {
    note(`SIGNAL ${id}: independent run failed with a summary that shows no failure -> ${JSON.stringify((it.test_output_summary || '').slice(0, 90))}`)
  }
}

// ---- 3. absent-signal prose uniqueness --------------------------------------
// build_v4_sft.py quotes test_output_summary verbatim in the g6 locus; a
// summary shared across signal_absent bundles becomes a duplicate locus and
// the build's hard 'duplicate loci across rows' SystemExit at the next regen.
for (const [sm, ids] of absSummaryIds) {
  if (ids.length > 1) {
    note(`ABSENT-SIGNAL DUPLICATE SUMMARY across ${ids.join(', ')}: ${JSON.stringify(sm.slice(0, 90))} — build_v4_sft.py derives the g6 locus verbatim from this summary, so these rows collide into duplicate loci`)
  }
}

// ---- report -----------------------------------------------------------------
if (!QUIET) {
  console.log(`spec file : ${path}`)
  console.log(`parsed    : ${specs.length} specs (${skipped} non-spec line(s) skipped)`)
  console.log(`gate      : no single value may exceed ${(MAX_SHARE * 100).toFixed(0)}% of bundles\n`)
  console.log('  field                                 n  distinct  top    share    verdict  histogram(top6)')
  for (const r of rows) {
    console.log(`  ${String(r[0]).padEnd(34)}${String(r[1]).padStart(5)}${String(r[2]).padStart(10)}  ${String(r[3]).padEnd(7)}${String(r[4]).padStart(6)}   ${String(r[5]).padEnd(8)} ${r[6] || ''}`)
  }
  console.log(`\ncoherence : ${bddChecked} bdd block(s), ${absChecked} absent-signal block(s) checked`)
  console.log(`prose     : ${absChecked} absent-signal summar${absChecked === 1 ? 'y' : 'ies'}, ${absSummaryIds.size} distinct (duplicates become duplicate v4 loci)`)
}

if (problems.length) {
  const shown = problems.slice(0, 25)
  console.log('\nPROBLEMS:')
  for (const p of shown) console.log('  - ' + p)
  if (problems.length > shown.length) console.log(`  ... and ${problems.length - shown.length} more`)
  console.log(`\nFAIL: ${problems.length} problem(s) — do NOT bank this corpus`)
  process.exit(1)
}
console.log('\nPASS: numeric spread and evidence coherence within gate')
process.exit(0)
