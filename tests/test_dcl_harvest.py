"""W2c — harvested real briefs into the DCL corpus (author-only, M-22 gated).

ZERO real model calls: the Player/Coach are injected stubs (the repo idiom). Covers the
loader (accept / refuse-loud / malformed / ignore-non-brief), the harvested provenance
contract, the author-only generator routing, and the synthetic-path regression.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from dcl import contracts
from dcl.briefs import load_briefs, render_reference_capability
from dcl.contracts import (
    RowValidationError,
    build_author_row,
    build_provenance,
    validate_row,
)
from dcl.generate import GenerateConfig, run_generation
from dcl.harvest import HarvestedBrief, load_harvested_briefs

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")

# A brief whose stub-authored capability compiles clean (the Player ignores the prompt and
# returns this fixed valid capability — the compile gate is the real DCL compiler).
_SYNTH_BRIEF = load_briefs(enforce_denylist=False)[0]
VALID_FENCE = f"```dcl\n{render_reference_capability(_SYNTH_BRIEF)}\n```"

CLEAN = {
    "kind": "brief",
    "correlation_id": "run-abc",
    "feature_id": "loyalty-points",
    "task_id": "T-1",
    "request_text": "Let customers accrue loyalty points on each completed order.",
    "machine_criteria": "given a completed order\nthen points are credited to the customer",
    "repo": "acme/shop",
    "spec_track": "dcl",
    "source": "plan-commit-harvest",
}
# request_text carries the frozen-exam identity token "stats" -> M-22 must refuse.
CONTAMINATED = {
    "kind": "brief",
    "correlation_id": "run-xyz",
    "feature_id": "metrics",
    "task_id": None,
    "request_text": "Expose a /stats endpoint returning request statistics for the service.",
    "machine_criteria": "given a GET /stats\nthen counts are returned",
    "repo": "acme/telemetry",
    "spec_track": "dcl",
    "source": "plan-commit-harvest",
}
SHADOW = {"kind": "compile_shadow", "correlation_id": "run-abc", "artifact": "x.dcl", "ok": True}


def _queue(tmp_path: Path) -> Path:
    """A fixture queue: 1 clean brief, 1 contaminated brief, 1 malformed line, 1 shadow row."""
    lines = [
        json.dumps(CLEAN),
        json.dumps(CONTAMINATED),
        "{ this is not valid json",  # malformed
        json.dumps(SHADOW),          # non-brief kind -> ignored
    ]
    p = tmp_path / "queue.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def _cfg(tmp_path, **kw):
    kw.setdefault("output_dir", str(tmp_path / "out"))
    kw.setdefault("holdout_fraction", 0.0)  # deterministic: everything to train
    return GenerateConfig(**kw)


class StubPlayer:
    def __init__(self, default=VALID_FENCE):
        self.default = default
        self.calls = []

    def complete(self, system, user):
        self.calls.append((system, user))
        return self.default


class StubCoach:
    def __init__(self, decision="accept"):
        self.decision = decision

    def assess(self, brief, capability_text):
        return contracts_verdict(self.decision)


def contracts_verdict(decision):
    from dcl.generate import CoachVerdict
    return CoachVerdict(decision=decision, score=9 if decision == "accept" else 3, reasons=[])


# --------------------------------------------------------------------------------------
# Loader: accept clean, refuse-loud contaminated, count malformed, ignore non-brief kinds.
# --------------------------------------------------------------------------------------
def test_loader_accepts_clean_refuses_contaminated_counts_malformed(tmp_path):
    accepted, rejects = load_harvested_briefs(_queue(tmp_path))

    # exactly one clean brief yielded
    assert len(accepted) == 1
    b = accepted[0]
    assert isinstance(b, HarvestedBrief)
    assert b.harvested is True
    assert b.id == "harvest-run-abc-loyalty-points"
    assert b.request_text in b.brief_text
    assert "loyalty points" in b.brief_text.lower()
    assert "Machine acceptance criteria" in b.brief_text  # criteria rendered readably

    # one refused-loud (with hit detail), one malformed counted; shadow ignored (neither list)
    contaminated = [r for r in rejects if r["reason"] == "contaminated"]
    malformed = [r for r in rejects if r["reason"] == "malformed"]
    assert len(contaminated) == 1
    assert len(malformed) == 1
    assert contaminated[0]["feature_id"] == "metrics"
    assert contaminated[0]["repo"] == "acme/telemetry"
    assert any("stats" in h for h in contaminated[0]["hits"])  # the hit detail is recorded
    assert malformed[0]["line"] == 3


def test_loader_uses_injected_scan(tmp_path):
    # denylist_scan is the injection seam — a scan that hits everything refuses all briefs.
    accepted, rejects = load_harvested_briefs(_queue(tmp_path), denylist_scan=lambda t: ["forced hit"])
    assert accepted == []
    assert sum(1 for r in rejects if r["reason"] == "contaminated") == 2


def test_loader_brief_missing_required_field_is_malformed(tmp_path):
    p = tmp_path / "q.jsonl"
    p.write_text(json.dumps({"kind": "brief", "correlation_id": "r", "feature_id": "f"}) + "\n")
    accepted, rejects = load_harvested_briefs(p)  # missing request_text
    assert accepted == []
    assert rejects[0]["reason"] == "malformed"


# --------------------------------------------------------------------------------------
# Provenance contract — harvested requires {repo, feature, run}; forbidden otherwise.
# --------------------------------------------------------------------------------------
def test_build_provenance_harvested_requires_extra_keys():
    prov = build_provenance("harvested", repo="acme/shop", feature="f", run="r")
    assert prov == {
        "source": "harvested", "vocab_pin": "4f9fbe56", "compiler_pin": "4f9fbe56",
        "repo": "acme/shop", "feature": "f", "run": "r",
    }
    with pytest.raises(RowValidationError):
        build_provenance("harvested", repo="acme/shop")  # missing feature+run


def test_build_provenance_extra_keys_forbidden_on_synthetic():
    with pytest.raises(RowValidationError):
        build_provenance("synthetic-brief", repo="acme/shop", feature="f", run="r")


def test_validate_row_accepts_harvested_author_row():
    prov = build_provenance("harvested", repo="acme/shop", feature="loyalty", run="run-abc")
    row = build_author_row(
        brief="Accrue loyalty points.", dcl_text="language dcl 1.0\n\nactor C is human\n",
        vocab_reference="# vocab\n", split="train", provenance=prov,
    )
    validate_row(row)  # no raise
    assert row["metadata"]["provenance"]["source"] == "harvested"
    assert row["metadata"]["provenance"]["repo"] == "acme/shop"


def test_validate_row_rejects_harvested_missing_extra_keys():
    row = build_author_row(brief="x", dcl_text="language dcl 1.0\n", vocab_reference="v", split="train")
    row["metadata"]["provenance"]["source"] = "harvested"  # now missing repo/feature/run
    with pytest.raises(RowValidationError):
        validate_row(row)


# --------------------------------------------------------------------------------------
# Generator: author row minted from a clean harvested brief; repair skipped; contaminated
# never reaches a row.
# --------------------------------------------------------------------------------------
@requires_node
def test_harvested_brief_mints_author_row_with_provenance(tmp_path):
    accepted, rejects = load_harvested_briefs(_queue(tmp_path))
    summary = run_generation(
        _cfg(tmp_path, mode="both"), player=StubPlayer(), coach=StubCoach("accept"),
        briefs=accepted, harvest_rejects=rejects, created="2026-07-18", factory_sha="t",
    )
    assert summary.author_accepted == 1
    assert summary.repair_written == 0                 # author-only: no repair from harvested
    assert summary.harvested_repair_skipped == 1
    assert summary.harvested_scanned == 2              # 1 accepted + 1 refused
    assert summary.harvested_refused == 1
    assert summary.harvested_malformed == 1

    train = (tmp_path / "out" / "train.jsonl").read_text().splitlines()
    assert len(train) == 1
    row = json.loads(train[0])
    validate_row(row)
    prov = row["metadata"]["provenance"]
    assert prov["source"] == "harvested"
    assert prov == {
        "source": "harvested", "vocab_pin": "4f9fbe56", "compiler_pin": "4f9fbe56",
        "repo": "acme/shop", "feature": "loyalty-points", "run": "run-abc",
    }
    assert row["metadata"]["mode"] == "dcl_author"


@requires_node
def test_contaminated_brief_never_reaches_a_row(tmp_path):
    accepted, rejects = load_harvested_briefs(_queue(tmp_path))
    run_generation(
        _cfg(tmp_path, mode="both"), player=StubPlayer(), coach=StubCoach("accept"),
        briefs=accepted, harvest_rejects=rejects, created="2026-07-18", factory_sha="t",
    )
    all_rows = (tmp_path / "out" / "train.jsonl").read_text()
    # nothing from the refused telemetry brief — not its run id, not the /stats token.
    assert "run-xyz" not in all_rows
    assert "/stats" not in all_rows
    assert "acme/telemetry" not in all_rows


@requires_node
def test_manifest_counts_and_harvest_block(tmp_path):
    accepted, rejects = load_harvested_briefs(_queue(tmp_path))
    run_generation(
        _cfg(tmp_path, mode="both"), player=StubPlayer(), coach=StubCoach("accept"),
        briefs=accepted, harvest_rejects=rejects, created="2026-07-18", factory_sha="t",
    )
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    from dcl.manifest import validate_manifest
    validate_manifest(manifest)  # embedded contamination check passes + private

    src_counts = manifest["counts"]["train"]["by_provenance_source"]
    assert src_counts["harvested"] == 1
    assert src_counts["synthetic-brief"] == 0
    harvest = manifest["harvest"]
    assert harvest["refused"] == 1
    assert harvest["malformed"] == 1
    assert harvest["repair_skipped_author_only"] == 1
    assert "AUTHOR-ONLY" in harvest["note"]


# --------------------------------------------------------------------------------------
# Synthetic-path regression: default config -> load_briefs, synthetic-brief provenance,
# byte-identical row for a fixed stub. The harvest block is OMITTED entirely.
# --------------------------------------------------------------------------------------
@requires_node
def test_synthetic_path_byte_identical(tmp_path):
    brief = _SYNTH_BRIEF
    # default: NO briefs kwarg would load the whole bank; pass the single brief to pin output.
    summary = run_generation(
        _cfg(tmp_path, mode="dcl_author"), player=StubPlayer(), coach=StubCoach("accept"),
        briefs=[brief], created="2026-07-18", factory_sha="t",
    )
    assert summary.author_accepted == 1
    assert summary.harvested_scanned == 0            # no harvested accounting on the synthetic path
    assert summary.harvested_repair_skipped == 0

    produced = json.loads((tmp_path / "out" / "train.jsonl").read_text().splitlines()[0])
    assert produced["metadata"]["provenance"] == {
        "source": "synthetic-brief", "vocab_pin": "4f9fbe56", "compiler_pin": "4f9fbe56",
    }
    # byte-identical to a directly-built synthetic author row for the same brief+capability.
    reference = build_author_row(
        brief=brief.brief_text, dcl_text=render_reference_capability(brief),
        vocab_reference=contracts.load_vocab_reference(), split="train",
    )
    assert produced == reference

    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert "harvest" not in manifest                 # omitted on synthetic-only runs


def test_config_from_yaml_reads_briefs_source_and_queue(tmp_path):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        "generation:\n  briefs_source: harvested\n"
        "corpus:\n  harvest_queue: some/queue.jsonl\n",
        encoding="utf-8",
    )
    cfg = GenerateConfig.from_yaml(cfg_path)
    assert cfg.briefs_source == "harvested"
    assert cfg.harvest_queue == "some/queue.jsonl"

    # default config is unchanged: synthetic, no queue.
    empty = tmp_path / "empty.yaml"
    empty.write_text("generation: {}\n", encoding="utf-8")
    d = GenerateConfig.from_yaml(empty)
    assert d.briefs_source == "synthetic"
    assert d.harvest_queue is None


def test_loader_accepts_kindless_forge_writer_row(tmp_path):
    """forge's plan-commit harvest writer stamps ``source`` but no ``kind``.

    The first REAL harvested row (2026-07-18, FEAT-B9AE) had exactly this
    shape; the loader must accept it by the source discriminator.
    """
    forge_row = {k: v for k, v in CLEAN.items() if k != "kind"}
    assert "kind" not in forge_row and forge_row["source"] == "plan-commit-harvest"
    p = tmp_path / "queue.jsonl"
    p.write_text(json.dumps(forge_row) + "\n", encoding="utf-8")
    briefs, rejects = load_harvested_briefs(p)
    assert len(briefs) == 1 and rejects == []
    assert briefs[0].brief_text.startswith("Let customers accrue loyalty points")


def test_schema_header_stripped_before_scan(tmp_path):
    """The pass-bar seed's ``format_version:`` header must not trip M-22.

    Live-caught 2026-07-18: every real harvested brief opens its criteria with
    the F-format schema header, whose key tokenizes to the denylisted word
    "version" — 2/2 real briefs refused before this strip. Real version-related
    CONTENT elsewhere in the criteria must still refuse.
    """
    ok_row = {k: v for k, v in CLEAN.items() if k != "kind"}
    ok_row["machine_criteria"] = 'format_version: "1.0"\ncriteria:\n- the order total is recalculated'
    bad_row = dict(ok_row)
    bad_row["feature_id"] = "versionish"
    bad_row["machine_criteria"] = 'format_version: "1.0"\ncriteria:\n- mirrors the /version endpoint body'
    p = tmp_path / "queue.jsonl"
    p.write_text(json.dumps(ok_row) + "\n" + json.dumps(bad_row) + "\n", encoding="utf-8")
    briefs, rejects = load_harvested_briefs(p)
    assert len(briefs) == 1 and "format_version" not in briefs[0].brief_text
    assert len(rejects) == 1 and rejects[0]["reason"] == "contaminated"
