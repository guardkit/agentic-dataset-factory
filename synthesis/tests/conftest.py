"""Shared fixtures for synthesis tests."""

import pytest


@pytest.fixture()
def sample_generation_plan():
    """A sample generation plan: list of target dicts as loaded from generation-plan.yaml."""
    return [
        {
            "topic": "Macbeth Act 1 themes",
            "style": "reasoning",
            "turns": "single",
            "layer": "behaviour",
        },
        {
            "topic": "Persuasive writing techniques",
            "style": "direct",
            "turns": "multi",
            "layer": "behaviour",
        },
        {
            "topic": "Romeo and Juliet key quotes",
            "style": "reasoning",
            "turns": "single",
            "layer": "knowledge",
        },
    ]


@pytest.fixture()
def sample_valid_example():
    """A sample valid training example in ShareGPT format with metadata."""
    return {
        "conversations": [
            {"from": "human", "value": "Explain the theme of ambition in Macbeth Act 1."},
            {
                "from": "gpt",
                "value": (
                    "In Act 1, ambition is introduced as a corrupting force. "
                    "Macbeth's encounter with the witches plants the seed of ambition..."
                ),
            },
        ],
        "metadata": {
            "topic": "Macbeth Act 1 themes",
            "style": "reasoning",
            "turns": "single",
            "layer": "behaviour",
            "model": "claude-sonnet-4-5",
        },
    }


@pytest.fixture()
def sample_invalid_example():
    """A sample invalid training example — missing required conversations field."""
    return {
        "metadata": {
            "topic": "Macbeth Act 1 themes",
            "style": "reasoning",
        },
    }
