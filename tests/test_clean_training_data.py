"""Tests for scripts/clean_training_data.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.clean_training_data import (
    CleaningStats,
    clean_training_data,
    has_unclosed_think,
    is_degenerate,
    is_empty_assistant,
    repair_think_blocks,
)


def _make_entry(
    system: str = "You are a tutor.",
    user: str = "Hello",
    assistant: str = "Hi there!",
) -> dict:
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }


class TestIsDegenerate:
    def test_normal_entry(self):
        assert is_degenerate(_make_entry()) is False

    def test_system_placeholder(self):
        assert is_degenerate(_make_entry(system="...")) is True

    def test_user_placeholder(self):
        assert is_degenerate(_make_entry(user="...")) is True

    def test_assistant_placeholder(self):
        assert is_degenerate(_make_entry(assistant="...")) is True

    def test_ellipsis_in_sentence(self):
        assert is_degenerate(_make_entry(assistant="Wait... let me think")) is False

    def test_whitespace_around_dots(self):
        assert is_degenerate(_make_entry(assistant="  ...  ")) is True


class TestIsEmptyAssistant:
    def test_normal_response(self):
        assert is_empty_assistant(_make_entry()) is False

    def test_think_only(self):
        entry = _make_entry(assistant="<think>some reasoning</think>")
        assert is_empty_assistant(entry) is True

    def test_think_with_visible_content(self):
        entry = _make_entry(assistant="<think>reasoning</think>Here is the answer.")
        assert is_empty_assistant(entry) is False

    def test_unclosed_think_only(self):
        entry = _make_entry(assistant="<think>reasoning without close tag")
        assert is_empty_assistant(entry) is True

    def test_whitespace_after_think(self):
        entry = _make_entry(assistant="<think>reasoning</think>   \n\t  ")
        assert is_empty_assistant(entry) is True

    def test_no_assistant_message(self):
        entry = {
            "messages": [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "hi"},
            ]
        }
        assert is_empty_assistant(entry) is False


class TestHasUnclosedThink:
    def test_no_think_block(self):
        assert has_unclosed_think(_make_entry()) is False

    def test_closed_think(self):
        entry = _make_entry(assistant="<think>ok</think>Answer")
        assert has_unclosed_think(entry) is False

    def test_unclosed_think(self):
        entry = _make_entry(assistant="<think>reasoning goes on and on")
        assert has_unclosed_think(entry) is True

    def test_multiple_think_some_unclosed(self):
        entry = _make_entry(
            assistant="<think>a</think>middle<think>b without close"
        )
        assert has_unclosed_think(entry) is True

    def test_case_insensitive(self):
        entry = _make_entry(assistant="<Think>reasoning")
        assert has_unclosed_think(entry) is True


class TestRepairThinkBlocks:
    def test_appends_closing_tag(self):
        entry = _make_entry(assistant="<think>reasoning without end")
        repaired = repair_think_blocks(entry)
        content = repaired["messages"][2]["content"]
        assert content.endswith("</think>")

    def test_no_change_if_closed(self):
        entry = _make_entry(assistant="<think>ok</think>Answer")
        repaired = repair_think_blocks(entry)
        assert repaired["messages"][2]["content"] == "<think>ok</think>Answer"

    def test_does_not_mutate_original(self):
        entry = _make_entry(assistant="<think>reasoning")
        original_content = entry["messages"][2]["content"]
        repair_think_blocks(entry)
        assert entry["messages"][2]["content"] == original_content


class TestCleanTrainingData:
    @pytest.fixture()
    def sample_data(self, tmp_path: Path) -> tuple[Path, Path]:
        input_path = tmp_path / "train.jsonl"
        output_path = tmp_path / "train_cleaned.jsonl"

        entries = [
            _make_entry(),  # line 1: normal
            _make_entry(system="..."),  # line 2: degenerate
            _make_entry(  # line 3: empty assistant
                assistant="<think>reasoning only</think>"
            ),
            _make_entry(  # line 4: unclosed think (repair)
                assistant="<think>ok</think>Answer is here.<think>wait, more thought"
            ),
            _make_entry(  # line 5: normal
                assistant="<think>ok</think>Good answer"
            ),
        ]

        with open(input_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        return input_path, output_path

    def test_counts(self, sample_data: tuple[Path, Path]):
        input_path, output_path = sample_data
        stats = clean_training_data(input_path, output_path)
        assert stats.total == 5
        assert stats.removed_degenerate == 1
        assert stats.removed_empty == 1
        assert stats.repaired_think == 1
        assert stats.unchanged == 2
        assert stats.kept == 3

    def test_output_line_count(self, sample_data: tuple[Path, Path]):
        input_path, output_path = sample_data
        clean_training_data(input_path, output_path)
        with open(output_path) as f:
            lines = [l for l in f.readlines() if l.strip()]
        assert len(lines) == 3

    def test_repaired_entry_has_closing_tag(self, sample_data: tuple[Path, Path]):
        input_path, output_path = sample_data
        clean_training_data(input_path, output_path)
        with open(output_path) as f:
            entries = [json.loads(l) for l in f if l.strip()]
        # The repaired entry (originally line 4) should have </think>
        repaired = [
            e
            for e in entries
            if "<think>" in e["messages"][2]["content"]
            and "Answer is here" in e["messages"][2]["content"]
        ]
        assert len(repaired) == 1
        assert "</think>" in repaired[0]["messages"][2]["content"]

    def test_dry_run_no_output(self, sample_data: tuple[Path, Path]):
        input_path, output_path = sample_data
        stats = clean_training_data(input_path, output_path, dry_run=True)
        assert stats.total == 5
        assert not output_path.exists()

    def test_log_entries(self, sample_data: tuple[Path, Path]):
        input_path, output_path = sample_data
        stats = clean_training_data(input_path, output_path)
        assert len(stats.log_entries) == 3
        defect_types = {e["defect"] for e in stats.log_entries}
        assert defect_types == {
            "degenerate_placeholder",
            "empty_assistant_response",
            "unclosed_think_block",
        }

    def test_original_not_modified(self, sample_data: tuple[Path, Path]):
        input_path, output_path = sample_data
        with open(input_path) as f:
            original = f.read()
        clean_training_data(input_path, output_path)
        with open(input_path) as f:
            after = f.read()
        assert original == after


class TestCleaningStatsKept:
    def test_kept_property(self):
        stats = CleaningStats(total=100, removed_degenerate=3, removed_empty=13)
        assert stats.kept == 84
