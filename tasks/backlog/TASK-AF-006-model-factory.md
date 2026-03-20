---
id: TASK-AF-006
title: "Create shared model factory"
task_type: feature
parent_review: TASK-REV-DAA1
feature_id: FEAT-AF
wave: 1
implementation_mode: task-work
complexity: 3
dependencies:
  - TASK-AF-001
status: pending
tags: [model-factory, langchain, init-chat-model, DRY]
consumer_context:
  - task: TASK-AF-001
    consumes: ModelConfig
    framework: "LangChain init_chat_model"
    driver: "langchain"
    format_note: "ModelConfig fields (provider, model, endpoint, temperature) must be translated to init_chat_model parameters"
---

# Task: Create shared model factory

## Description

Create `agents/model_factory.py` with a `create_model(config: ModelConfig) -> BaseChatModel` function that translates `ModelConfig` into a concrete LangChain chat model. This shared module prevents duplication between Player and Coach factories (DRY principle).

## Requirements

- Translate `ModelConfig.provider` to appropriate LangChain model class or `init_chat_model` call
- Handle `local` provider with custom endpoint
- Handle `anthropic` and `openai` providers with default endpoints
- Pass `temperature` through to model configuration

## Acceptance Criteria

- [ ] `agents/model_factory.py` contains `create_model(config: ModelConfig) -> BaseChatModel`
- [ ] Local provider creates model with custom endpoint URL
- [ ] Anthropic provider creates model using default Anthropic API
- [ ] OpenAI provider creates model using default OpenAI API
- [ ] Temperature is passed through to the model
- [ ] Invalid provider raises clear error (though Pydantic should catch this first)
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify ModelConfig contract from TASK-AF-001."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("ModelConfig")
def test_model_config_to_model_translation():
    """Verify ModelConfig can be translated to model creation parameters.

    Contract: ModelConfig fields (provider, model, endpoint, temperature) must be translated to init_chat_model parameters
    Producer: TASK-AF-001
    """
    from config.models import ModelConfig

    config = ModelConfig(provider="local", model="test-model", endpoint="http://localhost:8000/v1", temperature=0.7)
    assert hasattr(config, "provider"), "ModelConfig must have provider field"
    assert hasattr(config, "model"), "ModelConfig must have model field"
    assert hasattr(config, "endpoint"), "ModelConfig must have endpoint field"
    assert hasattr(config, "temperature"), "ModelConfig must have temperature field"
```

## Implementation Notes

Use LangChain's `init_chat_model` or direct model class instantiation depending on provider. This is the "Option C" hybrid approach — extracting model creation into a shared module used by both Player and Coach factories.
