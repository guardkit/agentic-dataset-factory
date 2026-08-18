"""Tests for entrypoint.batch_loop — two-window batched-legs generation.

Hermetic (mock agents only — no endpoints, no model inference).  Covers
the Stage-1 batch-mode acceptance surface:

- Target collection parity with the sequential loop (expansion, limit
  interleave, mode/grade round-robin, fingerprint identity).
- Window 1: all Player/teacher legs before ANY Coach leg, per-row
  checkpoint shape, format-gate retries within the window.
- The window boundary: clean stop with an operator instruction naming the
  resume command; no Coach calls before the boundary.
- Window 2: consumption of the checkpointed outputs (no Player calls),
  acceptance path writes, revision rows becoming the next pass.
- Crash/resume mid-window (both windows): at most the in-flight row is
  redone; a truncated final state line is tolerated.
- Fingerprint mismatch (config changed mid-run) is refused.
- Sequential mode regression: batch config defaults leave the sequential
  path engaged and untouched.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from config.coach_verdict import CoachVerdict, Issue
from config.models import AgentConfig, BatchConfig, GenerationConfig, ModelConfig
from domain_config.models import GenerationTarget
from entrypoint.batch_loop import (
    RESUME_COMMAND,
    BatchWindowOutcome,
    collect_generation_targets,
    run_batch_generation_loop,
    select_window1_model_config,
    target_fingerprint,
)
from entrypoint.batch_state import (
    BATCH_STATE_FILENAME,
    BatchStateError,
    BatchStateManager,
)


# ---------------------------------------------------------------------------
# Helpers (mirroring test_generation_loop conventions)
# ---------------------------------------------------------------------------


def _make_target(
    category: str = "Literary analysis",
    type_: str = "reasoning",
    count: int = 1,
    grade_targets: list[int | None] | None = None,
) -> GenerationTarget:
    kwargs: dict[str, Any] = {"category": category, "type": type_, "count": count}
    if grade_targets is not None:
        kwargs["grade_targets"] = grade_targets
    return GenerationTarget(**kwargs)


def _make_accept_verdict() -> CoachVerdict:
    return CoachVerdict(
        decision="accept",
        score=4,
        layer_correct=True,
        type_correct=True,
        criteria_met={"accuracy": True},
        issues=[],
        quality_assessment="Good example",
    )


def _make_reject_verdict(reason: str = "Needs improvement") -> CoachVerdict:
    return CoachVerdict(
        decision="revise",
        score=2,
        layer_correct=True,
        type_correct=True,
        criteria_met={"accuracy": False},
        issues=[
            Issue(
                criterion="accuracy",
                severity="blocking",
                description=reason,
                suggestion="Fix it",
            )
        ],
        quality_assessment=reason,
    )


def _make_generation_config(**overrides: Any) -> GenerationConfig:
    defaults = {
        "max_turns": 3,
        "llm_retry_attempts": 0,
        "llm_retry_backoff": 0.0,
        "llm_timeout": 300,
        "target_timeout": 60,
    }
    defaults.update(overrides)
    return GenerationConfig(**defaults)


def _make_mock_player(responses: list[str] | None = None) -> AsyncMock:
    player = AsyncMock()
    if responses is None:
        player.ainvoke.return_value = {
            "messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]
        }
    else:
        player.ainvoke.side_effect = [
            {"messages": [MagicMock(content=resp)]} for resp in responses
        ]
    return player


def _make_mock_coach(verdicts: list[CoachVerdict]) -> AsyncMock:
    coach = AsyncMock()
    coach.ainvoke.side_effect = [
        {"messages": [MagicMock(content=v.model_dump_json())]} for v in verdicts
    ]
    return coach


def _make_mock_write_tool(
    return_value: str = "Written to output/train.jsonl (example #1)",
) -> MagicMock:
    write_tool = MagicMock()
    write_tool.invoke.return_value = return_value
    return write_tool


def _make_output_manager() -> MagicMock:
    output_mgr = MagicMock()
    output_mgr.rejected_fh = MagicMock()
    return output_mgr


_VALID_EXAMPLE_JSON = json.dumps(
    {
        "messages": [
            {"role": "system", "content": "You are a tutor."},
            {"role": "user", "content": "What is a metaphor?"},
            {"role": "assistant", "content": "A metaphor is a figure of speech."},
        ],
        "metadata": {"layer": "behaviour", "type": "direct"},
    }
)


async def _run(
    tmp_path: Path,
    *,
    player: AsyncMock,
    coach: AsyncMock,
    targets: list[GenerationTarget],
    config: GenerationConfig,
    batch: BatchConfig | None = None,
    write_tool: MagicMock | None = None,
    output_mgr: MagicMock | None = None,
    resume: bool = False,
) -> BatchWindowOutcome:
    return await run_batch_generation_loop(
        player=player,
        coach=coach,
        targets=targets,
        config=config,
        batch=batch or BatchConfig(),
        output_dir=tmp_path,
        output_manager=output_mgr or _make_output_manager(),
        write_tool=write_tool or _make_mock_write_tool(),
        resume=resume,
    )


def _state_events(tmp_path: Path) -> list[dict[str, Any]]:
    path = tmp_path / BATCH_STATE_FILENAME
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Target collection (sequential-parity semantics)
# ---------------------------------------------------------------------------


class TestTargetCollection:
    """The driver collects the run's generation targets deterministically."""

    def test_expands_targets_by_count(self) -> None:
        targets = [_make_target(category="A", count=3), _make_target(category="B", count=2)]
        rows = collect_generation_targets(targets, _make_generation_config())
        assert len(rows) == 5
        assert [r.target.category for r in rows] == ["A", "A", "A", "B", "B"]
        assert [r.index for r in rows] == [0, 1, 2, 3, 4]

    def test_limit_interleaves_categories(self) -> None:
        """A small cap spans all categories (sequential-loop parity)."""
        targets = [_make_target(category="A", count=3), _make_target(category="B", count=3)]
        config = _make_generation_config(limit=2)
        rows = collect_generation_targets(targets, config)
        assert [r.target.category for r in rows] == ["A", "B"]

    def test_modes_round_robin_by_absolute_index(self) -> None:
        targets = [_make_target(count=4)]
        config = _make_generation_config(modes=["idea", "scope"])
        rows = collect_generation_targets(targets, config)
        assert [r.mode for r in rows] == ["idea", "scope", "idea", "scope"]

    def test_grades_round_robin_by_absolute_index(self) -> None:
        targets = [_make_target(count=3, grade_targets=[4, 9])]
        rows = collect_generation_targets(targets, _make_generation_config())
        assert [r.grade_target for r in rows] == [4, 9, 4]

    def test_fingerprint_is_deterministic_and_config_sensitive(self) -> None:
        targets = [_make_target(count=2)]
        config_a = _make_generation_config(modes=["idea"])
        config_b = _make_generation_config(modes=["scope"])
        fp_a1 = target_fingerprint(collect_generation_targets(targets, config_a))
        fp_a2 = target_fingerprint(collect_generation_targets(targets, config_a))
        fp_b = target_fingerprint(collect_generation_targets(targets, config_b))
        assert fp_a1 == fp_a2
        assert fp_a1 != fp_b


# ---------------------------------------------------------------------------
# Teacher seam (ModelConfig — no model names in code)
# ---------------------------------------------------------------------------


class TestTeacherSeam:
    """Window-1 seat resolves through the same ModelConfig seam."""

    def _base_config(self, batch: dict[str, Any] | None = None) -> AgentConfig:
        data: dict[str, Any] = {
            "domain": "test-domain",
            "player": {
                "provider": "local",
                "model": "player-model",
                "endpoint": "http://localhost:9000/v1",
            },
            "coach": {
                "provider": "local",
                "model": "coach-model",
                "endpoint": "http://localhost:9000/v1",
            },
        }
        if batch is not None:
            data["batch"] = batch
        return AgentConfig.model_validate(data)

    def test_teacher_unset_falls_back_to_player(self) -> None:
        config = self._base_config(batch={"enabled": True})
        assert select_window1_model_config(config) is config.player

    def test_teacher_set_takes_the_window1_seat(self) -> None:
        config = self._base_config(
            batch={
                "enabled": True,
                "teacher": {
                    "provider": "local",
                    "model": "teacher-model",
                    "endpoint": "http://nodea:8888/v1",
                },
            }
        )
        selected = select_window1_model_config(config)
        assert isinstance(selected, ModelConfig)
        assert selected.model == "teacher-model"
        assert selected.endpoint == "http://nodea:8888/v1"


# ---------------------------------------------------------------------------
# Window 1 — leg ordering + checkpoint shape
# ---------------------------------------------------------------------------


class TestWindow1:
    """All Player/teacher legs run and checkpoint before any Coach leg."""

    @pytest.mark.asyncio
    async def test_all_player_legs_no_coach_then_pause(self, tmp_path: Path) -> None:
        targets = [_make_target(category=f"Cat-{i}") for i in range(3)]
        player = _make_mock_player()
        coach = AsyncMock()

        outcome = await _run(
            tmp_path,
            player=player,
            coach=coach,
            targets=targets,
            config=_make_generation_config(),
        )

        assert outcome.status == "paused"
        assert outcome.window == 1
        assert outcome.pass_number == 1
        assert player.ainvoke.await_count == 3
        coach.ainvoke.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_checkpoint_shape_per_row(self, tmp_path: Path) -> None:
        """Each row's Player output is checkpointed as its own event."""
        targets = [_make_target(category=f"Cat-{i}") for i in range(2)]
        player = _make_mock_player()

        await _run(
            tmp_path,
            player=player,
            coach=AsyncMock(),
            targets=targets,
            config=_make_generation_config(),
        )

        events = _state_events(tmp_path)
        assert events[0]["event"] == "run_started"
        assert events[0]["total_rows"] == 2
        assert events[0]["fingerprint"]
        player_events = [e for e in events if e["event"] == "player_done"]
        assert [e["index"] for e in player_events] == [0, 1]
        for e in player_events:
            assert e["status"] == "ok"
            assert e["pass"] == 1
            assert e["player_content"] == _VALID_EXAMPLE_JSON
        assert events[-1] == {"event": "window1_complete", "pass": 1}

    @pytest.mark.asyncio
    async def test_format_gate_retries_within_window(self, tmp_path: Path) -> None:
        """A format-gate failure re-prompts the live Player immediately."""
        targets = [_make_target()]
        player = _make_mock_player(["not json at all", _VALID_EXAMPLE_JSON])

        outcome = await _run(
            tmp_path,
            player=player,
            coach=AsyncMock(),
            targets=targets,
            config=_make_generation_config(),
        )

        assert outcome.status == "paused"
        assert player.ainvoke.await_count == 2
        second_msg = player.ainvoke.await_args_list[1][0][0]["messages"][0]["content"]
        assert "FORMAT ERROR" in second_msg
        events = _state_events(tmp_path)
        player_events = [e for e in events if e["event"] == "player_done"]
        assert player_events[0]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_format_gate_exhaustion_rejects_row(self, tmp_path: Path) -> None:
        targets = [_make_target()]
        player = _make_mock_player(["junk"] * 10)
        output_mgr = _make_output_manager()

        await _run(
            tmp_path,
            player=player,
            coach=AsyncMock(),
            targets=targets,
            config=_make_generation_config(max_format_retries=1),
            output_mgr=output_mgr,
        )

        events = _state_events(tmp_path)
        player_events = [e for e in events if e["event"] == "player_done"]
        assert player_events[0]["status"] == "failed"
        assert player_events[0]["reason"] == "format_retries_exhausted"
        written = output_mgr.rejected_fh.write.call_args[0][0]
        assert json.loads(written)["reason"] == "format_retries_exhausted"

    @pytest.mark.asyncio
    async def test_output_validator_hook_gates_window1(self, tmp_path: Path) -> None:
        """2026-08-18: the per-domain output validator runs in the batch
        Player leg too — a failing row re-prompts with the validator's error
        text; a passing row is accepted."""
        import entrypoint.generation_loop as gl

        calls: list[str] = []

        def fake_validator(content: str, metadata: dict[str, Any]) -> tuple[bool, str]:
            calls.append(content)
            if "metaphor" in content:
                return False, "FeatureSpecInput.description must contain at least 2 sentences"
            return True, "ok"

        gl._OUTPUT_VALIDATOR_CACHE["fake:validator"] = fake_validator
        try:
            good = json.loads(_VALID_EXAMPLE_JSON)
            good["messages"][-1]["content"] = "A simile compares. It uses like or as."
            targets = [_make_target()]
            player = _make_mock_player([_VALID_EXAMPLE_JSON, json.dumps(good)])
            outcome = await _run(
                tmp_path,
                player=player,
                coach=AsyncMock(),
                targets=targets,
                config=_make_generation_config(output_validator="fake:validator"),
            )
        finally:
            gl._OUTPUT_VALIDATOR_CACHE.pop("fake:validator", None)

        assert outcome.status == "paused"
        assert player.ainvoke.await_count == 2
        second_msg = player.ainvoke.await_args_list[1][0][0]["messages"][0]["content"]
        assert "at least 2 sentences" in second_msg
        events = _state_events(tmp_path)
        player_events = [e for e in events if e["event"] == "player_done"]
        assert player_events[0]["status"] == "ok"
        assert len(calls) == 2


# ---------------------------------------------------------------------------
# The window boundary — clean stop with operator instruction
# ---------------------------------------------------------------------------


class TestWindowBoundary:
    """The run stops at the boundary and instructs the operator."""

    @pytest.mark.asyncio
    async def test_window1_boundary_instruction(self, tmp_path: Path) -> None:
        outcome = await _run(
            tmp_path,
            player=_make_mock_player(),
            coach=AsyncMock(),
            targets=[_make_target()],
            config=_make_generation_config(),
        )

        text = outcome.operator_instruction
        assert "BATCH WINDOW BOUNDARY" in text
        assert "Window 1" in text
        assert "OPERATOR" in text
        assert RESUME_COMMAND in text

    @pytest.mark.asyncio
    async def test_operator_note_is_appended(self, tmp_path: Path) -> None:
        outcome = await _run(
            tmp_path,
            player=_make_mock_player(),
            coach=AsyncMock(),
            targets=[_make_target()],
            config=_make_generation_config(),
            batch=BatchConfig(operator_note="follow RUNBOOK-teacher.md phases 3-4"),
        )

        assert "follow RUNBOOK-teacher.md phases 3-4" in outcome.operator_instruction


# ---------------------------------------------------------------------------
# Window 2 — consumption of checkpointed outputs + ordering
# ---------------------------------------------------------------------------


class TestWindow2:
    """Coach legs consume the checkpointed outputs; the Player stays idle."""

    @pytest.mark.asyncio
    async def test_resume_runs_coach_over_checkpointed_content(
        self, tmp_path: Path
    ) -> None:
        targets = [_make_target(category=f"Cat-{i}") for i in range(3)]
        config = _make_generation_config()
        write_tool = _make_mock_write_tool()

        await _run(
            tmp_path,
            player=_make_mock_player(),
            coach=AsyncMock(),
            targets=targets,
            config=config,
        )

        # Window 2: fresh mocks prove the Player is never touched.
        player2 = AsyncMock()
        coach = _make_mock_coach([_make_accept_verdict()] * 3)
        outcome = await _run(
            tmp_path,
            player=player2,
            coach=coach,
            targets=targets,
            config=config,
            write_tool=write_tool,
            resume=True,
        )

        player2.ainvoke.assert_not_awaited()
        assert coach.ainvoke.await_count == 3
        for call in coach.ainvoke.await_args_list:
            assert call[0][0]["messages"][0]["content"] == _VALID_EXAMPLE_JSON
        assert write_tool.invoke.call_count == 3
        assert outcome.status == "complete"
        assert outcome.result is not None
        assert outcome.result.accepted == 3
        assert outcome.result.rejected == 0
        events = _state_events(tmp_path)
        coach_events = [e for e in events if e["event"] == "coach_done"]
        assert [e["index"] for e in coach_events] == [0, 1, 2]
        assert events[-1] == {"event": "run_complete"}

    @pytest.mark.asyncio
    async def test_revision_routes_to_next_pass_window1(self, tmp_path: Path) -> None:
        """A revise verdict pauses at the boundary; pass 2 window 1 redoes
        ONLY the revise row, with the Coach feedback in the prompt."""
        targets = [_make_target(category=f"Cat-{i}") for i in range(2)]
        config = _make_generation_config(max_turns=3)

        await _run(
            tmp_path,
            player=_make_mock_player(),
            coach=AsyncMock(),
            targets=targets,
            config=config,
        )

        coach = _make_mock_coach(
            [_make_reject_verdict("Too shallow"), _make_accept_verdict()]
        )
        outcome = await _run(
            tmp_path,
            player=AsyncMock(),
            coach=coach,
            targets=targets,
            config=config,
            resume=True,
        )
        assert outcome.status == "paused"
        assert outcome.window == 2
        assert "pass 2" in outcome.operator_instruction

        # Pass 2 window 1: only the revise row, with feedback injected.
        player3 = _make_mock_player()
        outcome = await _run(
            tmp_path,
            player=player3,
            coach=AsyncMock(),
            targets=targets,
            config=config,
            resume=True,
        )
        assert outcome.status == "paused"
        assert outcome.window == 1
        assert outcome.pass_number == 2
        assert player3.ainvoke.await_count == 1
        msg = player3.ainvoke.await_args_list[0][0][0]["messages"][0]["content"]
        assert "Coach Feedback" in msg
        assert "Too shallow" in msg

        # Pass 2 window 2 accepts the revision — run completes at 2/2.
        coach2 = _make_mock_coach([_make_accept_verdict()])
        outcome = await _run(
            tmp_path,
            player=AsyncMock(),
            coach=coach2,
            targets=targets,
            config=config,
            resume=True,
        )
        assert outcome.status == "complete"
        assert outcome.result is not None
        assert outcome.result.accepted == 2
        assert outcome.result.rejected == 0

    @pytest.mark.asyncio
    async def test_passes_exhausted_rejects_pending_rows(self, tmp_path: Path) -> None:
        targets = [_make_target()]
        config = _make_generation_config(max_turns=1)
        output_mgr = _make_output_manager()

        await _run(
            tmp_path,
            player=_make_mock_player(),
            coach=AsyncMock(),
            targets=targets,
            config=config,
        )
        outcome = await _run(
            tmp_path,
            player=AsyncMock(),
            coach=_make_mock_coach([_make_reject_verdict()]),
            targets=targets,
            config=config,
            output_mgr=output_mgr,
            resume=True,
        )

        assert outcome.status == "complete"
        assert outcome.result is not None
        assert outcome.result.accepted == 0
        assert outcome.result.rejected == 1
        written = output_mgr.rejected_fh.write.call_args[0][0]
        assert json.loads(written)["reason"] == "max_turns_exhausted"

    @pytest.mark.asyncio
    async def test_batch_max_passes_overrides_max_turns(self, tmp_path: Path) -> None:
        """batch.max_passes caps revision passes independently of max_turns."""
        targets = [_make_target()]
        config = _make_generation_config(max_turns=3)
        batch = BatchConfig(max_passes=1)

        await _run(
            tmp_path,
            player=_make_mock_player(),
            coach=AsyncMock(),
            targets=targets,
            config=config,
            batch=batch,
        )
        outcome = await _run(
            tmp_path,
            player=AsyncMock(),
            coach=_make_mock_coach([_make_reject_verdict()]),
            targets=targets,
            config=config,
            batch=batch,
            resume=True,
        )

        assert outcome.status == "complete"
        assert outcome.result is not None
        assert outcome.result.rejected == 1

    @pytest.mark.asyncio
    async def test_write_failure_routes_to_revision(self, tmp_path: Path) -> None:
        targets = [_make_target()]
        config = _make_generation_config(max_turns=3)
        write_tool = _make_mock_write_tool(return_value="Error: schema mismatch")

        await _run(
            tmp_path,
            player=_make_mock_player(),
            coach=AsyncMock(),
            targets=targets,
            config=config,
        )
        outcome = await _run(
            tmp_path,
            player=AsyncMock(),
            coach=_make_mock_coach([_make_accept_verdict()]),
            targets=targets,
            config=config,
            write_tool=write_tool,
            resume=True,
        )

        assert outcome.status == "paused"  # boundary into pass 2
        events = _state_events(tmp_path)
        coach_events = [e for e in events if e["event"] == "coach_done"]
        assert coach_events[0]["status"] == "revise"
        assert "Write validation failed" in coach_events[0]["coach_feedback"]


# ---------------------------------------------------------------------------
# Crash / resume mid-window (both windows)
# ---------------------------------------------------------------------------


class TestCrashResume:
    """A crash loses at most the in-flight row; resume redoes only it."""

    @pytest.mark.asyncio
    async def test_crash_mid_window1_resumes_remaining_rows(
        self, tmp_path: Path
    ) -> None:
        targets = [_make_target(category=f"Cat-{i}") for i in range(3)]
        config = _make_generation_config()
        rows = collect_generation_targets(targets, config)

        # Simulate a crash after row 0's leg landed: hand-write the log.
        mgr = BatchStateManager(tmp_path)
        mgr.record(
            "run_started", total_rows=3, fingerprint=target_fingerprint(rows)
        )
        mgr.record(
            "player_done",
            index=0,
            **{"pass": 1},
            status="ok",
            player_content=_VALID_EXAMPLE_JSON,
        )

        player = _make_mock_player()
        outcome = await _run(
            tmp_path,
            player=player,
            coach=AsyncMock(),
            targets=targets,
            config=config,
            resume=True,
        )

        assert outcome.status == "paused"
        assert player.ainvoke.await_count == 2  # rows 1 and 2 only
        events = _state_events(tmp_path)
        player_events = [e for e in events if e["event"] == "player_done"]
        assert [e["index"] for e in player_events] == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_crash_mid_window2_resumes_remaining_rows(
        self, tmp_path: Path
    ) -> None:
        targets = [_make_target(category=f"Cat-{i}") for i in range(3)]
        config = _make_generation_config()

        await _run(
            tmp_path,
            player=_make_mock_player(),
            coach=AsyncMock(),
            targets=targets,
            config=config,
        )
        # Simulate a crash after row 0's Coach leg landed.
        mgr = BatchStateManager(tmp_path)
        mgr.record("coach_done", index=0, **{"pass": 1}, status="accepted")

        coach = _make_mock_coach([_make_accept_verdict()] * 2)
        outcome = await _run(
            tmp_path,
            player=AsyncMock(),
            coach=coach,
            targets=targets,
            config=config,
            resume=True,
        )

        assert coach.ainvoke.await_count == 2  # rows 1 and 2 only
        assert outcome.status == "complete"
        assert outcome.result is not None
        assert outcome.result.accepted == 3

    @pytest.mark.asyncio
    async def test_replayed_revise_verdict_survives_crash_resume(
        self, tmp_path: Path
    ) -> None:
        """BLOCKER regression (drive receipt 2026-08-14): a revise verdict
        recorded BEFORE a crash must pause the run into the next pass on
        resume — not be terminally rejected as ``max_turns_exhausted`` at
        pass 1 because the invocation-local revise counter never saw it."""
        targets = [_make_target(category=f"Cat-{i}") for i in range(3)]
        config = _make_generation_config(max_turns=3)
        output_mgr = _make_output_manager()

        await _run(
            tmp_path,
            player=_make_mock_player(),
            coach=AsyncMock(),
            targets=targets,
            config=config,
        )
        # Crash simulation: row 0's revise verdict landed (fsynced), then
        # SIGKILL before rows 1-2 were coached.
        mgr = BatchStateManager(tmp_path)
        mgr.record(
            "coach_done",
            index=0,
            **{"pass": 1},
            status="revise",
            coach_feedback="Too shallow",
        )

        coach = _make_mock_coach([_make_accept_verdict()] * 2)
        outcome = await _run(
            tmp_path,
            player=AsyncMock(),
            coach=coach,
            targets=targets,
            config=config,
            output_mgr=output_mgr,
            resume=True,
        )

        assert coach.ainvoke.await_count == 2  # rows 1 and 2 only
        assert outcome.status == "paused"  # into pass 2 — NOT complete
        assert outcome.window == 2
        assert "pass 2" in outcome.operator_instruction
        assert "1 row(s) pending revision" in outcome.operator_instruction
        events = _state_events(tmp_path)
        assert not [e for e in events if e["event"] == "row_finalised"]
        assert not [e for e in events if e["event"] == "run_complete"]
        output_mgr.rejected_fh.write.assert_not_called()

        # Pass 2 window 1 redoes ONLY row 0, with the pre-crash feedback.
        player = _make_mock_player()
        outcome = await _run(
            tmp_path,
            player=player,
            coach=AsyncMock(),
            targets=targets,
            config=config,
            resume=True,
        )
        assert outcome.status == "paused"
        assert outcome.window == 1
        assert outcome.pass_number == 2
        assert player.ainvoke.await_count == 1
        msg = player.ainvoke.await_args_list[0][0][0]["messages"][0]["content"]
        assert "Too shallow" in msg

    @pytest.mark.asyncio
    async def test_crash_after_last_coach_leg_still_pauses_into_next_pass(
        self, tmp_path: Path
    ) -> None:
        """Crash after the final ``coach_done`` but before
        ``window2_complete``: resume has NO rows awaiting the Coach, yet
        must still pause into the next pass for the replayed revise row."""
        targets = [_make_target(category=f"Cat-{i}") for i in range(2)]
        config = _make_generation_config(max_turns=3)

        await _run(
            tmp_path,
            player=_make_mock_player(),
            coach=AsyncMock(),
            targets=targets,
            config=config,
        )
        mgr = BatchStateManager(tmp_path)
        mgr.record("coach_done", index=0, **{"pass": 1}, status="accepted")
        mgr.record(
            "coach_done",
            index=1,
            **{"pass": 1},
            status="revise",
            coach_feedback="Weak evidence",
        )

        coach = AsyncMock()
        outcome = await _run(
            tmp_path,
            player=AsyncMock(),
            coach=coach,
            targets=targets,
            config=config,
            resume=True,
        )

        coach.ainvoke.assert_not_awaited()  # every verdict already landed
        assert outcome.status == "paused"
        assert outcome.window == 2
        assert "1 row(s) accepted" in outcome.operator_instruction
        assert "1 row(s) pending revision" in outcome.operator_instruction

    @pytest.mark.asyncio
    async def test_replayed_revise_still_finalised_when_passes_exhausted(
        self, tmp_path: Path
    ) -> None:
        """Out of passes, a replayed revise row IS terminally rejected —
        the crash-resume fix must not unbound the pass cap."""
        targets = [_make_target()]
        config = _make_generation_config(max_turns=1)
        output_mgr = _make_output_manager()

        await _run(
            tmp_path,
            player=_make_mock_player(),
            coach=AsyncMock(),
            targets=targets,
            config=config,
        )
        mgr = BatchStateManager(tmp_path)
        mgr.record(
            "coach_done",
            index=0,
            **{"pass": 1},
            status="revise",
            coach_feedback="Too shallow",
        )

        outcome = await _run(
            tmp_path,
            player=AsyncMock(),
            coach=AsyncMock(),
            targets=targets,
            config=config,
            output_mgr=output_mgr,
            resume=True,
        )

        assert outcome.status == "complete"
        assert outcome.result is not None
        assert outcome.result.accepted == 0
        assert outcome.result.rejected == 1
        written = output_mgr.rejected_fh.write.call_args[0][0]
        assert json.loads(written)["reason"] == "max_turns_exhausted"

    @pytest.mark.asyncio
    async def test_crash_in_write_gap_redoes_only_the_write(
        self, tmp_path: Path
    ) -> None:
        """A crash between ``accept_pending`` and ``coach_done`` resumes
        as a write-only redo: the pinned verdict is honoured, the Coach is
        never re-consulted."""
        targets = [_make_target()]
        config = _make_generation_config()

        await _run(
            tmp_path,
            player=_make_mock_player(),
            coach=AsyncMock(),
            targets=targets,
            config=config,
        )
        mgr = BatchStateManager(tmp_path)
        mgr.record("accept_pending", index=0, **{"pass": 1})

        coach = AsyncMock()
        write_tool = _make_mock_write_tool()
        outcome = await _run(
            tmp_path,
            player=AsyncMock(),
            coach=coach,
            targets=targets,
            config=config,
            write_tool=write_tool,
            resume=True,
        )

        coach.ainvoke.assert_not_awaited()
        assert write_tool.invoke.call_count == 1
        assert outcome.status == "complete"
        assert outcome.result is not None
        assert outcome.result.accepted == 1
        events = _state_events(tmp_path)
        coach_events = [e for e in events if e["event"] == "coach_done"]
        assert coach_events == [
            {"event": "coach_done", "index": 0, "pass": 1, "status": "accepted"}
        ]

    @pytest.mark.asyncio
    async def test_accepting_verdict_is_pinned_before_the_write(
        self, tmp_path: Path
    ) -> None:
        """``accept_pending`` reaches the fsynced log BEFORE the
        orchestrator write runs (the crash-in-the-gap contract)."""
        targets = [_make_target()]
        config = _make_generation_config()

        await _run(
            tmp_path,
            player=_make_mock_player(),
            coach=AsyncMock(),
            targets=targets,
            config=config,
        )

        events_at_write: list[list[str]] = []
        write_tool = MagicMock()

        def _capture(args: dict[str, Any]) -> str:
            events_at_write.append([e["event"] for e in _state_events(tmp_path)])
            return "Written to output/train.jsonl (example #1)"

        write_tool.invoke.side_effect = _capture

        outcome = await _run(
            tmp_path,
            player=AsyncMock(),
            coach=_make_mock_coach([_make_accept_verdict()]),
            targets=targets,
            config=config,
            write_tool=write_tool,
            resume=True,
        )

        assert outcome.status == "complete"
        assert events_at_write[0][-1] == "accept_pending"
        accept_events = [
            e["event"]
            for e in _state_events(tmp_path)
            if e["event"] in ("accept_pending", "coach_done")
        ]
        assert accept_events == ["accept_pending", "coach_done"]

    @pytest.mark.asyncio
    async def test_truncated_final_line_is_tolerated(self, tmp_path: Path) -> None:
        """A crash mid-write leaves a truncated line; the row is redone."""
        targets = [_make_target(category=f"Cat-{i}") for i in range(2)]
        config = _make_generation_config()
        rows = collect_generation_targets(targets, config)

        mgr = BatchStateManager(tmp_path)
        mgr.record(
            "run_started", total_rows=2, fingerprint=target_fingerprint(rows)
        )
        mgr.record(
            "player_done",
            index=0,
            **{"pass": 1},
            status="ok",
            player_content=_VALID_EXAMPLE_JSON,
        )
        with open(tmp_path / BATCH_STATE_FILENAME, "a", encoding="utf-8") as fh:
            fh.write('{"event": "player_done", "index": 1, "sta')  # crash mid-write

        player = _make_mock_player()
        outcome = await _run(
            tmp_path,
            player=player,
            coach=AsyncMock(),
            targets=targets,
            config=config,
            resume=True,
        )

        assert outcome.status == "paused"
        assert player.ainvoke.await_count == 1  # only row 1 redone

    @pytest.mark.asyncio
    async def test_fingerprint_mismatch_is_refused(self, tmp_path: Path) -> None:
        """A config change mid-run must not silently mispair rows."""
        targets = [_make_target(count=2)]
        config = _make_generation_config()

        mgr = BatchStateManager(tmp_path)
        mgr.record("run_started", total_rows=2, fingerprint="deadbeefdeadbeef")

        with pytest.raises(BatchStateError, match="fingerprint"):
            await _run(
                tmp_path,
                player=_make_mock_player(),
                coach=AsyncMock(),
                targets=targets,
                config=config,
                resume=True,
            )

    @pytest.mark.asyncio
    async def test_max_passes_change_is_refused_on_resume(
        self, tmp_path: Path
    ) -> None:
        """A mid-run max_passes/max_turns change is caught on resume,
        like the target fingerprint."""
        targets = [_make_target()]
        config = _make_generation_config(max_turns=3)

        await _run(
            tmp_path,
            player=_make_mock_player(),
            coach=AsyncMock(),
            targets=targets,
            config=config,
            batch=BatchConfig(max_passes=2),
        )

        with pytest.raises(BatchStateError, match="max_passes"):
            await _run(
                tmp_path,
                player=AsyncMock(),
                coach=AsyncMock(),
                targets=targets,
                config=config,
                batch=BatchConfig(max_passes=3),
                resume=True,
            )

    @pytest.mark.asyncio
    async def test_resume_without_state_starts_fresh(self, tmp_path: Path) -> None:
        """--resume with no state log mirrors sequential's warning path."""
        player = _make_mock_player()
        outcome = await _run(
            tmp_path,
            player=player,
            coach=AsyncMock(),
            targets=[_make_target()],
            config=_make_generation_config(),
            resume=True,
        )
        assert outcome.status == "paused"
        assert outcome.window == 1
        assert player.ainvoke.await_count == 1


# ---------------------------------------------------------------------------
# Window-1 failure handling
# ---------------------------------------------------------------------------


class TestWindow1Failures:
    """Row-level failures reject the row and continue the window."""

    @pytest.mark.asyncio
    async def test_llm_failure_rejects_row_and_continues(self, tmp_path: Path) -> None:
        targets = [_make_target(category=f"Cat-{i}") for i in range(2)]
        player = AsyncMock()
        player.ainvoke.side_effect = [
            RuntimeError("connection refused"),
            {"messages": [MagicMock(content=_VALID_EXAMPLE_JSON)]},
        ]
        output_mgr = _make_output_manager()

        outcome = await _run(
            tmp_path,
            player=player,
            coach=AsyncMock(),
            targets=targets,
            config=_make_generation_config(llm_retry_attempts=0),
            output_mgr=output_mgr,
        )

        assert outcome.status == "paused"
        events = _state_events(tmp_path)
        player_events = [e for e in events if e["event"] == "player_done"]
        assert player_events[0]["status"] == "failed"
        assert "llm_failure" in player_events[0]["reason"]
        assert player_events[1]["status"] == "ok"
        written = output_mgr.rejected_fh.write.call_args[0][0]
        assert "llm_failure" in json.loads(written)["reason"]


# ---------------------------------------------------------------------------
# Layer-aware Coach routing (parity with sequential TASK-CR-003)
# ---------------------------------------------------------------------------


class TestLayerRouting:
    """A layer-keyed Coach dict routes each row to its layer's Coach."""

    @pytest.mark.asyncio
    async def test_coach_dict_routes_by_target_layer(self, tmp_path: Path) -> None:
        targets = [
            GenerationTarget(
                category="A", type="reasoning", layer="behaviour", count=1
            ),
            GenerationTarget(
                category="B", type="reasoning", layer="knowledge", count=1
            ),
        ]
        config = _make_generation_config()

        await _run(
            tmp_path,
            player=_make_mock_player(),
            coach=AsyncMock(),
            targets=targets,
            config=config,
        )

        coach_behaviour = _make_mock_coach([_make_accept_verdict()])
        coach_knowledge = _make_mock_coach([_make_accept_verdict()])
        outcome = await run_batch_generation_loop(
            player=AsyncMock(),
            coach={"behaviour": coach_behaviour, "knowledge": coach_knowledge},
            targets=targets,
            config=config,
            batch=BatchConfig(),
            output_dir=tmp_path,
            output_manager=_make_output_manager(),
            write_tool=_make_mock_write_tool(),
            resume=True,
        )

        assert outcome.status == "complete"
        assert coach_behaviour.ainvoke.await_count == 1
        assert coach_knowledge.ainvoke.await_count == 1
