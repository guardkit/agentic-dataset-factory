"""Tests for the synthesis orchestrator."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import anthropic
import pytest
import yaml

from synthesis.synthesise import (
    _ensure_output_dirs,
    _resolve_route,
    _write_rejected,
    call_claude,
    extract_json,
    load_checkpoint,
    load_plan,
    run,
    save_checkpoint,
)
from synthesis.validator import (
    GenerationPlan,
    GenerationTarget,
    ValidationResult,
)


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

VALID_REASONING_JSON = json.dumps(
    {
        "messages": [
            {"role": "system", "content": "You are a tutor."},
            {"role": "user", "content": "Explain Macbeth."},
            {
                "role": "assistant",
                "content": "<think>\nReasoning here.\n</think>\n\nMacbeth is a tragedy.",
            },
        ],
        "metadata": {
            "layer": "behaviour",
            "type": "reasoning",
            "ao": ["AO1"],
            "text": "macbeth",
            "topic": "character_analysis",
            "grade_target": 7,
            "source": "synthetic",
            "turns": 1,
        },
    }
)

VALID_DIRECT_JSON = json.dumps(
    {
        "messages": [
            {"role": "system", "content": "You are a tutor."},
            {"role": "user", "content": "What is a simile?"},
            {"role": "assistant", "content": "A simile compares two things using 'like' or 'as'."},
        ],
        "metadata": {
            "layer": "knowledge",
            "type": "direct",
            "ao": [],
            "text": "general",
            "topic": "terminology",
            "grade_target": None,
            "source": "synthetic",
            "turns": 1,
        },
    }
)

MINIMAL_TARGET = {
    "text": "macbeth",
    "topic": "character_analysis",
    "grade_target": 7,
    "layer": "behaviour",
    "type": "reasoning",
    "ao": ["AO1"],
    "turns": 1,
}

DIRECT_TARGET = {
    "text": "general",
    "topic": "terminology",
    "grade_target": None,
    "layer": "knowledge",
    "type": "direct",
    "ao": [],
    "turns": 1,
}


def _make_plan_yaml(targets: list[dict]) -> dict:
    return {"generation_targets": targets}


def _make_mock_client(response_text: str) -> MagicMock:
    """Build a mock Anthropic client returning *response_text*."""
    mock_content = MagicMock()
    mock_content.text = response_text
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    mock_client = MagicMock(spec=anthropic.Anthropic)
    mock_client.messages.create.return_value = mock_response
    return mock_client


# ---------------------------------------------------------------------------
# extract_json
# ---------------------------------------------------------------------------


class TestExtractJson:
    def test_plain_json_object(self):
        text = '{"key": "value"}'
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_json_with_preamble(self):
        text = 'Here is the JSON:\n{"key": "value"}'
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_json_in_markdown_fence(self):
        text = "```json\n{\"key\": \"value\"}\n```"
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_json_in_plain_fence(self):
        text = "```\n{\"key\": \"value\"}\n```"
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_returns_none_for_no_json(self):
        result = extract_json("No JSON here at all.")
        assert result is None

    def test_returns_none_for_malformed_json(self):
        result = extract_json("{bad json}")
        assert result is None

    def test_nested_json(self):
        text = '{"messages": [{"role": "system", "content": "hi"}]}'
        result = extract_json(text)
        assert result["messages"][0]["role"] == "system"


# ---------------------------------------------------------------------------
# load_plan
# ---------------------------------------------------------------------------


class TestLoadPlan:
    def test_valid_plan_loaded(self, tmp_path):
        plan_file = tmp_path / "plan.yaml"
        plan_file.write_text(yaml.dump(_make_plan_yaml([MINIMAL_TARGET])))
        plan = load_plan(plan_file)
        assert isinstance(plan, GenerationPlan)
        assert len(plan.generation_targets) == 1

    def test_empty_targets_list(self, tmp_path):
        plan_file = tmp_path / "plan.yaml"
        plan_file.write_text(yaml.dump(_make_plan_yaml([])))
        plan = load_plan(plan_file)
        assert plan.generation_targets == []

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_plan(tmp_path / "nonexistent.yaml")

    def test_invalid_yaml_raises(self, tmp_path):
        plan_file = tmp_path / "plan.yaml"
        plan_file.write_text(":\n  - invalid: [yaml")
        with pytest.raises(yaml.YAMLError):
            load_plan(plan_file)

    def test_invalid_schema_raises(self, tmp_path):
        plan_file = tmp_path / "plan.yaml"
        plan_file.write_text(yaml.dump({"wrong_key": []}))
        with pytest.raises(Exception):
            load_plan(plan_file)


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------


class TestCheckpoint:
    def test_defaults_when_no_checkpoint(self, tmp_path):
        cp = load_checkpoint(tmp_path)
        assert cp == {"last_completed_index": -1, "accepted": 0, "rejected": 0}

    def test_save_and_load_checkpoint(self, tmp_path):
        save_checkpoint(tmp_path, 42, 35, 7)
        cp = load_checkpoint(tmp_path)
        assert cp == {"last_completed_index": 42, "accepted": 35, "rejected": 7}

    def test_checkpoint_overwrites_previous(self, tmp_path):
        save_checkpoint(tmp_path, 10, 8, 2)
        save_checkpoint(tmp_path, 20, 16, 4)
        cp = load_checkpoint(tmp_path)
        assert cp["last_completed_index"] == 20


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


class TestEnsureOutputDirs:
    def test_creates_output_and_rag_index(self, tmp_path):
        output_dir = tmp_path / "output"
        _ensure_output_dirs(output_dir)
        assert output_dir.exists()
        assert (output_dir / "rag_index").exists()

    def test_idempotent_when_dirs_exist(self, tmp_path):
        output_dir = tmp_path / "output"
        _ensure_output_dirs(output_dir)
        _ensure_output_dirs(output_dir)  # Should not raise
        assert output_dir.exists()


class TestResolveRoute:
    def test_behaviour_route(self, tmp_path):
        route = _resolve_route("output/train.jsonl", tmp_path)
        assert route == tmp_path / "train.jsonl"

    def test_knowledge_route(self, tmp_path):
        route = _resolve_route("output/rag_index/knowledge.jsonl", tmp_path)
        assert route == tmp_path / "rag_index" / "knowledge.jsonl"

    def test_none_route_defaults_to_train(self, tmp_path):
        route = _resolve_route(None, tmp_path)
        assert route == tmp_path / "train.jsonl"


class TestWriteRejected:
    def test_creates_rejected_jsonl(self, tmp_path):
        target = GenerationTarget(**MINIMAL_TARGET)
        _write_rejected(tmp_path, target, "malformed_content", '{"bad": "json"}')
        rejected_file = tmp_path / "rejected.jsonl"
        assert rejected_file.exists()
        record = json.loads(rejected_file.read_text().strip())
        assert record["reason"] == "malformed_content"

    def test_appends_multiple_rejections(self, tmp_path):
        target = GenerationTarget(**MINIMAL_TARGET)
        _write_rejected(tmp_path, target, "api_error")
        _write_rejected(tmp_path, target, "malformed_content")
        lines = (tmp_path / "rejected.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2

    def test_null_raw_response_allowed(self, tmp_path):
        target = GenerationTarget(**MINIMAL_TARGET)
        _write_rejected(tmp_path, target, "api_error", None)
        record = json.loads((tmp_path / "rejected.jsonl").read_text().strip())
        assert record["raw_response"] is None


# ---------------------------------------------------------------------------
# call_claude
# ---------------------------------------------------------------------------


class TestCallClaude:
    def test_returns_text_on_success(self):
        mock_client = _make_mock_client("response text")
        result = call_claude(mock_client, "system", "user")
        assert result == "response text"

    def test_passes_correct_model_and_messages(self):
        mock_client = _make_mock_client("ok")
        call_claude(mock_client, "sys prompt", "user prompt")
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "claude-sonnet-4-5-20250514"
        assert call_kwargs.kwargs["system"] == "sys prompt"
        assert call_kwargs.kwargs["messages"][0]["content"] == "user prompt"

    def test_retries_on_rate_limit(self):
        mock_content = MagicMock()
        mock_content.text = "success"
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_client = MagicMock(spec=anthropic.Anthropic)
        mock_client.messages.create.side_effect = [
            anthropic.RateLimitError.__new__(anthropic.RateLimitError),
            mock_response,
        ]

        with patch("synthesis.synthesise.time.sleep") as mock_sleep:
            # Need to give RateLimitError a response attr
            rate_err = anthropic.RateLimitError(
                message="rate limit",
                response=MagicMock(status_code=429),
                body={},
            )
            mock_client.messages.create.side_effect = [rate_err, mock_response]
            result = call_claude(mock_client, "sys", "user")

        assert result == "success"
        assert mock_client.messages.create.call_count == 2
        mock_sleep.assert_called_once_with(1)

    def test_raises_after_max_retries(self):
        rate_err = anthropic.RateLimitError(
            message="rate limit",
            response=MagicMock(status_code=429),
            body={},
        )
        mock_client = MagicMock(spec=anthropic.Anthropic)
        mock_client.messages.create.side_effect = rate_err

        with patch("synthesis.synthesise.time.sleep"):
            with pytest.raises(anthropic.RateLimitError):
                call_claude(mock_client, "sys", "user")

        assert mock_client.messages.create.call_count == 3


# ---------------------------------------------------------------------------
# run() — orchestration integration tests
# ---------------------------------------------------------------------------


class TestRun:
    def _write_plan(self, tmp_path: Path, targets: list[dict]) -> Path:
        plan_file = tmp_path / "plan.yaml"
        plan_file.write_text(yaml.dump(_make_plan_yaml(targets)))
        return plan_file

    def test_zero_targets_exits_cleanly(self, tmp_path):
        plan_file = self._write_plan(tmp_path, [])
        output_dir = tmp_path / "output"
        run(plan_file, output_dir, client=MagicMock())
        # No output directory created for zero targets
        assert not (output_dir / "train.jsonl").exists()

    def test_single_target_accepted(self, tmp_path):
        plan_file = self._write_plan(tmp_path, [MINIMAL_TARGET])
        output_dir = tmp_path / "output"
        mock_client = _make_mock_client(VALID_REASONING_JSON)
        run(plan_file, output_dir, client=mock_client)
        assert (output_dir / "train.jsonl").exists()
        record = json.loads((output_dir / "train.jsonl").read_text().strip())
        assert "messages" in record

    def test_direct_example_routed_to_knowledge(self, tmp_path):
        plan_file = self._write_plan(tmp_path, [DIRECT_TARGET])
        output_dir = tmp_path / "output"
        mock_client = _make_mock_client(VALID_DIRECT_JSON)
        run(plan_file, output_dir, client=mock_client)
        assert (output_dir / "rag_index" / "knowledge.jsonl").exists()

    def test_api_error_writes_to_rejected(self, tmp_path):
        plan_file = self._write_plan(tmp_path, [MINIMAL_TARGET])
        output_dir = tmp_path / "output"
        mock_client = MagicMock(spec=anthropic.Anthropic)
        mock_client.messages.create.side_effect = anthropic.APIStatusError(
            message="server error",
            response=MagicMock(status_code=500),
            body={},
        )
        run(plan_file, output_dir, client=mock_client)
        assert (output_dir / "rejected.jsonl").exists()
        record = json.loads((output_dir / "rejected.jsonl").read_text().strip())
        assert record["reason"] == "api_error"

    def test_malformed_json_writes_to_rejected(self, tmp_path):
        plan_file = self._write_plan(tmp_path, [MINIMAL_TARGET])
        output_dir = tmp_path / "output"
        mock_client = _make_mock_client("This is not JSON at all.")
        run(plan_file, output_dir, client=mock_client)
        assert (output_dir / "rejected.jsonl").exists()
        record = json.loads((output_dir / "rejected.jsonl").read_text().strip())
        assert record["reason"] == "malformed_content"

    def test_invalid_example_writes_to_rejected(self, tmp_path):
        """A response with valid JSON but invalid TrainingExample schema."""
        plan_file = self._write_plan(tmp_path, [MINIMAL_TARGET])
        output_dir = tmp_path / "output"
        bad_json = json.dumps({"messages": [], "metadata": {}})
        mock_client = _make_mock_client(bad_json)
        run(plan_file, output_dir, client=mock_client)
        assert (output_dir / "rejected.jsonl").exists()

    def test_checkpoint_updated_after_each_target(self, tmp_path):
        targets = [MINIMAL_TARGET, DIRECT_TARGET]
        plan_file = self._write_plan(tmp_path, targets)
        output_dir = tmp_path / "output"

        responses = [VALID_REASONING_JSON, VALID_DIRECT_JSON]
        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            text = responses[call_count]
            call_count += 1
            mock_content = MagicMock()
            mock_content.text = text
            mock_response = MagicMock()
            mock_response.content = [mock_content]
            return mock_response

        mock_client = MagicMock(spec=anthropic.Anthropic)
        mock_client.messages.create.side_effect = side_effect
        run(plan_file, output_dir, client=mock_client)

        cp = load_checkpoint(output_dir)
        assert cp["last_completed_index"] == 1
        assert cp["accepted"] == 2

    def test_resumption_skips_processed_targets(self, tmp_path):
        """If checkpoint says index 0 done, only index 1 is processed."""
        targets = [MINIMAL_TARGET, DIRECT_TARGET]
        plan_file = self._write_plan(tmp_path, targets)
        output_dir = tmp_path / "output"
        _ensure_output_dirs(output_dir)
        # Pre-set checkpoint: index 0 already done
        save_checkpoint(output_dir, 0, 1, 0)

        mock_client = _make_mock_client(VALID_DIRECT_JSON)
        run(plan_file, output_dir, client=mock_client)

        # API called only once (for index 1)
        assert mock_client.messages.create.call_count == 1

    def test_output_directories_created_if_missing(self, tmp_path):
        plan_file = self._write_plan(tmp_path, [MINIMAL_TARGET])
        output_dir = tmp_path / "deeply" / "nested" / "output"
        mock_client = _make_mock_client(VALID_REASONING_JSON)
        run(plan_file, output_dir, client=mock_client)
        assert output_dir.exists()
        assert (output_dir / "rag_index").exists()

    def test_null_grade_target_passes_through(self, tmp_path):
        target = {**MINIMAL_TARGET, "grade_target": None}
        plan_file = self._write_plan(tmp_path, [target])
        output_dir = tmp_path / "output"
        mock_client = _make_mock_client(VALID_REASONING_JSON)
        run(plan_file, output_dir, client=mock_client)
        assert (output_dir / "train.jsonl").exists()

    def test_rate_limit_retry_calls_sleep(self, tmp_path):
        plan_file = self._write_plan(tmp_path, [MINIMAL_TARGET])
        output_dir = tmp_path / "output"

        mock_content = MagicMock()
        mock_content.text = VALID_REASONING_JSON
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        rate_err = anthropic.RateLimitError(
            message="rate limit",
            response=MagicMock(status_code=429),
            body={},
        )
        mock_client = MagicMock(spec=anthropic.Anthropic)
        mock_client.messages.create.side_effect = [rate_err, mock_response]

        with patch("synthesis.synthesise.time.sleep") as mock_sleep:
            run(plan_file, output_dir, client=mock_client)

        mock_sleep.assert_called_once_with(1)
        assert (output_dir / "train.jsonl").exists()

    def test_rate_limit_exhausted_writes_rejected(self, tmp_path):
        plan_file = self._write_plan(tmp_path, [MINIMAL_TARGET])
        output_dir = tmp_path / "output"

        rate_err = anthropic.RateLimitError(
            message="rate limit",
            response=MagicMock(status_code=429),
            body={},
        )
        mock_client = MagicMock(spec=anthropic.Anthropic)
        mock_client.messages.create.side_effect = rate_err

        with patch("synthesis.synthesise.time.sleep"):
            run(plan_file, output_dir, client=mock_client)

        assert (output_dir / "rejected.jsonl").exists()
        record = json.loads((output_dir / "rejected.jsonl").read_text().strip())
        assert record["reason"] == "api_error"

    def test_reasoning_missing_think_block_rejected(self, tmp_path):
        """Reasoning example without <think> block should be rejected."""
        plan_file = self._write_plan(tmp_path, [MINIMAL_TARGET])
        output_dir = tmp_path / "output"
        bad_example = json.dumps(
            {
                "messages": [
                    {"role": "system", "content": "You are a tutor."},
                    {"role": "user", "content": "Explain Macbeth."},
                    {"role": "assistant", "content": "Macbeth is a tragedy."},  # no <think>
                ],
                "metadata": {
                    "layer": "behaviour",
                    "type": "reasoning",
                    "ao": ["AO1"],
                    "text": "macbeth",
                    "topic": "character_analysis",
                    "grade_target": 7,
                    "source": "synthetic",
                    "turns": 1,
                },
            }
        )
        mock_client = _make_mock_client(bad_example)
        run(plan_file, output_dir, client=mock_client)
        assert (output_dir / "rejected.jsonl").exists()
        record = json.loads((output_dir / "rejected.jsonl").read_text().strip())
        assert "think" in record["reason"]

    def test_multiple_targets_all_accepted(self, tmp_path):
        """Two distinct reasoning targets produce two lines in train.jsonl."""
        targets = [MINIMAL_TARGET, MINIMAL_TARGET]
        plan_file = self._write_plan(tmp_path, targets)
        output_dir = tmp_path / "output"

        # Return different content each call so duplicate detector doesn't reject
        response_a = json.dumps(
            {
                "messages": [
                    {"role": "system", "content": "You are a tutor."},
                    {"role": "user", "content": "Explain Macbeth themes."},
                    {
                        "role": "assistant",
                        "content": "<think>\nTheme reasoning A.\n</think>\n\nResponse A.",
                    },
                ],
                "metadata": {
                    "layer": "behaviour",
                    "type": "reasoning",
                    "ao": ["AO1"],
                    "text": "macbeth",
                    "topic": "character_analysis",
                    "grade_target": 7,
                    "source": "synthetic",
                    "turns": 1,
                },
            }
        )
        response_b = json.dumps(
            {
                "messages": [
                    {"role": "system", "content": "You are a tutor."},
                    {"role": "user", "content": "Explain Macbeth symbols."},
                    {
                        "role": "assistant",
                        "content": "<think>\nSymbol reasoning B.\n</think>\n\nResponse B.",
                    },
                ],
                "metadata": {
                    "layer": "behaviour",
                    "type": "reasoning",
                    "ao": ["AO1"],
                    "text": "macbeth",
                    "topic": "character_analysis",
                    "grade_target": 7,
                    "source": "synthetic",
                    "turns": 1,
                },
            }
        )
        responses = [response_a, response_b]
        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            text = responses[call_count]
            call_count += 1
            mock_content = MagicMock()
            mock_content.text = text
            mock_response = MagicMock()
            mock_response.content = [mock_content]
            return mock_response

        mock_client = MagicMock(spec=anthropic.Anthropic)
        mock_client.messages.create.side_effect = side_effect

        run(plan_file, output_dir, client=mock_client)

        lines = (output_dir / "train.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2

    def test_api_key_not_in_logs(self, tmp_path, caplog):
        """API key must never appear in log output."""
        import os

        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-secret-key-12345"
        plan_file = self._write_plan(tmp_path, [MINIMAL_TARGET])
        output_dir = tmp_path / "output"
        mock_client = _make_mock_client(VALID_REASONING_JSON)

        with caplog.at_level(logging.INFO):
            run(plan_file, output_dir, client=mock_client)

        for record in caplog.records:
            assert "sk-ant-test-secret-key-12345" not in record.getMessage()

        # Clean up
        os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_jsonl_output_valid_after_write(self, tmp_path):
        """Each line in output must be valid JSON (crash-safe JSONL)."""
        targets = [MINIMAL_TARGET, MINIMAL_TARGET]
        plan_file = self._write_plan(tmp_path, targets)
        output_dir = tmp_path / "output"
        mock_client = _make_mock_client(VALID_REASONING_JSON)
        run(plan_file, output_dir, client=mock_client)

        for line in (output_dir / "train.jsonl").read_text().strip().splitlines():
            parsed = json.loads(line)
            assert "messages" in parsed


# ---------------------------------------------------------------------------
# Seam tests: integration contracts with producer tasks
# ---------------------------------------------------------------------------


@pytest.mark.seam
@pytest.mark.integration_contract("VALIDATION_API")
def test_validation_api_contract():
    """Verify validate_example returns expected ValidationResult shape.

    Contract: validate_example returns ValidationResult with is_valid, reason, route fields
    Producer: TASK-GTS-003
    """
    from synthesis.validator import (
        validate_example,
    )

    assert callable(validate_example)
    # ValidationResult is a dataclass — check __dataclass_fields__ for field presence
    fields = ValidationResult.__dataclass_fields__
    assert "is_valid" in fields
    assert "reason" in fields
    assert "route" in fields


@pytest.mark.seam
@pytest.mark.integration_contract("TEMPLATE_API")
def test_template_api_contract():
    """Verify select_template returns callable that produces PromptPair.

    Contract: select_template returns callable taking GenerationTarget, returning PromptPair
    Producer: TASK-GTS-004
    """
    from synthesis.templates import PromptPair, select_template

    assert callable(select_template)
    # PromptPair is a dataclass — check __dataclass_fields__ for field presence
    fields = PromptPair.__dataclass_fields__
    assert "system_prompt" in fields
    assert "user_prompt" in fields
