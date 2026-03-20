"""Coach verdict model for the Player-Coach adversarial evaluation loop.

Defines the structured JSON schema that the Coach agent returns for every
training example evaluation. See ``docs/design/models/DM-coach-rejection.md``
and ``docs/design/contracts/API-generation.md`` for the full specification.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Issue(BaseModel):
    """A specific problem identified during Coach evaluation.

    Each issue maps to a named evaluation criterion from GOAL.md and
    carries a severity that determines whether it blocks acceptance.
    """

    criterion: str
    severity: Literal["blocking", "minor"]
    description: str
    suggestion: str


class CoachVerdict(BaseModel):
    """Structured evaluation returned by the Coach agent.

    The Coach produces one ``CoachVerdict`` per training example submitted
    by the Player. The ``is_accepted`` property encodes the composite
    acceptance rule used to gate output writes.

    Acceptance rule (all must hold):
    - ``decision == "accept"``
    - ``score >= 3``
    - ``layer_correct is True``
    - ``type_correct is True``
    - No issues with ``severity == "blocking"``
    """

    decision: Literal["accept", "revise"]
    score: int = Field(ge=1, le=5)
    layer_correct: bool
    type_correct: bool
    criteria_met: dict[str, bool]
    issues: list[Issue]
    quality_assessment: str

    @property
    def is_accepted(self) -> bool:
        """Evaluate the composite acceptance rule.

        Returns ``True`` only when *all* acceptance conditions are satisfied:
        the decision is ``"accept"``, the score meets the minimum threshold,
        both structural checks pass, and no blocking issues are present.
        """
        if self.decision != "accept":
            return False
        if self.score < 3:
            return False
        if not self.layer_correct:
            return False
        if not self.type_correct:
            return False
        if any(issue.severity == "blocking" for issue in self.issues):
            return False
        return True


__all__ = ["CoachVerdict", "Issue"]
