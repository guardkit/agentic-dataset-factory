"""Gold-negative tests — the 4 reconstruct field-by-field per SPEC and validate.

Also the WS2-B11 on-disk-survival deliverable: GN-3 (10AC/TASK-QAV-005) survives VERBATIM
as ``coach_evidence_turn_2.json``; when the real guardkit corpus is present the builder
prefers those bytes ("verbatim beats reconstruction").
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qav.contracts import extract_bundle, extract_label, validate_row
from qav.gold_negatives import (
    GN1,
    GN2,
    GN3,
    GN4,
    GOLD_NEGATIVES,
    build_gold_negative_row,
    build_gold_negative_rows,
    probe_survival,
)

CORPUS = {
    "guardkit": Path("/home/richardwoollcott/Projects/appmilla_github/guardkit"),
    "study-tutor": Path("/home/richardwoollcott/Projects/appmilla_github/study-tutor"),
    "forge": Path("/home/richardwoollcott/Projects/appmilla_github/forge"),
}


def test_four_gold_negatives():
    assert [gn.gn_id for gn in GOLD_NEGATIVES] == ["GN-1", "GN-2", "GN-3", "GN-4"]


def test_all_reconstruct_and_validate():
    rows = build_gold_negative_rows()  # no corpus -> reconstructed
    assert len(rows) == 4
    for row in rows:
        validate_row(row)
        meta = row["metadata"]
        assert meta["split"] == "eval_qav"
        assert meta["generation_mode"] == "gold_negative"
        assert extract_label(row)["verdict"] == "reject"


def test_classes_and_sources_match_spec():
    assert (GN1.dc_class, GN1.ground_truth_source) == ("DC-08", "operator_caught")
    assert (GN2.dc_class, GN2.ground_truth_source) == ("DC-03", "operator_caught")
    assert (GN3.dc_class, GN3.ground_truth_source) == ("DC-03", "merge_review_caught")
    assert (GN4.dc_class, GN4.ground_truth_source) == ("DC-03", "merge_review_caught")


def test_gn1_bundle_reconstructs_field_by_field():
    b = GN1.reconstructed_bundle
    assert b["gathering_status"] == "complete"
    assert b["bdd"] is None and b["bdd_authoring_sweep"] is None  # the load-bearing absence
    assert b["independent_tests"]["tests_passed"] == 109  # the integration-green trap


def test_gn2_bundle_reconstructs_field_by_field():
    b = GN2.reconstructed_bundle
    assert b["tests"]["tests_passed"] == 1049  # canonical green-looking bundle
    assert b["wiring"] is None and b["runtime_parity"] is None  # no cross-file / parity witness


def test_gn3_bundle_reconstructs_field_by_field():
    b = GN3.reconstructed_bundle
    assert b["behavioural_oracle"] is None  # the field this task was supposed to make real


def test_gn4_bundle_reconstructs_field_by_field():
    b = GN4.reconstructed_bundle
    assert b["stub_scan"] is None and b["wiring"] is None
    assert b["tests"]["passed"] is True  # green suites over a soft-failed TypeError


@pytest.mark.skipif(
    not (CORPUS["guardkit"] / ".guardkit").exists(),
    reason="guardkit corpus not present on this host",
)
def test_gn3_survives_verbatim_on_disk():
    survival = probe_survival(CORPUS)
    # GN-3's approving-turn bundle is the one confirmed on disk 2026-07-08.
    if survival["GN-3"]["fidelity"] != "verbatim":
        pytest.skip("GN-3 verbatim bundle not found in this checkout")
    row = build_gold_negative_row(GN3, CORPUS)
    validate_row(row)
    assert row["metadata"]["reconstruction_fidelity"] == "verbatim"
    assert row["metadata"]["bundle_schema_sha"] == "888906f2"
    # verbatim bytes carry the real bundle; behavioural_oracle is the null tell
    assert extract_bundle(row).get("behavioural_oracle") is None
