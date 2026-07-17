"""GOAL.md passes the domain_config parser + all 10 cross-section validators, and carries
the DCL-specific contract (modes, splits, reasoning >= 70%, closed-vocabulary discipline)."""

from __future__ import annotations

from pathlib import Path

import pytest

from domain_config.models import GoalValidationError
from domain_config.parser import parse_goal_md

GOAL = Path(__file__).resolve().parent.parent / "domains" / "dcl-capability-language" / "GOAL.md"


@pytest.fixture(scope="module")
def cfg():
    return parse_goal_md(GOAL)


def test_goal_md_parses(cfg):
    assert cfg.goal
    assert cfg.system_prompt
    assert cfg.output_schema.get("messages") is not None or "messages" in cfg.output_schema


def test_reasoning_split_at_least_70pct(cfg):
    total = sum(t.count for t in cfg.generation_targets)
    reasoning = sum(t.count for t in cfg.generation_targets if t.type == "reasoning")
    assert reasoning / total >= 0.70


def test_targets_are_author_and_repair(cfg):
    types = {t.type for t in cfg.generation_targets}
    assert types == {"direct", "reasoning"}
    assert all(t.layer == "behaviour" for t in cfg.generation_targets)


def test_metadata_valid_values_cover_mode_split_type(cfg):
    by_field = {m.field: m for m in cfg.metadata_schema}
    assert set(by_field["mode"].valid_values) == {"dcl_author", "dcl_repair"}
    assert set(by_field["split"].valid_values) == {"train", "eval_dcl"}
    assert set(by_field["type"].valid_values) == {"direct", "reasoning"}
    assert all(m.required for m in cfg.metadata_schema)


def test_evaluation_criteria_named(cfg):
    names = {c.name for c in cfg.evaluation_criteria}
    assert {"brief_fidelity", "vocabulary_discipline", "fence_integrity", "semantic_preservation"} <= names


def test_layer_routing_behaviour_to_train(cfg):
    assert cfg.layer_routing["behaviour"].endswith("dcl-capability-language/train.jsonl")
    assert "knowledge" in cfg.layer_routing
