"""Per-sample dataset gates.

``gates.quote_gate`` — the fabrication (quote-verification) gate plus the
run-level gate report and the DuplicateDetector wiring helpers.  Applied
by the orchestrator between Coach acceptance and the write, in both the
sequential and the two-window batch loops.
"""
