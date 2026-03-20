"""Prompt builder package for Player and Coach agent system prompts.

Provides base prompt constants and builder functions that inject GOAL.md
domain context into agent system prompts:

    from prompts import build_player_prompt, build_coach_prompt
    from prompts import PLAYER_BASE_PROMPT, COACH_BASE_PROMPT
"""

from __future__ import annotations

from prompts.coach_prompts import COACH_BASE_PROMPT, build_coach_prompt
from prompts.player_prompts import PLAYER_BASE_PROMPT, build_player_prompt

__all__ = [
    "PLAYER_BASE_PROMPT",
    "COACH_BASE_PROMPT",
    "build_player_prompt",
    "build_coach_prompt",
]
