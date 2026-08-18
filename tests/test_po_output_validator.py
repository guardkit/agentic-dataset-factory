"""Tests for the product-owner factory acceptance-gate validator
(``domains/product-owner/po_schemas.py:validate_assistant_content``) and its
loop-side hook (``entrypoint.generation_loop._resolve_output_validator`` /
``_run_output_validator`` / ``GenerationConfig.output_validator``).

2026-08-18, Rich's word: the 08-13/14 corpus was only 17% serve-valid because
the factory gate did strict ``json.loads`` only.  The validator runs the
vendored serving Pydantic models on the assistant content, exactly the way
``ProductOwnerOutputHandler.parse`` would see it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

_REPO = Path(__file__).resolve().parents[1]
_PO_DIR = _REPO / "domains" / "product-owner"
if str(_PO_DIR) not in sys.path:
    sys.path.insert(0, str(_PO_DIR))

import po_schemas as ps  # noqa: E402

VALIDATOR_SPEC = "domains/product-owner/po_schemas.py:validate_assistant_content"


# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------


def _feature(desc: str = "A user can reset a lost password. The reset link expires after one hour.",
             fid: str = "FEAT-001", **over: Any) -> dict[str, Any]:
    f = {
        "feature_id": fid,
        "title": "Password reset",
        "description": desc,
        "bounded_context": "Identity",
        "source_documents": ["request:reset a lost password"],
        "constraints": [],
        "suggested_context_files": [],
        "depends_on": [],
    }
    f.update(over)
    return f


def _roadmap(features: list[dict[str, Any]] | None = None, **over: Any) -> dict[str, Any]:
    feats = features if features is not None else [_feature()]
    r = {
        "project_name": "demo",
        "mode": "greenfield",
        "epics": [
            {
                "id": "EPIC-001",
                "name": "Identity",
                "bounded_context": "Identity",
                "description": "Account access.",
                "source_documents": [],
                "features": feats,
            }
        ],
        "feature_spec_inputs": feats,
        "priority_rationale": "Access first; everything else depends on it.",
        "constraints_and_dependencies": [],
        "open_questions": [],
        "coverage_score": None,
        "source_documents": [],
        "assumptions": [],
    }
    r.update(over)
    return r


def _assistant(obj: dict[str, Any], think: str = "Reason about it.") -> str:
    return f"<think>{think}</think>\n\n```json\n{json.dumps(obj, indent=2)}\n```"


def _md(mode: str = "greenfield", **over: Any) -> dict[str, Any]:
    m = {"layer": "behaviour", "type": "reasoning", "mode": mode,
         "topic": "mvp_scoping", "source": "synthetic", "turns": 1}
    m.update(over)
    return m


def _batch() -> dict[str, Any]:
    return {
        "project_name": "demo",
        "epic_id": "EPIC-001",
        "enrichments": [
            {
                "feature_id": "FEAT-001",
                "description": "A user can reset a lost password. The link expires after one hour.",
                "source_documents": ["auth.md"],
                "constraints": [],
                "suggested_context_files": [],
                "depends_on": [],
            }
        ],
    }


# ---------------------------------------------------------------------------
# validate_assistant_content
# ---------------------------------------------------------------------------


class TestValidateAssistantContent:
    def test_real_passing_roadmap_shape_passes(self) -> None:
        ok, text = ps.validate_assistant_content(_assistant(_roadmap()), _md())
        assert ok is True, text
        assert text == "ok"

    def test_single_sentence_description_fails_with_serving_text(self) -> None:
        row = _roadmap([_feature("A user can reset a lost password.")])
        ok, text = ps.validate_assistant_content(_assistant(row), _md())
        assert ok is False
        assert "JSON parsed but failed ProductRoadmap validation" in text
        assert (
            "FeatureSpecInput.description must contain at least 2 sentences, got 1"
            in text
        )

    def test_empty_feature_epic_fails(self) -> None:
        row = _roadmap()
        row["epics"][0]["features"] = []
        ok, text = ps.validate_assistant_content(_assistant(row), _md("evolve"))
        assert ok is False
        assert "Each epic must have at least 1 feature" in text

    def test_str_list_field_fails(self) -> None:
        row = _roadmap(constraints_and_dependencies="none")
        ok, text = ps.validate_assistant_content(_assistant(row), _md("scope"))
        assert ok is False
        assert "constraints_and_dependencies" in text

    def test_fenced_phase_b_batch_passes(self) -> None:
        content = _assistant(_batch())
        ok, text = ps.validate_assistant_content(
            content, _md("extract", phase="b", source="harvest")
        )
        assert ok is True, text

    def test_bare_phase_b_batch_passes(self) -> None:
        content = "<think>x</think>\n" + json.dumps(_batch())
        ok, _ = ps.validate_assistant_content(
            content, _md("extract", phase="b", source="harvest")
        )
        assert ok is True

    def test_phase_b_empty_enrichments_fails(self) -> None:
        b = _batch()
        b["enrichments"] = []
        ok, text = ps.validate_assistant_content(
            _assistant(b), _md("extract", phase="b")
        )
        assert ok is False
        assert "EnrichmentBatch" in text

    def test_phase_a_epic_plan_selected(self) -> None:
        plan = {
            "project_name": "demo",
            "mode": "extract",
            "epics": [
                {
                    "epic_id": "EPIC-001",
                    "name": "Identity",
                    "bounded_context": "Identity",
                    "cited_docs": ["auth.md"],
                    "feature_stubs": [
                        {"feature_id": "FEAT-001", "title": "Reset", "intent": "Reset a password."}
                    ],
                }
            ],
            "open_questions": [],
            "priority_rationale": "Access first.",
            "constraints_and_dependencies": [],
        }
        ok, text = ps.validate_assistant_content(
            _assistant(plan), _md("extract", phase="a")
        )
        assert ok is True, text
        # The same object is NOT a ProductRoadmap (single-pass extract).
        ok2, text2 = ps.validate_assistant_content(
            _assistant(plan), _md("extract", phase="full")
        )
        assert ok2 is False
        assert "ProductRoadmap" in text2

    def test_schema_for_mapping(self) -> None:
        assert ps.schema_for({"mode": "extract", "phase": "a"}) is ps.EpicPlan
        assert ps.schema_for({"mode": "extract", "phase": "b"}) is ps.EnrichmentBatch
        assert ps.schema_for({"mode": "extract", "phase": "full"}) is ps.ProductRoadmap
        assert ps.schema_for({"mode": "extract"}) is ps.ProductRoadmap
        for m in ("idea", "greenfield", "evolve", "impact", "scope"):
            assert ps.schema_for({"mode": m}) is ps.ProductRoadmap
        assert ps.schema_for({"layer": "knowledge", "mode": "idea"}) is None
        assert ps.schema_for(None) is ps.ProductRoadmap

    def test_knowledge_layer_is_not_gated(self) -> None:
        ok, text = ps.validate_assistant_content(
            "<think>x</think>\nINVEST stands for ...", _md(layer="knowledge")
        )
        assert ok is True
        assert "knowledge layer" in text

    def test_literal_fence_inside_string_fails_like_serving(self) -> None:
        # A ``` inside a JSON string closes serving's non-greedy fence early.
        row = _roadmap()
        row["priority_rationale"] = "See ``` block below"
        ok, text = ps.validate_assistant_content(_assistant(row), _md())
        assert ok is False
        assert "Found code block but content is not valid JSON" in text

    def test_missing_project_name_is_defaulted_like_serving(self) -> None:
        row = _roadmap()
        del row["project_name"]
        ok, _ = ps.validate_assistant_content(_assistant(row), _md())
        assert ok is True

    def test_no_json_at_all_fails(self) -> None:
        ok, text = ps.validate_assistant_content("<think>x</think>\nJust prose.", _md())
        assert ok is False
        assert "No valid JSON found in Player output" in text

    def test_empty_content_fails(self) -> None:
        ok, text = ps.validate_assistant_content("<think>only thinking</think>", _md())
        assert ok is False
        assert "empty" in text.lower()

    def test_serving_fence_regex_is_the_pinned_one(self) -> None:
        # handler.py:670 @ specialist-agent c765c04
        assert ps._SERVING_FENCE_PATTERN == r"```(?:json)?\s*\n?(.*?)\n?\s*```"

    def test_error_text_is_capped(self) -> None:
        feats = [_feature("One sentence only.", fid=f"FEAT-{i:03d}") for i in range(60)]
        ok, text = ps.validate_assistant_content(_assistant(_roadmap(feats)), _md())
        assert ok is False
        assert len(text) <= ps._ERROR_TEXT_CAP


# ---------------------------------------------------------------------------
# Loop-side hook: config + resolver + runner
# ---------------------------------------------------------------------------


class TestGenerationConfigOutputValidator:
    def test_default_is_none(self) -> None:
        from config.models import GenerationConfig

        assert GenerationConfig().output_validator is None

    def test_spec_accepted(self) -> None:
        from config.models import GenerationConfig

        assert GenerationConfig(output_validator=VALIDATOR_SPEC).output_validator == VALIDATOR_SPEC

    @pytest.mark.parametrize("bad", ["no_colon_here", ":fn", "mod.py:", "   "])
    def test_bad_shape_rejected_or_blanked(self, bad: str) -> None:
        from config.models import GenerationConfig

        if bad.strip() == "":
            assert GenerationConfig(output_validator=bad).output_validator is None
        else:
            with pytest.raises(ValueError):
                GenerationConfig(output_validator=bad)


class TestResolveOutputValidator:
    def test_none_resolves_to_none(self) -> None:
        from entrypoint.generation_loop import _resolve_output_validator

        assert _resolve_output_validator(None) is None
        assert _resolve_output_validator("") is None

    def test_file_spec_resolves_and_caches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from entrypoint.generation_loop import _resolve_output_validator

        monkeypatch.chdir(_REPO)
        fn = _resolve_output_validator(VALIDATOR_SPEC)
        assert callable(fn)
        assert _resolve_output_validator(VALIDATOR_SPEC) is fn
        ok, _ = fn(_assistant(_roadmap()), _md())
        assert ok is True

    def test_dotted_spec_resolves(self) -> None:
        from entrypoint.generation_loop import _resolve_output_validator

        fn = _resolve_output_validator("json:loads")
        assert fn is json.loads

    def test_missing_module_is_loud(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from entrypoint.generation_loop import _resolve_output_validator

        monkeypatch.chdir(_REPO)
        with pytest.raises(ValueError, match="not found"):
            _resolve_output_validator("domains/nope/none.py:fn")

    def test_missing_attribute_is_loud(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from entrypoint.generation_loop import _resolve_output_validator

        monkeypatch.chdir(_REPO)
        with pytest.raises(ValueError, match="not a callable"):
            _resolve_output_validator("domains/product-owner/po_schemas.py:no_such_fn")


class TestRunOutputValidator:
    def _data(self, content: str, md: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "messages": [
                {"role": "system", "content": "s"},
                {"role": "user", "content": "u"},
                {"role": "assistant", "content": content},
            ],
            "metadata": md if md is not None else _md(),
        }

    def test_passes_last_assistant_content_and_metadata(self) -> None:
        from entrypoint.generation_loop import _run_output_validator

        seen: dict[str, Any] = {}

        def v(content: str, metadata: dict[str, Any]) -> tuple[bool, str]:
            seen["content"] = content
            seen["metadata"] = metadata
            return True, "ok"

        data = self._data("<think>t</think>\n```json\n{}\n```", _md("idea"))
        # a multi-turn row: the LAST assistant message is the one validated
        data["messages"] += [{"role": "user", "content": "again"},
                             {"role": "assistant", "content": "LAST"}]
        assert _run_output_validator(v, data) == (True, "ok")
        assert seen["content"] == "LAST"
        assert seen["metadata"]["mode"] == "idea"

    def test_validator_exception_is_a_failure_not_a_crash(self) -> None:
        from entrypoint.generation_loop import _run_output_validator

        def boom(content: str, metadata: dict[str, Any]) -> tuple[bool, str]:
            raise RuntimeError("kaboom")

        ok, reason = _run_output_validator(boom, self._data("x"))
        assert ok is False
        assert "kaboom" in reason

    def test_no_assistant_message(self) -> None:
        from entrypoint.generation_loop import _run_output_validator

        ok, reason = _run_output_validator(lambda c, m: (True, "ok"),
                                           {"messages": [{"role": "user", "content": "u"}]})
        assert ok is False
        assert "no assistant message" in reason


# ---------------------------------------------------------------------------
# Loop-level: the rejection path receives the validator's error text
# ---------------------------------------------------------------------------


def _accept_verdict_json() -> str:
    from config.coach_verdict import CoachVerdict

    return CoachVerdict(
        decision="accept", score=4, layer_correct=True, type_correct=True,
        criteria_met={"accuracy": True}, issues=[], quality_assessment="Good",
    ).model_dump_json()


def _outer_example(assistant_content: str, md: dict[str, Any]) -> str:
    return json.dumps({
        "messages": [
            {"role": "system", "content": "You are the PO."},
            {"role": "user", "content": "Brief: reset a lost password."},
            {"role": "assistant", "content": assistant_content},
        ],
        "metadata": md,
    })


def _run_loop(player_contents: list[str], **cfg: Any) -> tuple[Any, list[str], MagicMock]:
    from config.models import GenerationConfig
    from domain_config.models import GenerationTarget
    from entrypoint.generation_loop import run_generation_loop
    import asyncio

    config = GenerationConfig(
        max_turns=3, llm_retry_attempts=1, llm_retry_backoff=0.0,
        llm_timeout=30, target_timeout=60, max_format_retries=1, **cfg,
    )
    player = AsyncMock()
    player.ainvoke.side_effect = [
        {"messages": [MagicMock(content=c)]} for c in player_contents
    ]
    coach = AsyncMock()
    coach.ainvoke.return_value = {"messages": [MagicMock(content=_accept_verdict_json())]}
    output_mgr = MagicMock()
    rejected: list[str] = []
    output_mgr.rejected_fh = MagicMock()
    output_mgr.rejected_fh.write = MagicMock(side_effect=lambda s: rejected.append(s))
    write_tool = MagicMock()
    write_tool.invoke.return_value = "Written to output/train.jsonl (example #1)"

    result = asyncio.run(run_generation_loop(
        player=player, coach=coach,
        targets=[GenerationTarget(category="Scope", type="reasoning", count=1)],
        config=config, checkpoint=MagicMock(), output_manager=output_mgr,
        write_tool=write_tool, start_index=0,
    ))
    return result, rejected, write_tool


class TestLoopHook:
    def test_inert_without_validator_invalid_row_is_written(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Byte-compatible: with no validator the one-sentence row sails through."""
        monkeypatch.chdir(_REPO)
        bad = _assistant(_roadmap([_feature("A user can reset a lost password.")]))
        result, rejected, write_tool = _run_loop(
            [_outer_example(bad, _md())], require_fenced_json=True,
        )
        assert result.accepted == 1
        assert write_tool.invoke.call_count == 1
        assert rejected == []

    def test_validator_rejects_with_error_text_in_rejection_reason(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(_REPO)
        bad = _assistant(_roadmap([_feature("A user can reset a lost password.")]))
        result, rejected, write_tool = _run_loop(
            [_outer_example(bad, _md())] * 3,
            require_fenced_json=True, output_validator=VALIDATOR_SPEC,
        )
        assert result.accepted == 0
        assert result.rejected == 1
        assert write_tool.invoke.call_count == 0
        record = json.loads(rejected[0])
        gates = [h for h in record["rejection_history"] if h.get("format_gate")]
        assert gates, record
        assert gates[0]["format_gate"] == "assistant_output_invalid"
        assert "at least 2 sentences" in gates[0]["reason"]

    def test_validator_error_text_reaches_the_player_next_turn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The Player's second turn is asked to fix the reported fields; a
        corrected row is then accepted and written."""

        monkeypatch.chdir(_REPO)
        bad = _assistant(_roadmap([_feature("A user can reset a lost password.")]))
        good = _assistant(_roadmap())
        result, rejected, write_tool = _run_loop(
            [_outer_example(bad, _md()), _outer_example(good, _md())],
            output_validator=VALIDATOR_SPEC,
        )
        assert result.accepted == 1
        assert write_tool.invoke.call_count == 1
        assert rejected == []

    def test_bad_validator_spec_fails_loud_at_run_start(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(_REPO)
        with pytest.raises(ValueError, match="output_validator"):
            _run_loop([_outer_example(_assistant(_roadmap()), _md())],
                      output_validator="domains/product-owner/po_schemas.py:missing_fn")
