"""Tests for checkpoint/resume logic and lock file concurrency guard.

Covers all acceptance criteria from TASK-EP-005:
  AC-001: Checkpoint written atomically after each target completion
  AC-002: --resume reads checkpoint and continues from saved index
  AC-003: Error raised if --resume without checkpoint file
  AC-004: Fresh start cleans output directory
  AC-005: Lock file prevents concurrent processes
  AC-006: Checkpoint file survives process interruption (atomic write)
  AC-007: All modified files pass lint/format checks
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from entrypoint.checkpoint import (
    CheckpointManager,
    LockFileError,
    LockManager,
    NoCheckpointError,
    prepare_output_directory,
)


# ━━ Checkpoint Tests ━━


class TestCheckpointManager:
    """Tests for CheckpointManager: atomic writes, reads, resume logic."""

    def test_save_checkpoint_creates_file(self, tmp_path: Path) -> None:
        """AC-001: Checkpoint written after each target completion."""
        mgr = CheckpointManager(output_dir=tmp_path)
        mgr.save(5)
        checkpoint_file = tmp_path / ".checkpoint"
        assert checkpoint_file.exists()
        assert checkpoint_file.read_text().strip() == "5"

    def test_save_checkpoint_overwrites_previous(self, tmp_path: Path) -> None:
        """AC-001: Subsequent saves update the checkpoint value."""
        mgr = CheckpointManager(output_dir=tmp_path)
        mgr.save(3)
        mgr.save(10)
        assert (tmp_path / ".checkpoint").read_text().strip() == "10"

    def test_save_checkpoint_atomically(self, tmp_path: Path) -> None:
        """AC-006: Atomic write via temp file + os.rename."""
        mgr = CheckpointManager(output_dir=tmp_path)
        # Write initial checkpoint
        mgr.save(42)
        # The checkpoint file should contain the final value, not a partial write
        assert (tmp_path / ".checkpoint").read_text().strip() == "42"
        # Verify no temp files are left behind
        temp_files = list(tmp_path.glob(".checkpoint.tmp*"))
        assert temp_files == []

    def test_save_checkpoint_atomic_rename_preserves_previous_on_failure(
        self, tmp_path: Path
    ) -> None:
        """AC-006: If atomic write fails, previous checkpoint remains intact."""
        mgr = CheckpointManager(output_dir=tmp_path)
        mgr.save(100)

        # Simulate os.rename failure during second save
        with patch("os.rename", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                mgr.save(200)

        # Previous checkpoint should still be intact
        assert (tmp_path / ".checkpoint").read_text().strip() == "100"

    def test_load_checkpoint_returns_saved_index(self, tmp_path: Path) -> None:
        """AC-002: Reading checkpoint returns the saved target index."""
        mgr = CheckpointManager(output_dir=tmp_path)
        mgr.save(799)
        loaded = mgr.load()
        assert loaded == 799

    def test_load_checkpoint_raises_when_no_file(self, tmp_path: Path) -> None:
        """AC-003: Error raised if --resume without checkpoint file."""
        mgr = CheckpointManager(output_dir=tmp_path)
        with pytest.raises(NoCheckpointError, match="no checkpoint"):
            mgr.load()

    def test_load_checkpoint_raises_on_corrupt_content(self, tmp_path: Path) -> None:
        """AC-003 edge: Corrupt checkpoint file should raise clear error."""
        (tmp_path / ".checkpoint").write_text("not-a-number\n")
        mgr = CheckpointManager(output_dir=tmp_path)
        with pytest.raises(NoCheckpointError, match="corrupt"):
            mgr.load()

    def test_load_checkpoint_raises_on_negative_index(self, tmp_path: Path) -> None:
        """AC-003 edge: Negative checkpoint index is invalid."""
        (tmp_path / ".checkpoint").write_text("-1\n")
        mgr = CheckpointManager(output_dir=tmp_path)
        with pytest.raises(NoCheckpointError, match="corrupt"):
            mgr.load()

    def test_save_zero_index(self, tmp_path: Path) -> None:
        """AC-001: Zero is a valid checkpoint index (first target completed)."""
        mgr = CheckpointManager(output_dir=tmp_path)
        mgr.save(0)
        assert mgr.load() == 0

    def test_clear_removes_checkpoint(self, tmp_path: Path) -> None:
        """Checkpoint can be cleared for fresh starts."""
        mgr = CheckpointManager(output_dir=tmp_path)
        mgr.save(5)
        mgr.clear()
        assert not (tmp_path / ".checkpoint").exists()

    def test_clear_is_idempotent(self, tmp_path: Path) -> None:
        """Clearing when no checkpoint exists does not raise."""
        mgr = CheckpointManager(output_dir=tmp_path)
        mgr.clear()  # Should not raise


# ━━ Lock File Tests ━━


class TestLockManager:
    """Tests for LockManager: fcntl-based lock file concurrency guard."""

    def test_acquire_creates_lock_file(self, tmp_path: Path) -> None:
        """AC-005: Lock file is created when acquired."""
        mgr = LockManager(output_dir=tmp_path)
        mgr.acquire()
        try:
            assert (tmp_path / ".lock").exists()
        finally:
            mgr.release()

    def test_release_unlocks_file(self, tmp_path: Path) -> None:
        """AC-005: Lock is released so another process can acquire it."""
        mgr = LockManager(output_dir=tmp_path)
        mgr.acquire()
        mgr.release()

        # A second manager should be able to acquire after release
        mgr2 = LockManager(output_dir=tmp_path)
        mgr2.acquire()
        mgr2.release()

    def test_concurrent_lock_raises_error(self, tmp_path: Path) -> None:
        """AC-005: Second process fails to acquire lock held by first."""
        mgr1 = LockManager(output_dir=tmp_path)
        mgr1.acquire()
        try:
            mgr2 = LockManager(output_dir=tmp_path)
            with pytest.raises(LockFileError, match="already in use"):
                mgr2.acquire()
        finally:
            mgr1.release()

    def test_context_manager_acquires_and_releases(self, tmp_path: Path) -> None:
        """AC-005: Context manager pattern for automatic lock lifecycle."""
        mgr = LockManager(output_dir=tmp_path)
        with mgr:
            assert (tmp_path / ".lock").exists()

        # After exiting context, another lock can be acquired
        mgr2 = LockManager(output_dir=tmp_path)
        mgr2.acquire()
        mgr2.release()

    def test_release_without_acquire_is_safe(self, tmp_path: Path) -> None:
        """Releasing without acquiring should not raise."""
        mgr = LockManager(output_dir=tmp_path)
        mgr.release()  # Should not raise

    def test_double_release_is_safe(self, tmp_path: Path) -> None:
        """Releasing twice should not raise."""
        mgr = LockManager(output_dir=tmp_path)
        mgr.acquire()
        mgr.release()
        mgr.release()  # Should not raise


# ━━ Output Directory Tests ━━


class TestPrepareOutputDirectory:
    """Tests for output directory preparation: fresh vs resume modes."""

    def test_fresh_start_cleans_output_directory(self, tmp_path: Path) -> None:
        """AC-004: Fresh start cleans output directory."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "train.jsonl").write_text('{"example": 1}\n')
        (output_dir / ".checkpoint").write_text("5\n")
        rag_dir = output_dir / "rag_index"
        rag_dir.mkdir()
        (rag_dir / "index.bin").write_text("data")

        prepare_output_directory(output_dir=output_dir, resume=False)

        # Directory should exist but be empty of previous content
        assert output_dir.exists()
        assert not (output_dir / "train.jsonl").exists()
        assert not (output_dir / ".checkpoint").exists()
        # rag_index subdirectory should be recreated
        assert (output_dir / "rag_index").is_dir()

    def test_fresh_start_creates_output_directory(self, tmp_path: Path) -> None:
        """AC-004: Fresh start creates output dir if it doesn't exist."""
        output_dir = tmp_path / "output"
        assert not output_dir.exists()

        prepare_output_directory(output_dir=output_dir, resume=False)

        assert output_dir.is_dir()
        assert (output_dir / "rag_index").is_dir()

    def test_resume_preserves_output_files(self, tmp_path: Path) -> None:
        """AC-002: Resume mode preserves existing output files."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "train.jsonl").write_text('{"example": 1}\n')
        checkpoint = output_dir / ".checkpoint"
        checkpoint.write_text("5\n")

        prepare_output_directory(output_dir=output_dir, resume=True)

        assert (output_dir / "train.jsonl").exists()
        assert checkpoint.exists()
        assert checkpoint.read_text().strip() == "5"

    def test_resume_creates_rag_index_if_missing(self, tmp_path: Path) -> None:
        """AC-002: Resume creates rag_index dir if not present."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / ".checkpoint").write_text("0\n")

        prepare_output_directory(output_dir=output_dir, resume=True)

        assert (output_dir / "rag_index").is_dir()

    def test_resume_creates_output_dir_if_missing(self, tmp_path: Path) -> None:
        """Resume with missing output dir creates it."""
        output_dir = tmp_path / "output"

        prepare_output_directory(output_dir=output_dir, resume=True)

        assert output_dir.is_dir()
        assert (output_dir / "rag_index").is_dir()
