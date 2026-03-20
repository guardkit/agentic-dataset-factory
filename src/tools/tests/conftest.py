"""Shared fixtures for tools model tests."""

from __future__ import annotations

import pytest

from tools.models import ExampleMetadata, Message, RagRetrievalParams, TrainingExample


# ---------------------------------------------------------------------------
# Message fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def system_message() -> Message:
    return Message(role="system", content="You are a helpful tutor.")


@pytest.fixture
def user_message() -> Message:
    return Message(role="user", content="Explain Macbeth's ambition.")


@pytest.fixture
def assistant_message() -> Message:
    return Message(role="assistant", content="Macbeth's ambition drives the play...")


@pytest.fixture
def valid_messages(
    system_message: Message,
    user_message: Message,
    assistant_message: Message,
) -> list[Message]:
    return [system_message, user_message, assistant_message]


# ---------------------------------------------------------------------------
# ExampleMetadata fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_metadata_kwargs() -> dict:
    return {
        "layer": "behaviour",
        "type": "reasoning",
        "source": "synthetic",
    }


@pytest.fixture
def valid_metadata(valid_metadata_kwargs: dict) -> ExampleMetadata:
    return ExampleMetadata(**valid_metadata_kwargs)


# ---------------------------------------------------------------------------
# TrainingExample fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_example(
    valid_messages: list[Message],
    valid_metadata: ExampleMetadata,
) -> TrainingExample:
    return TrainingExample(messages=valid_messages, metadata=valid_metadata)


# ---------------------------------------------------------------------------
# RagRetrievalParams fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_rag_kwargs() -> dict:
    return {
        "query": "What is Macbeth's fatal flaw?",
        "n_results": 5,
        "collection_name": "gcse-english-tutor",
    }


@pytest.fixture
def valid_rag_params(valid_rag_kwargs: dict) -> RagRetrievalParams:
    return RagRetrievalParams(**valid_rag_kwargs)
