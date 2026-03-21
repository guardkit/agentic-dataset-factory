"""Output directory management and append-mode file handles.

Implements the output directory lifecycle for the generation pipeline:

1. **Directory creation** — ``output/`` and ``output/rag_index/`` are
   created on startup if they don't exist.
2. **Fresh start** — all files except ``.lock`` are removed (ADR-ARCH-008).
3. **Resume** — existing ``train.jsonl``, ``rejected.jsonl``, and
   ``knowledge.jsonl`` are preserved for incremental append.
4. **Append-mode handles** — ``OutputFileManager`` opens the three JSONL
   files in append mode for the generation loop.

References:
    - ``docs/design/contracts/API-output.md`` (directory structure)
    - ``docs/architecture/decisions/ADR-ARCH-008-start-fresh-restart.md``
    - ``features/entrypoint/entrypoint.feature`` (BDD scenarios)
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import TracebackType
from typing import IO

logger = logging.getLogger(__name__)

TRAIN_FILENAME = "train.jsonl"
REJECTED_FILENAME = "rejected.jsonl"
KNOWLEDGE_FILENAME = "knowledge.jsonl"
RAG_INDEX_DIRNAME = "rag_index"


class OutputFileManager:
    """Context manager that opens output JSONL files in append mode.

    Opens ``train.jsonl``, ``rejected.jsonl``, and
    ``rag_index/knowledge.jsonl`` in append mode (``"a"``) so the
    generation loop can write to them incrementally. All three handles
    are closed when the context manager exits.

    Usage::

        with OutputFileManager(output_dir) as ofm:
            ofm.train_fh.write(json.dumps(example) + "\\n")
            ofm.rejected_fh.write(json.dumps(rejection) + "\\n")
            ofm.knowledge_fh.write(json.dumps(knowledge) + "\\n")

    Attributes:
        output_dir: Path to the output directory.
        train_fh: File handle for ``train.jsonl`` (append mode).
        rejected_fh: File handle for ``rejected.jsonl`` (append mode).
        knowledge_fh: File handle for ``rag_index/knowledge.jsonl``
            (append mode).
    """

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = Path(output_dir)
        self._handles: list[IO[str]] = []
        self.train_fh: IO[str] | None = None
        self.rejected_fh: IO[str] | None = None
        self.knowledge_fh: IO[str] | None = None

    def open(self) -> OutputFileManager:
        """Open all three JSONL files in append mode.

        Creates the files if they don't exist. Each file is opened with
        UTF-8 encoding.

        Returns:
            ``self`` for fluent usage.

        Raises:
            OSError: If a file cannot be opened.
        """
        try:
            train_path = self._output_dir / TRAIN_FILENAME
            rejected_path = self._output_dir / REJECTED_FILENAME
            knowledge_path = self._output_dir / RAG_INDEX_DIRNAME / KNOWLEDGE_FILENAME

            self.train_fh = open(train_path, "a", encoding="utf-8")  # noqa: SIM115
            self._handles.append(self.train_fh)

            self.rejected_fh = open(rejected_path, "a", encoding="utf-8")  # noqa: SIM115
            self._handles.append(self.rejected_fh)

            self.knowledge_fh = open(knowledge_path, "a", encoding="utf-8")  # noqa: SIM115
            self._handles.append(self.knowledge_fh)

            logger.info(
                "Output files opened in append mode: %s, %s, %s",
                train_path,
                rejected_path,
                knowledge_path,
            )
        except Exception:
            # If any file fails to open, close the ones already opened
            self.close()
            raise

        return self

    def close(self) -> None:
        """Close all open file handles. Safe to call multiple times."""
        for fh in self._handles:
            try:
                fh.close()
            except Exception:
                logger.warning("Error closing file handle", exc_info=True)
        self._handles.clear()
        self.train_fh = None
        self.rejected_fh = None
        self.knowledge_fh = None

    def __enter__(self) -> OutputFileManager:
        return self.open()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()


__all__ = [
    "KNOWLEDGE_FILENAME",
    "OutputFileManager",
    "RAG_INDEX_DIRNAME",
    "REJECTED_FILENAME",
    "TRAIN_FILENAME",
]
