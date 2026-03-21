"""Tests for output directory management and append-mode file handles.

Covers acceptance criteria for TASK-EP-006:
  AC-001: Output directory structure created on startup
  AC-002: Fresh start removes previous output files (preserving .lock)
  AC-003: Resume preserves existing output files
  AC-004: Files opened in append mode for generation loop compatibility
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from entrypoint.checkpoint import (
    LOCK_FILENAME,
    RAG_INDEX_DIRNAME,
    prepare_output_directory,
)
from entrypoint.output import (
    KNOWLEDGE_FILENAME,
    REJECTED_FILENAME,
    TRAIN_FILENAME,
    OutputFileManager,
)


# ━━ AC-001: Output directory structure created on startup ━━


class TestOutputDirectoryCreation:
    """AC-001: Output directory structure created on startup."""

    def test_creates_output_dir_when_missing(self, tmp_path: Path) -> None:
        """output/ is created when it doesn't exist."""
        output_dir = tmp_path / "output"
        assert not output_dir.exists()

        prepare_output_directory(output_dir=output_dir, resume=False)

        assert output_dir.is_dir()

    def test_creates_rag_index_subdir(self, tmp_path: Path) -> None:
        """output/rag_index/ is created as part of the directory structure."""
        output_dir = tmp_path / "output"

        prepare_output_directory(output_dir=output_dir, resume=False)

        assert (output_dir / RAG_INDEX_DIRNAME).is_dir()

    def test_creates_output_dir_on_resume_when_missing(self, tmp_path: Path) -> None:
        """Resume mode also creates output/ if it doesn't exist."""
        output_dir = tmp_path / "output"
        assert not output_dir.exists()

        prepare_output_directory(output_dir=output_dir, resume=True)

        assert output_dir.is_dir()
        assert (output_dir / RAG_INDEX_DIRNAME).is_dir()

    def test_idempotent_creation(self, tmp_path: Path) -> None:
        """Calling prepare_output_directory twice doesn't raise."""
        output_dir = tmp_path / "output"

        prepare_output_directory(output_dir=output_dir, resume=False)
        prepare_output_directory(output_dir=output_dir, resume=False)

        assert output_dir.is_dir()
        assert (output_dir / RAG_INDEX_DIRNAME).is_dir()

    def test_creates_nested_parent_directories(self, tmp_path: Path) -> None:
        """Output dir with missing parents is created (parents=True)."""
        output_dir = tmp_path / "deep" / "nested" / "output"

        prepare_output_directory(output_dir=output_dir, resume=False)

        assert output_dir.is_dir()
        assert (output_dir / RAG_INDEX_DIRNAME).is_dir()


# ━━ AC-002: Fresh start removes previous output files ━━


class TestFreshStartCleaning:
    """AC-002: Fresh start removes previous output files."""

    def test_fresh_start_removes_train_jsonl(self, tmp_path: Path) -> None:
        """train.jsonl is removed on fresh start."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / TRAIN_FILENAME).write_text('{"example": 1}\n')

        prepare_output_directory(output_dir=output_dir, resume=False)

        assert not (output_dir / TRAIN_FILENAME).exists()

    def test_fresh_start_removes_rejected_jsonl(self, tmp_path: Path) -> None:
        """rejected.jsonl is removed on fresh start."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / REJECTED_FILENAME).write_text('{"rejection": 1}\n')

        prepare_output_directory(output_dir=output_dir, resume=False)

        assert not (output_dir / REJECTED_FILENAME).exists()

    def test_fresh_start_removes_rag_index_contents(self, tmp_path: Path) -> None:
        """rag_index/ contents are removed on fresh start."""
        output_dir = tmp_path / "output"
        rag_dir = output_dir / RAG_INDEX_DIRNAME
        rag_dir.mkdir(parents=True)
        (rag_dir / KNOWLEDGE_FILENAME).write_text('{"knowledge": 1}\n')
        (rag_dir / "index.bin").write_text("binary data")

        prepare_output_directory(output_dir=output_dir, resume=False)

        # rag_index/ should be recreated but empty of previous content
        assert (output_dir / RAG_INDEX_DIRNAME).is_dir()
        assert not (rag_dir / KNOWLEDGE_FILENAME).exists()
        assert not (rag_dir / "index.bin").exists()

    def test_fresh_start_removes_checkpoint(self, tmp_path: Path) -> None:
        """Checkpoint file is removed on fresh start."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / ".checkpoint").write_text("5\n")

        prepare_output_directory(output_dir=output_dir, resume=False)

        assert not (output_dir / ".checkpoint").exists()

    def test_fresh_start_preserves_lock_file(self, tmp_path: Path) -> None:
        """BDD: Fresh start cleans the output directory but preserves .lock."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        lock_file = output_dir / LOCK_FILENAME
        lock_file.write_text("")
        (output_dir / TRAIN_FILENAME).write_text('{"example": 1}\n')
        (output_dir / ".checkpoint").write_text("5\n")

        prepare_output_directory(output_dir=output_dir, resume=False)

        # Lock file must survive
        assert lock_file.exists()
        # Other files should be gone
        assert not (output_dir / TRAIN_FILENAME).exists()
        assert not (output_dir / ".checkpoint").exists()

    def test_fresh_start_recreates_rag_index_directory(self, tmp_path: Path) -> None:
        """rag_index/ is recreated after cleaning."""
        output_dir = tmp_path / "output"
        rag_dir = output_dir / RAG_INDEX_DIRNAME
        rag_dir.mkdir(parents=True)
        (rag_dir / KNOWLEDGE_FILENAME).write_text('{"k": 1}\n')

        prepare_output_directory(output_dir=output_dir, resume=False)

        assert rag_dir.is_dir()
        assert list(rag_dir.iterdir()) == []

    def test_fresh_start_with_nonexistent_dir(self, tmp_path: Path) -> None:
        """Fresh start on a nonexistent output dir creates it cleanly."""
        output_dir = tmp_path / "output"
        assert not output_dir.exists()

        prepare_output_directory(output_dir=output_dir, resume=False)

        assert output_dir.is_dir()
        assert (output_dir / RAG_INDEX_DIRNAME).is_dir()

    def test_fresh_start_removes_all_non_lock_files(self, tmp_path: Path) -> None:
        """All files except .lock are removed, including arbitrary files."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        lock_file = output_dir / LOCK_FILENAME
        lock_file.write_text("")
        (output_dir / TRAIN_FILENAME).write_text("data")
        (output_dir / REJECTED_FILENAME).write_text("data")
        (output_dir / ".checkpoint").write_text("0")
        (output_dir / "unexpected_file.txt").write_text("data")
        rag_dir = output_dir / RAG_INDEX_DIRNAME
        rag_dir.mkdir()
        (rag_dir / KNOWLEDGE_FILENAME).write_text("data")

        prepare_output_directory(output_dir=output_dir, resume=False)

        remaining = {p.name for p in output_dir.iterdir()}
        assert remaining == {LOCK_FILENAME, RAG_INDEX_DIRNAME}
        assert list((output_dir / RAG_INDEX_DIRNAME).iterdir()) == []


# ━━ AC-003: Resume preserves existing output files ━━


class TestResumePreservation:
    """AC-003: Resume preserves existing output files."""

    def test_resume_preserves_train_jsonl(self, tmp_path: Path) -> None:
        """train.jsonl is preserved on resume."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        train_file = output_dir / TRAIN_FILENAME
        train_file.write_text('{"example": 1}\n')

        prepare_output_directory(output_dir=output_dir, resume=True)

        assert train_file.exists()
        assert train_file.read_text() == '{"example": 1}\n'

    def test_resume_preserves_rejected_jsonl(self, tmp_path: Path) -> None:
        """rejected.jsonl is preserved on resume."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        rejected_file = output_dir / REJECTED_FILENAME
        rejected_file.write_text('{"rejection": 1}\n')

        prepare_output_directory(output_dir=output_dir, resume=True)

        assert rejected_file.exists()
        assert rejected_file.read_text() == '{"rejection": 1}\n'

    def test_resume_preserves_knowledge_jsonl(self, tmp_path: Path) -> None:
        """rag_index/knowledge.jsonl is preserved on resume."""
        output_dir = tmp_path / "output"
        rag_dir = output_dir / RAG_INDEX_DIRNAME
        rag_dir.mkdir(parents=True)
        knowledge_file = rag_dir / KNOWLEDGE_FILENAME
        knowledge_file.write_text('{"knowledge": 1}\n')

        prepare_output_directory(output_dir=output_dir, resume=True)

        assert knowledge_file.exists()
        assert knowledge_file.read_text() == '{"knowledge": 1}\n'

    def test_resume_preserves_checkpoint(self, tmp_path: Path) -> None:
        """Checkpoint file is preserved on resume."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        checkpoint = output_dir / ".checkpoint"
        checkpoint.write_text("42\n")

        prepare_output_directory(output_dir=output_dir, resume=True)

        assert checkpoint.exists()
        assert checkpoint.read_text().strip() == "42"

    def test_resume_creates_rag_index_if_missing(self, tmp_path: Path) -> None:
        """Resume creates rag_index/ if not present."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        prepare_output_directory(output_dir=output_dir, resume=True)

        assert (output_dir / RAG_INDEX_DIRNAME).is_dir()

    def test_resume_preserves_all_existing_files(self, tmp_path: Path) -> None:
        """All files are preserved on resume, including lock and checkpoint."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / TRAIN_FILENAME).write_text("train")
        (output_dir / REJECTED_FILENAME).write_text("rejected")
        (output_dir / ".checkpoint").write_text("10")
        (output_dir / LOCK_FILENAME).write_text("")
        rag_dir = output_dir / RAG_INDEX_DIRNAME
        rag_dir.mkdir()
        (rag_dir / KNOWLEDGE_FILENAME).write_text("knowledge")

        prepare_output_directory(output_dir=output_dir, resume=True)

        assert (output_dir / TRAIN_FILENAME).read_text() == "train"
        assert (output_dir / REJECTED_FILENAME).read_text() == "rejected"
        assert (output_dir / ".checkpoint").read_text() == "10"
        assert (output_dir / LOCK_FILENAME).read_text() == ""
        assert (rag_dir / KNOWLEDGE_FILENAME).read_text() == "knowledge"


# ━━ AC-004: Files opened in append mode ━━


class TestOutputFileManager:
    """AC-004: Files opened in append mode for generation loop compatibility."""

    def test_opens_all_three_files(self, tmp_path: Path) -> None:
        """OutputFileManager opens train, rejected, and knowledge handles."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / RAG_INDEX_DIRNAME).mkdir()

        with OutputFileManager(output_dir) as ofm:
            assert ofm.train_fh is not None
            assert ofm.rejected_fh is not None
            assert ofm.knowledge_fh is not None

    def test_files_opened_in_append_mode(self, tmp_path: Path) -> None:
        """All file handles use append mode ('a')."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / RAG_INDEX_DIRNAME).mkdir()

        with OutputFileManager(output_dir) as ofm:
            assert ofm.train_fh.mode == "a"  # type: ignore[union-attr]
            assert ofm.rejected_fh.mode == "a"  # type: ignore[union-attr]
            assert ofm.knowledge_fh.mode == "a"  # type: ignore[union-attr]

    def test_append_preserves_existing_content(self, tmp_path: Path) -> None:
        """Writing via append mode preserves data already in the file."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / RAG_INDEX_DIRNAME).mkdir()

        # Write initial content
        train_file = output_dir / TRAIN_FILENAME
        train_file.write_text('{"existing": true}\n')

        # Open in append mode and write more
        with OutputFileManager(output_dir) as ofm:
            ofm.train_fh.write('{"new": true}\n')  # type: ignore[union-attr]

        lines = train_file.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"existing": True}
        assert json.loads(lines[1]) == {"new": True}

    def test_write_to_all_three_files(self, tmp_path: Path) -> None:
        """Data can be written to all three output files."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / RAG_INDEX_DIRNAME).mkdir()

        example = {"messages": [{"role": "user", "content": "hello"}]}
        rejection = {"generation_target": {}, "turns": 3, "final_score": 2}
        knowledge = {"messages": [{"role": "system", "content": "fact"}]}

        with OutputFileManager(output_dir) as ofm:
            ofm.train_fh.write(json.dumps(example) + "\n")  # type: ignore[union-attr]
            ofm.rejected_fh.write(json.dumps(rejection) + "\n")  # type: ignore[union-attr]
            ofm.knowledge_fh.write(json.dumps(knowledge) + "\n")  # type: ignore[union-attr]

        assert json.loads((output_dir / TRAIN_FILENAME).read_text().strip()) == example
        assert json.loads((output_dir / REJECTED_FILENAME).read_text().strip()) == rejection
        knowledge_path = output_dir / RAG_INDEX_DIRNAME / KNOWLEDGE_FILENAME
        assert json.loads(knowledge_path.read_text().strip()) == knowledge

    def test_context_manager_closes_handles(self, tmp_path: Path) -> None:
        """File handles are closed when leaving the context manager."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / RAG_INDEX_DIRNAME).mkdir()

        with OutputFileManager(output_dir) as ofm:
            train_fh = ofm.train_fh
            rejected_fh = ofm.rejected_fh
            knowledge_fh = ofm.knowledge_fh

        assert train_fh.closed  # type: ignore[union-attr]
        assert rejected_fh.closed  # type: ignore[union-attr]
        assert knowledge_fh.closed  # type: ignore[union-attr]

    def test_handles_are_none_after_close(self, tmp_path: Path) -> None:
        """After close(), all file handle attributes are set to None."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / RAG_INDEX_DIRNAME).mkdir()

        ofm = OutputFileManager(output_dir)
        ofm.open()
        ofm.close()

        assert ofm.train_fh is None
        assert ofm.rejected_fh is None
        assert ofm.knowledge_fh is None

    def test_close_is_idempotent(self, tmp_path: Path) -> None:
        """Calling close() multiple times doesn't raise."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / RAG_INDEX_DIRNAME).mkdir()

        ofm = OutputFileManager(output_dir)
        ofm.open()
        ofm.close()
        ofm.close()  # Should not raise

    def test_creates_files_if_not_exist(self, tmp_path: Path) -> None:
        """Files are created if they don't exist when opened in append mode."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / RAG_INDEX_DIRNAME).mkdir()

        with OutputFileManager(output_dir) as ofm:
            assert ofm.train_fh is not None

        assert (output_dir / TRAIN_FILENAME).exists()
        assert (output_dir / REJECTED_FILENAME).exists()
        assert (output_dir / RAG_INDEX_DIRNAME / KNOWLEDGE_FILENAME).exists()

    def test_handles_exception_during_open(self, tmp_path: Path) -> None:
        """If rag_index/ is missing, open raises and cleans up handles."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        # Deliberately NOT creating rag_index/ — knowledge.jsonl open fails

        with pytest.raises(FileNotFoundError):
            with OutputFileManager(output_dir):
                pass  # Should not reach here

    def test_multiple_appends_across_sessions(self, tmp_path: Path) -> None:
        """Multiple open/close cycles correctly append to the same files."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / RAG_INDEX_DIRNAME).mkdir()

        # Session 1
        with OutputFileManager(output_dir) as ofm:
            ofm.train_fh.write('{"session": 1}\n')  # type: ignore[union-attr]

        # Session 2
        with OutputFileManager(output_dir) as ofm:
            ofm.train_fh.write('{"session": 2}\n')  # type: ignore[union-attr]

        lines = (output_dir / TRAIN_FILENAME).read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"session": 1}
        assert json.loads(lines[1]) == {"session": 2}


# ━━ Integration: prepare_output_directory + OutputFileManager ━━


class TestPrepareOutputThenOpen:
    """Integration: prepare_output_directory followed by OutputFileManager."""

    def test_fresh_then_open_creates_empty_files(self, tmp_path: Path) -> None:
        """After fresh start, opening files creates them empty."""
        output_dir = tmp_path / "output"

        prepare_output_directory(output_dir=output_dir, resume=False)

        with OutputFileManager(output_dir) as ofm:
            ofm.train_fh.write('{"fresh": true}\n')  # type: ignore[union-attr]

        content = (output_dir / TRAIN_FILENAME).read_text()
        assert content == '{"fresh": true}\n'

    def test_resume_then_open_appends_to_existing(self, tmp_path: Path) -> None:
        """After resume, opening files appends to existing content."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / RAG_INDEX_DIRNAME).mkdir()
        (output_dir / TRAIN_FILENAME).write_text('{"old": true}\n')

        prepare_output_directory(output_dir=output_dir, resume=True)

        with OutputFileManager(output_dir) as ofm:
            ofm.train_fh.write('{"new": true}\n')  # type: ignore[union-attr]

        lines = (output_dir / TRAIN_FILENAME).read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"old": True}
        assert json.loads(lines[1]) == {"new": True}

    def test_fresh_start_with_lock_then_open(self, tmp_path: Path) -> None:
        """Fresh start preserves .lock then files open correctly."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / LOCK_FILENAME).write_text("")
        (output_dir / TRAIN_FILENAME).write_text("old data\n")

        prepare_output_directory(output_dir=output_dir, resume=False)

        assert (output_dir / LOCK_FILENAME).exists()
        assert not (output_dir / TRAIN_FILENAME).exists()

        with OutputFileManager(output_dir) as ofm:
            ofm.train_fh.write('{"after_clean": true}\n')  # type: ignore[union-attr]

        content = (output_dir / TRAIN_FILENAME).read_text()
        assert content == '{"after_clean": true}\n'
