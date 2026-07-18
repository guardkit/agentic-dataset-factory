"""Offline generation driver — author + repair paths against LOCAL STUB clients.

ZERO real model calls: the Player/teacher/Coach are injected stubs. Covers the happy author
path, the compile-gate retry, a coach rejection, the repair path, and the write/manifest
surface. Requires ``node`` (the compile gate is the real DCL compiler).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from dcl import contracts
from dcl.briefs import load_briefs, render_reference_capability
from dcl.generate import (
    CoachVerdict,
    GenerateConfig,
    GenerationSummary,
    extract_dcl,
    run_generation,
)

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")

BRIEF = load_briefs(enforce_denylist=False)[0]
VALID_FENCE = f"```dcl\n{render_reference_capability(BRIEF)}\n```"
INVALID_FENCE = "```dcl\nlanguage dcl 1.0\n\nactor Bad is machine\n```"


class StubPlayer:
    def __init__(self, responses=None, default=VALID_FENCE):
        self.responses = list(responses or [])
        self.default = default
        self.calls = []

    def complete(self, system, user):
        self.calls.append((system, user))
        return self.responses.pop(0) if self.responses else self.default


class StubCoach:
    def __init__(self, decision="accept"):
        self.decision = decision
        self.calls = 0

    def assess(self, brief, capability_text):
        self.calls += 1
        return CoachVerdict(decision=self.decision, score=9 if self.decision == "accept" else 3,
                            reasons=[] if self.decision == "accept" else ["missing the emitted event"])


def _cfg(tmp_path, **kw):
    kw.setdefault("output_dir", str(tmp_path / "out"))
    kw.setdefault("holdout_fraction", 0.0)  # deterministic: everything to train for assertions
    return GenerateConfig(**kw)


def test_extract_dcl():
    assert extract_dcl(VALID_FENCE).startswith("language dcl 1.0")
    assert extract_dcl("no fence here") is None


@requires_node
def test_author_happy_path(tmp_path):
    player, coach = StubPlayer(), StubCoach("accept")
    summary = run_generation(_cfg(tmp_path, mode="dcl_author"), player=player, coach=coach,
                             briefs=[BRIEF], created="2026-07-17", factory_sha="t")
    assert summary.author_accepted == 1
    assert summary.author_rejected == 0
    train = (tmp_path / "out" / "train.jsonl").read_text().splitlines()
    assert len(train) == 1
    row = json.loads(train[0])
    contracts.validate_row(row)
    assert row["metadata"]["mode"] == "dcl_author"


@requires_node
def test_author_compile_gate_retry(tmp_path):
    # first Player output does NOT compile -> diagnostics fed back -> second compiles.
    player = StubPlayer(responses=[INVALID_FENCE, VALID_FENCE])
    coach = StubCoach("accept")
    summary = run_generation(_cfg(tmp_path, mode="dcl_author", max_format_retries=3),
                             player=player, coach=coach, briefs=[BRIEF],
                             created="2026-07-17", factory_sha="t")
    assert summary.author_accepted == 1
    assert len(player.calls) == 2  # one failed compile, one success
    # the second prompt carried the verbatim diagnostics as repair feedback
    assert "Compiler feedback" in player.calls[1][1]
    assert "DCL_" in player.calls[1][1]


@requires_node
def test_author_coach_reject(tmp_path):
    player, coach = StubPlayer(), StubCoach("revise")
    summary = run_generation(_cfg(tmp_path, mode="dcl_author", coach_max_turns=2),
                             player=player, coach=coach, briefs=[BRIEF],
                             created="2026-07-17", factory_sha="t")
    assert summary.author_accepted == 0
    assert summary.author_rejected == 1
    rejected = (tmp_path / "out" / "rejected.jsonl").read_text().splitlines()
    assert len(rejected) == 1
    assert json.loads(rejected[0])["reason"] == "coach_rejected"


@requires_node
def test_author_compile_gate_exhausted(tmp_path):
    player = StubPlayer(default=INVALID_FENCE)  # never compiles
    coach = StubCoach("accept")
    summary = run_generation(_cfg(tmp_path, mode="dcl_author", max_format_retries=2),
                             player=player, coach=coach, briefs=[BRIEF],
                             created="2026-07-17", factory_sha="t")
    assert summary.author_accepted == 0
    assert summary.author_rejected == 1
    rec = json.loads((tmp_path / "out" / "rejected.jsonl").read_text().splitlines()[0])
    assert rec["reason"] == "compile_gate_exhausted"


@requires_node
def test_repair_path_mints_reasoning_rows(tmp_path):
    teacher = StubPlayer(default="<think>Restore the closed-vocabulary literal named in the "
                         "diagnostics; change nothing else.</think>")
    summary = run_generation(_cfg(tmp_path, mode="dcl_repair"), player=teacher,
                             coach=StubCoach("accept"), briefs=[BRIEF],
                             created="2026-07-17", factory_sha="t")
    # brief-001 render carries every anchor except retry (no retry combo) -> 9 recipes apply.
    assert summary.repair_written >= 8
    assert summary.repair_skipped_anchor >= 1  # retry-no-idempotency has no anchor here
    train = (tmp_path / "out" / "train.jsonl").read_text().splitlines()
    for line in train:
        row = json.loads(line)
        contracts.validate_row(row)
        assert row["metadata"]["mode"] == "dcl_repair"
        assert row["metadata"]["type"] == "reasoning"
        assert row["metadata"]["recipe_id"] in __import__("dcl").RECIPES


def _variant_fence(tag):
    """A distinct-but-still-compiling completion of BRIEF's capability (a `//` comment)."""
    return "```dcl\n" + render_reference_capability(BRIEF).replace(
        "language dcl 1.0", f"language dcl 1.0\n// {tag}", 1
    ) + "\n```"


@requires_node
def test_author_reps_default_one_byte_identical(tmp_path):
    # author_reps default (1) reproduces today's behaviour: one authoring, one row.
    player, coach = StubPlayer(), StubCoach("accept")
    summary = run_generation(_cfg(tmp_path, mode="dcl_author"), player=player, coach=coach,
                             briefs=[BRIEF], created="2026-07-17", factory_sha="t")
    assert summary.author_accepted == 1
    assert summary.author_deduped == 0
    assert len(player.calls) == 1  # exactly one authoring call for the one brief
    assert len((tmp_path / "out" / "train.jsonl").read_text().splitlines()) == 1


@requires_node
def test_author_reps_distinct_completions_mint_distinct_rows(tmp_path):
    # author_reps=3 with three DIFFERENT valid completions -> three distinct rows, distinct row_ids.
    player = StubPlayer(responses=[_variant_fence("rep a"), _variant_fence("rep b"), _variant_fence("rep c")])
    coach = StubCoach("accept")
    summary = run_generation(_cfg(tmp_path, mode="dcl_author", author_reps=3),
                             player=player, coach=coach, briefs=[BRIEF],
                             created="2026-07-17", factory_sha="t")
    assert summary.author_accepted == 3
    assert summary.author_deduped == 0
    rows = [json.loads(x) for x in (tmp_path / "out" / "train.jsonl").read_text().splitlines()]
    assert len(rows) == 3
    ids = {r["metadata"]["row_id"] for r in rows}
    assert len(ids) == 3  # distinct completions -> distinct content-addressed row_ids
    for r in rows:
        contracts.validate_row(r)
        assert r["metadata"]["mode"] == "dcl_author"


@requires_node
def test_author_reps_identical_completions_dedupe(tmp_path):
    # author_reps=3 but the model returns the SAME completion each call -> one row, two deduped.
    player = StubPlayer()  # default VALID_FENCE every call
    coach = StubCoach("accept")
    summary = run_generation(_cfg(tmp_path, mode="dcl_author", author_reps=3),
                             player=player, coach=coach, briefs=[BRIEF],
                             created="2026-07-17", factory_sha="t")
    assert len(player.calls) == 3  # three independent authorings happened
    assert summary.author_accepted == 1  # only the first distinct row is written/counted
    assert summary.author_deduped == 2   # the two identical reps deduped
    assert len((tmp_path / "out" / "train.jsonl").read_text().splitlines()) == 1


@requires_node
def test_write_paths_and_manifest(tmp_path):
    briefs = load_briefs(enforce_denylist=False)[:3]
    summary = run_generation(_cfg(tmp_path, mode="both", holdout_fraction=0.1),
                             player=StubPlayer(), coach=StubCoach("accept"),
                             teacher=StubPlayer(default="<think>fix</think>"), briefs=briefs,
                             created="2026-07-17", factory_sha="t")
    out = tmp_path / "out"
    assert (out / "train.jsonl").is_file()
    assert (out / "eval_dcl.jsonl").is_file()
    assert (out / "rejected.jsonl").is_file()
    manifest = json.loads((out / "manifest.json").read_text())
    from dcl.manifest import validate_manifest
    validate_manifest(manifest)  # embedded contamination check passes + private
    assert summary.train + summary.eval_dcl >= 3


@requires_node
def test_backup_convention(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "train.jsonl").write_text("PRIOR\n")
    run_generation(_cfg(tmp_path, mode="dcl_author"), player=StubPlayer(), coach=StubCoach("accept"),
                   briefs=[BRIEF], created="2026-07-17", factory_sha="t")
    assert (out / "train.jsonl.bak").read_text() == "PRIOR\n"  # prior file backed up


def test_author_row_conforms_to_existing_write_output_tool(tmp_path):
    # The row shape passes the repo's existing write_output validator conventions.
    from pathlib import Path as _P
    from domain_config.parser import parse_goal_md
    from tools.write_output import create_write_output_tool

    cfg = parse_goal_md(_P(__file__).resolve().parent.parent / "domains" / "dcl-capability-language" / "GOAL.md")
    row = contracts.build_author_row(
        brief="Place an order.", dcl_text="language dcl 1.0\n\nactor C is human\n",
        vocab_reference="# vocab\n", split="train",
    )
    tool = create_write_output_tool(tmp_path, cfg.metadata_schema)
    result = tool.invoke({"example_json": json.dumps(row)})
    assert result.startswith("Written to"), result
    assert (tmp_path / "train.jsonl").is_file()
