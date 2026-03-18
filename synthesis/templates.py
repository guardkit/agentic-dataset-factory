"""Prompt templates for training example generation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from synthesis.validator import GenerationTarget

TUTOR_SYSTEM_PROMPT: str = """\
You are an expert GCSE English tutor supporting a Year 10 student studying the AQA specification.
Your role is to guide the student using Socratic questioning — help them discover answers
rather than providing them directly. You have deep knowledge of:
- AQA English Language (8700): Paper 1 and Paper 2 question types
- AQA English Literature (8702): Set texts including Macbeth, A Christmas Carol,
  An Inspector Calls, and the Power and Conflict poetry anthology
- The AO1–AO6 assessment objectives and mark scheme criteria
- Grade descriptors from Grade 1 through Grade 9

Always be encouraging, patient, and age-appropriate. When assessing a student's response,
give structured feedback aligned to the mark scheme. Never do the work for the student —
ask questions that guide them toward the answer."""


@dataclass
class PromptPair:
    """System and user prompt pair ready for the Claude API.

    ``system_prompt`` is the meta-instruction to the generation model (Claude).
    ``user_prompt`` is the parameterised generation request.
    The TUTOR_SYSTEM_PROMPT is embedded *within* the user_prompt so that the
    generation model knows to include it verbatim in the produced ShareGPT JSON.
    """

    system_prompt: str
    user_prompt: str


# ---------------------------------------------------------------------------
# Private meta-instructions (system prompts for the generation model)
# ---------------------------------------------------------------------------

_REASONING_META: str = (
    "You are creating training data for a GCSE English AI tutor"
    " fine-tuned on Nemotron 3 Nano."
)

_MULTITURN_META: str = "You are creating training data for a GCSE English AI tutor."

_DIRECT_META: str = (
    "You are creating training data for a GCSE English AI tutor"
    " fine-tuned on Nemotron 3 Nano."
)


# ---------------------------------------------------------------------------
# Template functions
# ---------------------------------------------------------------------------


def build_reasoning_prompt(target: GenerationTarget) -> PromptPair:
    """Return a PromptPair for single-turn reasoning examples.

    Parameterised by target.text, target.topic, target.grade_target, target.ao.
    The generated example will include a <think> block in the assistant turn.
    """
    grade = target.grade_target if target.grade_target is not None else "null"
    user_prompt = (
        "Generate a single training example in this exact JSON format:\n"
        "\n"
        "{\n"
        '  "messages": [\n'
        '    {"role": "system", "content": "<SYSTEM_PROMPT>"},\n'
        '    {"role": "user", "content": "<STUDENT_QUESTION>"},\n'
        '    {"role": "assistant", "content":'
        ' "<think>\\n<REASONING>\\n</think>\\n\\n<TUTOR_RESPONSE>"}\n'
        "  ]\n"
        "}\n"
        "\n"
        "Requirements:\n"
        f"- Text: {target.text}\n"
        f"- Topic: {target.topic}\n"
        f"- Target grade level: {grade}\n"
        "- The <think> block should show the tutor reasoning about: what AOs apply, what the"
        " student likely knows, what misconceptions to watch for, and what Socratic question"
        " will guide them forward\n"
        "- The visible response should NOT give the answer — it should ask a guiding question"
        " or give partial scaffolding\n"
        "- Keep the student question realistic for a Year 10 student\n"
        "\n"
        "System prompt to embed verbatim as the 'system' message content:\n"
        f"{TUTOR_SYSTEM_PROMPT}\n"
        "\n"
        "Return only the JSON object, no preamble."
    )
    return PromptPair(system_prompt=_REASONING_META, user_prompt=user_prompt)


def build_multiturn_prompt(target: GenerationTarget) -> PromptPair:
    """Return a PromptPair for multi-turn essay feedback examples.

    Parameterised by target.text, target.topic, target.grade_target, target.ao.
    The generated example will have 4+ messages after the system message
    (user/assistant/user/assistant minimum), with each assistant turn containing
    a <think> block showing progressive Socratic scaffolding.
    """
    grade = target.grade_target if target.grade_target is not None else "null"
    ao_str = ", ".join(target.ao) if target.ao else "all relevant AOs"
    user_prompt = (
        "Generate a 3-turn conversation (user/assistant/user/assistant) where:\n"
        "1. A Year 10 student submits a paragraph for feedback\n"
        "2. The tutor gives structured feedback with a Socratic follow-up question\n"
        "3. The student responds with an attempt to improve\n"
        "4. The tutor affirms what improved and pushes further\n"
        "\n"
        "Format: ShareGPT JSON with system prompt included.\n"
        "The messages list must contain 4 or more messages after the system message"
        " (user/assistant/user/assistant minimum).\n"
        "Both assistant turns must include <think>...</think> blocks.\n"
        "Each <think> block should show the tutor reasoning about: what the student achieved,"
        " what AOs apply, and what Socratic question will guide them forward.\n"
        "\n"
        f"Text: {target.text}\n"
        f"Topic: {target.topic}\n"
        f"Assessment objective focus: {ao_str}\n"
        f"Starting grade of student paragraph: {grade}\n"
        "\n"
        "System prompt to embed verbatim as the 'system' message content:\n"
        f"{TUTOR_SYSTEM_PROMPT}\n"
        "\n"
        "Return only the JSON object, no preamble."
    )
    return PromptPair(system_prompt=_MULTITURN_META, user_prompt=user_prompt)


def build_direct_prompt(target: GenerationTarget) -> PromptPair:
    """Return a PromptPair for direct (non-reasoning) examples.

    Parameterised by target.text, target.topic, target.grade_target.
    The generated example will NOT contain a <think> block — used for factual
    recall, terminology definitions, and encouragement.
    """
    grade = target.grade_target if target.grade_target is not None else "null"
    user_prompt = (
        "Generate a single training example in this exact JSON format:\n"
        "\n"
        "{\n"
        '  "messages": [\n'
        '    {"role": "system", "content": "<SYSTEM_PROMPT>"},\n'
        '    {"role": "user", "content": "<STUDENT_QUESTION>"},\n'
        '    {"role": "assistant", "content": "<DIRECT_RESPONSE>"}\n'
        "  ]\n"
        "}\n"
        "\n"
        "Requirements:\n"
        f"- Text: {target.text}\n"
        f"- Topic: {target.topic}\n"
        f"- Target grade level: {grade}\n"
        "- The assistant response must NOT include a <think> block — respond directly\n"
        "- Suitable for factual recall, terminology definitions, or encouragement\n"
        "- Keep the student question realistic for a Year 10 student\n"
        "\n"
        "System prompt to embed verbatim as the 'system' message content:\n"
        f"{TUTOR_SYSTEM_PROMPT}\n"
        "\n"
        "Return only the JSON object, no preamble."
    )
    return PromptPair(system_prompt=_DIRECT_META, user_prompt=user_prompt)


def select_template(target: GenerationTarget) -> Callable[[GenerationTarget], PromptPair]:
    """Return the appropriate template function for the given GenerationTarget.

    Routing logic:
    - type="reasoning" and topic="essay_feedback" → build_multiturn_prompt
    - type="reasoning"                            → build_reasoning_prompt
    - type="direct"                               → build_direct_prompt
    """
    if target.type == "reasoning" and target.topic == "essay_feedback":
        return build_multiturn_prompt
    if target.type == "reasoning":
        return build_reasoning_prompt
    return build_direct_prompt


__all__ = [
    "TUTOR_SYSTEM_PROMPT",
    "PromptPair",
    "build_direct_prompt",
    "build_multiturn_prompt",
    "build_reasoning_prompt",
    "select_template",
]
