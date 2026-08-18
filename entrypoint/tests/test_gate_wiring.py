"""Wiring tests — the Stage-2 gates at the orchestrator choke point.

Hermetic (mock agents, no endpoints, no model inference).  Covers:

- Sequential loop: a gate-failed sample routes back into the revise loop
  with the fabricated span named in the feedback (mocked orchestrator
  round trip), and the corrected revision is written.
- Dedup wiring: a duplicate accepted sample routes to revision; hashes
  are recorded only after successful writes.
- The no-corpus subject: unverifiable is counted, the sample is written.
- The per-run gate report lands in the run output dir.
- Batch window 2: the gate runs between acceptance validation and the
  ``accept_pending`` pin; a flagged row becomes the next pass, and the
  revised row is accepted in pass 2.
- Gates absent (None): both loops take the exact pre-gate paths.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from config.coach_verdict import CoachVerdict
from config.models import BatchConfig, GenerationConfig, QuoteGateConfig
from domain_config.models import GenerationTarget
from entrypoint.batch_loop import run_batch_generation_loop
from entrypoint.batch_state import BATCH_STATE_FILENAME
from entrypoint.generation_loop import (
    _process_single_target,
    run_generation_loop,
)
from gates.quote_gate import GATE_REPORT_FILENAME, GateReport, QuoteGate
from synthesis.validator import DuplicateDetector

# ---------------------------------------------------------------------------
# Fixtures (the TASK-G4D-006 Macbeth fabrication + its real source)
# ---------------------------------------------------------------------------

FABRICATED_SPAN = "screw your courage to the hope of belief"
REAL_MACBETH = (
    "We fail! But screw your courage to the sticking-place, And we'll not fail."
)


def _make_store(tmp_path: Path) -> Path:
    store = tmp_path / "english_store"
    if (store / "chroma.sqlite3").exists():  # idempotent per test
        return store
    store.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(store / "chroma.sqlite3")
    con.execute(
        "create table embedding_metadata (id integer, key text, string_value text)"
    )
    con.execute(
        "insert into embedding_metadata values (0, 'chunk_json', ?)",
        (
            json.dumps(
                {"text": REAL_MACBETH, "text_name": "macbeth", "chunk_index": 0}
            ),
        ),
    )
    con.commit()
    con.close()
    return store


def _make_quote_gate(tmp_path: Path) -> QuoteGate:
    return QuoteGate(
        QuoteGateConfig(
            enabled=True,
            corpus_stores={"english": str(_make_store(tmp_path))},
            default_subject="english",
        )
    )


def _example_json(assistant_content: str, metadata: dict | None = None) -> str:
    return json.dumps(
        {
            "messages": [
                {"role": "system", "content": "You are a GCSE tutor."},
                {"role": "user", "content": "Analyse the quotation."},
                {"role": "assistant", "content": assistant_content},
            ],
            "metadata": metadata or {"layer": "behaviour", "type": "direct"},
        }
    )


FABRICATED_EXAMPLE = _example_json(f'Lady Macbeth urges: "{FABRICATED_SPAN}".')
CORRECTED_EXAMPLE = _example_json(
    'Lady Macbeth urges: "But screw your courage to the sticking-place".'
)
CLEAN_EXAMPLE = _example_json("A clean analysis without any quotation at all.")
OTHER_CLEAN_EXAMPLE = _example_json("A different clean analysis, new words.")


def _make_target(count: int = 1) -> GenerationTarget:
    return GenerationTarget(
        category="Literary analysis", type="reasoning", count=count
    )


def _accept_verdict() -> CoachVerdict:
    return CoachVerdict(
        decision="accept",
        score=4,
        layer_correct=True,
        type_correct=True,
        criteria_met={"accuracy": True},
        issues=[],
        quality_assessment="Good example",
    )


def _make_config(**overrides: Any) -> GenerationConfig:
    defaults = {
        "max_turns": 3,
        "llm_retry_attempts": 0,
        "llm_retry_backoff": 0.0,
        "llm_timeout": 300,
        "target_timeout": 60,
    }
    defaults.update(overrides)
    return GenerationConfig(**defaults)


def _make_player(responses: list[str]) -> AsyncMock:
    player = AsyncMock()
    player.ainvoke.side_effect = [
        {"messages": [MagicMock(content=r)]} for r in responses
    ]
    return player


def _make_coach(verdicts: list[CoachVerdict]) -> AsyncMock:
    coach = AsyncMock()
    coach.ainvoke.side_effect = [
        {"messages": [MagicMock(content=v.model_dump_json())]} for v in verdicts
    ]
    return coach


def _make_write_tool() -> MagicMock:
    write_tool = MagicMock()
    write_tool.invoke.return_value = "Written to output/train.jsonl (example #1)"
    return write_tool


def _make_output_manager() -> MagicMock:
    output_mgr = MagicMock()
    output_mgr.rejected_fh = MagicMock()
    return output_mgr


# ---------------------------------------------------------------------------
# Sequential loop — revise routing at the choke point
# ---------------------------------------------------------------------------


class TestSequentialQuoteGate:
    def test_fabrication_routes_to_revise_then_corrected_is_written(
        self, tmp_path
    ) -> None:
        """The mocked orchestrator round trip: fail -> revise -> pass."""
        quote_gate = _make_quote_gate(tmp_path)
        report = GateReport.load_or_new(tmp_path)
        player = _make_player([FABRICATED_EXAMPLE, CORRECTED_EXAMPLE])
        coach = _make_coach([_accept_verdict(), _accept_verdict()])
        write_tool = _make_write_tool()

        accepted, turns, history = asyncio.run(
            _process_single_target(
                player=player,
                coach=coach,
                target=_make_target(),
                target_index=0,
                total_targets=1,
                config=_make_config(),
                output_manager=_make_output_manager(),
                write_tool=write_tool,
                quote_gate=quote_gate,
                gate_report=report,
            )
        )

        assert accepted is True
        assert player.ainvoke.call_count == 2
        # The revise message names the fabricated span (coach_feedback).
        revise_message = player.ainvoke.call_args_list[1][0][0]["messages"][0][
            "content"
        ]
        assert FABRICATED_SPAN in revise_message
        assert "Fabrication gate failed" in revise_message
        # Only the corrected example was written.
        assert write_tool.invoke.call_count == 1
        written = write_tool.invoke.call_args[0][0]["example_json"]
        assert "sticking-place" in written
        # Rejection history carries the gate failure detail.
        assert any("quote_gate_error" in h for h in history)
        # Report: two checks — one revised, one passed.
        assert (report.checked, report.passed, report.revised) == (2, 1, 1)

    def test_unverifiable_subject_is_counted_not_blocked(self, tmp_path) -> None:
        quote_gate = _make_quote_gate(tmp_path)
        report = GateReport.load_or_new(tmp_path)
        biology_example = _example_json(
            'The textbook says "mitochondria are the powerhouse of cells".',
            metadata={
                "layer": "behaviour",
                "type": "direct",
                "subject": "biology",
            },
        )
        player = _make_player([biology_example])
        coach = _make_coach([_accept_verdict()])
        write_tool = _make_write_tool()

        accepted, _, _ = asyncio.run(
            _process_single_target(
                player=player,
                coach=coach,
                target=_make_target(),
                target_index=0,
                total_targets=1,
                config=_make_config(),
                output_manager=_make_output_manager(),
                write_tool=write_tool,
                quote_gate=quote_gate,
                gate_report=report,
            )
        )

        assert accepted is True
        assert write_tool.invoke.call_count == 1  # never blocked
        assert report.unverifiable == 1
        assert report.unverifiable_subjects == {"biology": 1}

    def test_gate_failure_to_max_turns_is_dropped(self, tmp_path) -> None:
        """A sample that never fixes its fabrication is terminally rejected
        and counted dropped via the run-loop rejection path."""
        quote_gate = _make_quote_gate(tmp_path)
        report = GateReport.load_or_new(tmp_path)
        player = _make_player([FABRICATED_EXAMPLE, FABRICATED_EXAMPLE])
        coach = _make_coach([_accept_verdict(), _accept_verdict()])
        write_tool = _make_write_tool()
        output_mgr = _make_output_manager()
        checkpoint = MagicMock()

        result = asyncio.run(
            run_generation_loop(
                player=player,
                coach=coach,
                targets=[_make_target()],
                config=_make_config(max_turns=2),
                checkpoint=checkpoint,
                output_manager=output_mgr,
                write_tool=write_tool,
                quote_gate=quote_gate,
                gate_report=report,
            )
        )

        assert result.rejected == 1
        assert write_tool.invoke.call_count == 0
        assert report.dropped == 1
        # The per-run report landed in the output dir.
        data = json.loads((tmp_path / GATE_REPORT_FILENAME).read_text())
        assert data["revised"] == 2
        assert data["dropped"] == 1


class TestSequentialDedup:
    def test_duplicate_routes_to_revise_and_distinct_is_written(
        self, tmp_path
    ) -> None:
        dup = DuplicateDetector()
        report = GateReport.load_or_new(tmp_path)
        # Target 0 accepted; target 1 first duplicates it, then revises.
        player = _make_player(
            [CLEAN_EXAMPLE, CLEAN_EXAMPLE, OTHER_CLEAN_EXAMPLE]
        )
        coach = _make_coach([_accept_verdict()] * 3)
        write_tool = _make_write_tool()

        result = asyncio.run(
            run_generation_loop(
                player=player,
                coach=coach,
                targets=[_make_target(count=2)],
                config=_make_config(),
                checkpoint=MagicMock(),
                output_manager=_make_output_manager(),
                write_tool=write_tool,
                dup_detector=dup,
                gate_report=report,
            )
        )

        assert result.accepted == 2
        assert write_tool.invoke.call_count == 2
        assert report.duplicates == 1
        # The duplicate's revise message asks for a different example.
        revise_message = player.ainvoke.call_args_list[2][0][0]["messages"][0][
            "content"
        ]
        assert "Duplicate content" in revise_message


class TestSequentialWithoutGates:
    def test_none_gates_leave_loop_unchanged(self, tmp_path) -> None:
        """Byte-compatibility: no gates => the pre-gate path exactly."""
        player = _make_player([CLEAN_EXAMPLE])
        coach = _make_coach([_accept_verdict()])
        write_tool = _make_write_tool()

        result = asyncio.run(
            run_generation_loop(
                player=player,
                coach=coach,
                targets=[_make_target()],
                config=_make_config(),
                checkpoint=MagicMock(),
                output_manager=_make_output_manager(),
                write_tool=write_tool,
            )
        )

        assert result.accepted == 1
        assert not (tmp_path / GATE_REPORT_FILENAME).exists()


# ---------------------------------------------------------------------------
# Batch window 2 — gate between acceptance validation and accept_pending
# ---------------------------------------------------------------------------


def _state_events(tmp_path: Path) -> list[dict[str, Any]]:
    path = tmp_path / BATCH_STATE_FILENAME
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


class TestBatchWindow2Gate:
    def test_flagged_row_revises_then_passes_next_pass(self, tmp_path) -> None:
        config = _make_config()
        write_tool = _make_write_tool()

        async def _invoke(**kwargs: Any) -> Any:
            quote_gate = _make_quote_gate(tmp_path)
            report = GateReport.load_or_new(tmp_path, resume=kwargs["resume"])
            return await run_batch_generation_loop(
                targets=[_make_target()],
                config=config,
                batch=BatchConfig(enabled=True),
                output_dir=tmp_path,
                output_manager=_make_output_manager(),
                write_tool=write_tool,
                quote_gate=quote_gate,
                gate_report=report,
                **kwargs,
            )

        # Pass 1, window 1: teacher leg produces the fabricated example.
        outcome = asyncio.run(
            _invoke(
                player=_make_player([FABRICATED_EXAMPLE]),
                coach=AsyncMock(),
                resume=False,
            )
        )
        assert outcome.status == "paused" and outcome.window == 1

        # Pass 1, window 2: Coach accepts, but the gate flags the row.
        outcome = asyncio.run(
            _invoke(
                player=AsyncMock(),
                coach=_make_coach([_accept_verdict()]),
                resume=True,
            )
        )
        assert outcome.status == "paused" and outcome.window == 2
        assert write_tool.invoke.call_count == 0
        events = _state_events(tmp_path)
        # No accepting verdict was pinned for the flagged row.
        assert not any(e.get("event") == "accept_pending" for e in events)
        revise = [
            e
            for e in events
            if e.get("event") == "coach_done" and e.get("status") == "revise"
        ]
        assert len(revise) == 1
        assert FABRICATED_SPAN in revise[0]["coach_feedback"]
        # The gate report persisted at the window-2 exit.
        data = json.loads((tmp_path / GATE_REPORT_FILENAME).read_text())
        assert (data["checked"], data["revised"]) == (1, 1)

        # Pass 2, window 1: the revised (corrected) example.
        outcome = asyncio.run(
            _invoke(
                player=_make_player([CORRECTED_EXAMPLE]),
                coach=AsyncMock(),
                resume=True,
            )
        )
        assert outcome.status == "paused" and outcome.window == 1

        # Pass 2, window 2: gate passes, row accepted and written.
        outcome = asyncio.run(
            _invoke(
                player=AsyncMock(),
                coach=_make_coach([_accept_verdict()]),
                resume=True,
            )
        )
        assert outcome.status == "complete"
        assert outcome.result.accepted == 1
        assert write_tool.invoke.call_count == 1
        assert (
            "sticking-place"
            in write_tool.invoke.call_args[0][0]["example_json"]
        )
        data = json.loads((tmp_path / GATE_REPORT_FILENAME).read_text())
        assert (data["checked"], data["passed"], data["revised"]) == (2, 1, 1)

    def test_batch_dedup_records_only_after_write(self, tmp_path) -> None:
        """Two rows with identical content: the second revises; hashes are
        learned from writes (window-2 acceptance path)."""
        config = _make_config()
        write_tool = _make_write_tool()
        dup = DuplicateDetector()

        async def _invoke(**kwargs: Any) -> Any:
            report = GateReport.load_or_new(tmp_path, resume=kwargs["resume"])
            return await run_batch_generation_loop(
                targets=[_make_target(count=2)],
                config=config,
                batch=BatchConfig(enabled=True),
                output_dir=tmp_path,
                output_manager=_make_output_manager(),
                write_tool=write_tool,
                dup_detector=dup,
                gate_report=report,
                **kwargs,
            )

        # Window 1: both teacher legs return identical content.
        outcome = asyncio.run(
            _invoke(
                player=_make_player([CLEAN_EXAMPLE, CLEAN_EXAMPLE]),
                coach=AsyncMock(),
                resume=False,
            )
        )
        assert outcome.status == "paused" and outcome.window == 1

        # Window 2: row 0 accepted + written; row 1 flagged duplicate.
        outcome = asyncio.run(
            _invoke(
                player=AsyncMock(),
                coach=_make_coach([_accept_verdict(), _accept_verdict()]),
                resume=True,
            )
        )
        assert outcome.status == "paused" and outcome.window == 2
        assert write_tool.invoke.call_count == 1
        data = json.loads((tmp_path / GATE_REPORT_FILENAME).read_text())
        assert data["duplicates"] == 1

        # Pass 2: the duplicate row revises to distinct content — accepted.
        outcome = asyncio.run(
            _invoke(
                player=_make_player([OTHER_CLEAN_EXAMPLE]),
                coach=AsyncMock(),
                resume=True,
            )
        )
        assert outcome.status == "paused" and outcome.window == 1
        outcome = asyncio.run(
            _invoke(
                player=AsyncMock(),
                coach=_make_coach([_accept_verdict()]),
                resume=True,
            )
        )
        assert outcome.status == "complete"
        assert outcome.result.accepted == 2
        assert write_tool.invoke.call_count == 2
