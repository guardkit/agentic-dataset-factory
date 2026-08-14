"""Per-row batch state checkpointing — append-only JSONL event log.

Supports the two-window batch mode (``entrypoint/batch_loop.py``): every
completed leg (Player/teacher output, Coach verdict, window boundary) is
recorded as one JSON line, flushed and fsynced immediately, so a crash at
any point loses at most the single in-flight row.  Resume replays the log
to reconstruct exactly where the run stopped — which pass, which window,
and which rows still need work.

The log lives at ``output/.batch_state.jsonl`` alongside the sequential
mode's ``.checkpoint`` file, and is cleared by the same fresh-start
directory preparation (ADR-ARCH-008).  Sequential mode never reads or
writes it.

Event vocabulary (one JSON object per line):

- ``run_started``    — total_rows, fingerprint (target-collection identity),
  max_passes (verified on resume, like the fingerprint)
- ``player_done``    — index, pass, status ``ok`` (+player_content) or
  ``failed`` (+reason)
- ``window1_complete`` — pass
- ``accept_pending`` — index, pass (accepting verdict pinned to the log;
  the orchestrator write is in flight — a crash before the row's
  ``coach_done`` resumes as a redo of ONLY the write, never a Coach
  re-evaluation)
- ``coach_done``     — index, pass, status ``accepted`` / ``revise``
  (+coach_feedback) / ``rejected`` (+reason)
- ``window2_complete`` — pass, next ``pass`` or ``complete``
- ``row_finalised``  — index, reason (revise rows out of passes)
- ``run_complete``   — terminal marker

References:
    - ADR-ARCH-006 (dated note 2026-08-14: batched legs / two-window mode)
    - ADR-ARCH-010 (overnight run resilience — the checkpoint lesson)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

BATCH_STATE_FILENAME = ".batch_state.jsonl"

# Row lifecycle states
ROW_PENDING_PLAYER = "pending_player"
ROW_AWAITING_COACH = "awaiting_coach"
ROW_ACCEPT_PENDING = "accept_pending"
ROW_REVISE = "revise"
ROW_ACCEPTED = "accepted"
ROW_REJECTED = "rejected"


class BatchStateError(Exception):
    """Raised when the batch state log is corrupt or inconsistent."""


@dataclass
class RowState:
    """Replayed state of a single generation row.

    Attributes:
        status: One of the ``ROW_*`` lifecycle constants.
        player_content: Checkpointed Player/teacher output (window 1).
        coach_feedback: Latest Coach feedback for a revise row.
        reason: Terminal rejection reason, when status is ``rejected``.
    """

    status: str = ROW_PENDING_PLAYER
    player_content: str | None = None
    coach_feedback: str | None = None
    reason: str | None = None


@dataclass
class BatchRunState:
    """Full replayed state of a batch run.

    Attributes:
        started: True once a ``run_started`` event has been recorded.
        total_rows: Number of collected generation rows.
        fingerprint: Target-collection fingerprint recorded at run start.
        max_passes: Pass cap recorded at run start (verified on resume so
            a mid-run ``max_turns``/``batch.max_passes`` config change is
            caught, like the fingerprint); None for logs predating the
            field.
        pass_number: Current pass (1-based; one pass = one Player-Coach
            cycle per pending row, split across two windows).
        window: Current window — 1 (Player/teacher legs) or 2 (Coach legs).
        complete: True once ``run_complete`` has been recorded.
        rows: Per-row state keyed by absolute row index.
        player_legs: Count of completed Player legs across the run.
        coach_evals: Count of completed Coach evaluations across the run.
    """

    started: bool = False
    total_rows: int = 0
    fingerprint: str = ""
    max_passes: int | None = None
    pass_number: int = 1
    window: int = 1
    complete: bool = False
    rows: dict[int, RowState] = field(default_factory=dict)
    player_legs: int = 0
    coach_evals: int = 0

    def pending_player_indices(self) -> list[int]:
        """Row indices still needing a Player/teacher leg this pass."""
        return sorted(
            i for i, r in self.rows.items() if r.status == ROW_PENDING_PLAYER
        )

    def awaiting_coach_indices(self) -> list[int]:
        """Row indices with a checkpointed Player output awaiting the Coach."""
        return sorted(
            i for i, r in self.rows.items() if r.status == ROW_AWAITING_COACH
        )

    def accept_pending_indices(self) -> list[int]:
        """Row indices whose accepting verdict is pinned but whose write
        was interrupted (crash between ``accept_pending`` and
        ``coach_done``) — resume redoes only the write."""
        return sorted(
            i for i, r in self.rows.items() if r.status == ROW_ACCEPT_PENDING
        )

    def revise_indices(self) -> list[int]:
        """Row indices the Coach sent back for revision this pass."""
        return sorted(i for i, r in self.rows.items() if r.status == ROW_REVISE)

    @property
    def accepted_count(self) -> int:
        """Number of rows accepted so far."""
        return sum(1 for r in self.rows.values() if r.status == ROW_ACCEPTED)

    @property
    def rejected_count(self) -> int:
        """Number of rows terminally rejected so far."""
        return sum(1 for r in self.rows.values() if r.status == ROW_REJECTED)


class BatchStateManager:
    """Append-only writer/replayer for the batch state event log.

    Every ``record()`` call appends one JSON line and fsyncs it, so the
    on-disk log is always at most one truncated line behind reality (the
    progressive-write lesson: a crash loses only the in-flight row).
    """

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = Path(output_dir)
        self._path = self._output_dir / BATCH_STATE_FILENAME

    @property
    def path(self) -> Path:
        """Path of the state log file."""
        return self._path

    def exists(self) -> bool:
        """True when a state log file is present in the output directory."""
        return self._path.exists()

    def record(self, event: str, **fields: object) -> None:
        """Append one event line and flush+fsync it to disk.

        Args:
            event: Event name (see module docstring vocabulary).
            **fields: Event payload fields, JSON-serialisable.
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"event": event, **fields})
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def replay(self) -> BatchRunState:
        """Reconstruct the run state by replaying the event log.

        A malformed FINAL line is tolerated (crash mid-write of the
        in-flight row) and dropped with a warning; a malformed line
        anywhere else is corruption and raises.

        Returns:
            The reconstructed :class:`BatchRunState`.

        Raises:
            BatchStateError: If the log is missing, empty, or corrupt.
        """
        if not self._path.exists():
            raise BatchStateError(f"No batch state log at {self._path}")

        lines = self._path.read_text(encoding="utf-8").splitlines()
        state = BatchRunState()
        events_applied = 0

        for lineno, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                if lineno == len(lines) - 1:
                    logger.warning(
                        "Batch state log ends in a truncated line "
                        "(crash mid-write); dropping it — the in-flight "
                        "row will be redone on resume."
                    )
                    break
                raise BatchStateError(
                    f"Corrupt batch state log at {self._path}, line {lineno + 1}"
                ) from None
            self._apply(state, ev, lineno)
            events_applied += 1

        if not state.started:
            raise BatchStateError(
                f"Batch state log at {self._path} has no run_started event"
            )
        logger.info(
            "batch_state_replayed: events=%d, pass=%d, window=%d, "
            "accepted=%d, rejected=%d, pending_player=%d, awaiting_coach=%d",
            events_applied,
            state.pass_number,
            state.window,
            state.accepted_count,
            state.rejected_count,
            len(state.pending_player_indices()),
            len(state.awaiting_coach_indices()),
        )
        return state

    @staticmethod
    def _apply(state: BatchRunState, ev: dict, lineno: int) -> None:
        """Apply one replayed event to *state*."""
        name = ev.get("event")

        if name == "run_started":
            state.started = True
            state.total_rows = int(ev["total_rows"])
            state.fingerprint = str(ev.get("fingerprint", ""))
            recorded_max_passes = ev.get("max_passes")
            state.max_passes = (
                int(recorded_max_passes) if recorded_max_passes is not None else None
            )
            state.rows = {i: RowState() for i in range(state.total_rows)}
        elif name == "player_done":
            row = state.rows[int(ev["index"])]
            state.player_legs += 1
            if ev.get("status") == "ok":
                row.status = ROW_AWAITING_COACH
                row.player_content = str(ev["player_content"])
            else:
                row.status = ROW_REJECTED
                row.reason = str(ev.get("reason", "unknown"))
        elif name == "window1_complete":
            state.window = 2
        elif name == "accept_pending":
            state.rows[int(ev["index"])].status = ROW_ACCEPT_PENDING
        elif name == "coach_done":
            row = state.rows[int(ev["index"])]
            state.coach_evals += 1
            status = ev.get("status")
            if status == "accepted":
                row.status = ROW_ACCEPTED
            elif status == "revise":
                row.status = ROW_REVISE
                row.coach_feedback = str(ev.get("coach_feedback", ""))
            else:
                row.status = ROW_REJECTED
                row.reason = str(ev.get("reason", "unknown"))
        elif name == "window2_complete":
            if ev.get("next") == "pass":
                state.pass_number += 1
                state.window = 1
                for row in state.rows.values():
                    if row.status == ROW_REVISE:
                        row.status = ROW_PENDING_PLAYER
        elif name == "row_finalised":
            row = state.rows[int(ev["index"])]
            row.status = ROW_REJECTED
            row.reason = str(ev.get("reason", "max_turns_exhausted"))
        elif name == "run_complete":
            state.complete = True
        else:
            raise BatchStateError(
                f"Unknown batch state event {name!r} at line {lineno + 1}"
            )


__all__ = [
    "BATCH_STATE_FILENAME",
    "BatchRunState",
    "BatchStateError",
    "BatchStateManager",
    "ROW_ACCEPT_PENDING",
    "ROW_ACCEPTED",
    "ROW_AWAITING_COACH",
    "ROW_PENDING_PLAYER",
    "ROW_REJECTED",
    "ROW_REVISE",
    "RowState",
]
