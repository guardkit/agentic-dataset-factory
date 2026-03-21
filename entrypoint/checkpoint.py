"""Checkpoint/resume logic and lock file concurrency guard.

Implements ADR-ARCH-010 (checkpoint/resume) and ASSUM-002 (lock file guard).

Checkpoint:
    Atomic write of target index to ``output/.checkpoint`` after each completed
    target. Supports ``--resume`` (continue from saved index) and ``--fresh``
    (clean output directory, the default per ADR-ARCH-008).

Lock file:
    Uses ``fcntl.flock()`` to prevent concurrent entrypoint processes writing
    to the same output directory.

Output directory:
    ``prepare_output_directory`` handles fresh-start cleaning vs resume
    preservation, and ensures the required subdirectory structure exists.
"""
from __future__ import annotations

import fcntl
import logging
import os
import shutil
import tempfile
from pathlib import Path
from types import TracebackType

logger = logging.getLogger(__name__)

CHECKPOINT_FILENAME = ".checkpoint"
LOCK_FILENAME = ".lock"
RAG_INDEX_DIRNAME = "rag_index"


# ━━ Exceptions ━━


class NoCheckpointError(FileNotFoundError):
    """Raised when --resume is requested but no valid checkpoint exists."""


class LockFileError(OSError):
    """Raised when the output directory lock cannot be acquired."""


# ━━ CheckpointManager ━━


class CheckpointManager:
    """Manages atomic checkpoint writes and reads for the generation loop.

    The checkpoint records the last completed target index so that a
    ``--resume`` invocation can skip already-processed targets.

    Attributes:
        output_dir: Path to the output directory containing the checkpoint file.
    """

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = Path(output_dir)
        self._checkpoint_path = self._output_dir / CHECKPOINT_FILENAME

    def save(self, target_index: int) -> None:
        """Write the completed target index atomically.

        Writes to a temporary file in the same directory then renames,
        ensuring the checkpoint is never half-written on process kill.

        Args:
            target_index: Zero-based index of the last completed target.

        Raises:
            OSError: If the atomic rename fails (previous checkpoint is preserved).
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Write to a temp file in the same directory for atomic rename
        fd, tmp_path = tempfile.mkstemp(
            prefix=f"{CHECKPOINT_FILENAME}.tmp",
            dir=str(self._output_dir),
        )
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write(f"{target_index}\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.rename(tmp_path, str(self._checkpoint_path))
            logger.debug("Checkpoint saved: target_index=%d", target_index)
        except BaseException:
            # Clean up temp file on failure; previous checkpoint stays intact
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
            raise

    def load(self) -> int:
        """Read the saved checkpoint index.

        Returns:
            The zero-based index of the last completed target.

        Raises:
            NoCheckpointError: If no checkpoint file exists or it is corrupt.
        """
        if not self._checkpoint_path.exists():
            raise NoCheckpointError(
                f"Cannot resume: no checkpoint file found at {self._checkpoint_path}"
            )

        raw = self._checkpoint_path.read_text().strip()
        try:
            index = int(raw)
        except ValueError:
            raise NoCheckpointError(
                f"Cannot resume: corrupt checkpoint file at {self._checkpoint_path} "
                f"(expected integer, got {raw!r})"
            ) from None

        if index < 0:
            raise NoCheckpointError(
                f"Cannot resume: corrupt checkpoint file at {self._checkpoint_path} "
                f"(negative index {index})"
            )

        logger.debug("Checkpoint loaded: target_index=%d", index)
        return index

    def clear(self) -> None:
        """Remove the checkpoint file, if it exists."""
        try:
            self._checkpoint_path.unlink()
            logger.debug("Checkpoint cleared")
        except FileNotFoundError:
            pass


# ━━ LockManager ━━


class LockManager:
    """Concurrency guard using fcntl file locking.

    Prevents two entrypoint processes from writing to the same output
    directory simultaneously. Supports both explicit acquire/release
    and context-manager usage.

    Attributes:
        output_dir: Path to the output directory containing the lock file.
    """

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = Path(output_dir)
        self._lock_path = self._output_dir / LOCK_FILENAME
        self._lock_fd: int | None = None

    def acquire(self) -> None:
        """Acquire an exclusive lock on the output directory.

        Creates the lock file if it does not exist, then attempts a
        non-blocking exclusive lock via ``fcntl.flock()``.

        Raises:
            LockFileError: If the lock is already held by another process.
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)

        fd = os.open(str(self._lock_path), os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            raise LockFileError(
                f"Output directory already in use: {self._output_dir}. "
                f"Another entrypoint process holds the lock on {self._lock_path}."
            ) from None

        self._lock_fd = fd
        logger.info("Lock acquired: %s", self._lock_path)

    def release(self) -> None:
        """Release the lock if held. Safe to call multiple times."""
        if self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
                logger.info("Lock released: %s", self._lock_path)
            except OSError:
                logger.warning("Error releasing lock on %s", self._lock_path, exc_info=True)
            finally:
                self._lock_fd = None

    def __enter__(self) -> LockManager:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.release()


# ━━ Output Directory Preparation ━━


def prepare_output_directory(output_dir: Path, *, resume: bool) -> None:
    """Prepare the output directory for a generation run.

    On fresh start (``resume=False``): removes all files in the output
    directory **except** the ``.lock`` file, then recreates the required
    subdirectory structure (ADR-ARCH-008).

    On resume (``resume=True``): preserves existing files and ensures
    the required subdirectory structure exists.

    Args:
        output_dir: Path to the output directory.
        resume: If True, preserve existing files; if False, clean first.
    """
    output_dir = Path(output_dir)

    if resume:
        logger.info("Resume mode: preserving existing output in %s", output_dir)
    else:
        logger.info("Fresh start: cleaning output directory %s", output_dir)
        if output_dir.exists():
            _clean_output_directory(output_dir)

    # Ensure directory structure exists
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / RAG_INDEX_DIRNAME).mkdir(exist_ok=True)


def _clean_output_directory(output_dir: Path) -> None:
    """Remove all files and subdirectories in *output_dir* except ``.lock``.

    The ``.lock`` file is preserved because it may be held by the current
    process via :class:`LockManager`.  All other files (``train.jsonl``,
    ``rejected.jsonl``, ``.checkpoint``, etc.) and subdirectories
    (``rag_index/``) are removed.

    Args:
        output_dir: Path to the output directory to clean.
    """
    for child in output_dir.iterdir():
        if child.name == LOCK_FILENAME:
            logger.debug("Preserving lock file: %s", child)
            continue
        if child.is_dir():
            shutil.rmtree(child)
            logger.debug("Removed directory: %s", child)
        else:
            child.unlink()
            logger.debug("Removed file: %s", child)
