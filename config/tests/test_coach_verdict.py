"""Tests for the CoachVerdict and Issue Pydantic models.

Validates schema constraints, field types, the is_accepted property,
and edge cases per the Coach Rejection Schema specification.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from config.coach_verdict import CoachVerdict, Issue


# ---------------------------------------------------------------------------
# Issue model tests
# ---------------------------------------------------------------------------


class TestIssue:
    """Tests for the Issue sub-model."""

    def test_valid_blocking_issue(self) -> None:
        issue = Issue(
            criterion="ao_accuracy",
            severity="blocking",
            description="AO3 cited but response contains no contextual analysis",
            suggestion="Add reference to Victorian social attitudes",
        )
        assert issue.criterion == "ao_accuracy"
        assert issue.severity == "blocking"
        assert issue.description == "AO3 cited but response contains no contextual analysis"
        assert issue.suggestion == "Add reference to Victorian social attitudes"

    def test_valid_minor_issue(self) -> None:
        issue = Issue(
            criterion="factual_accuracy",
            severity="minor",
            description="Incorrect act reference",
            suggestion="Correct the act/scene reference",
        )
        assert issue.severity == "minor"

    def test_invalid_severity_rejected(self) -> None:
        with pytest.raises(ValidationError, match="severity"):
            Issue(
                criterion="ao_accuracy",
                severity="critical",
                description="Some problem",
                suggestion="Fix it",
            )

    def test_missing_required_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Issue(
                criterion="ao_accuracy",
                severity="blocking",
                description="Some problem",
                # suggestion is missing
            )


# ---------------------------------------------------------------------------
# CoachVerdict model tests
# ---------------------------------------------------------------------------


class TestCoachVerdict:
    """Tests for the CoachVerdict model."""

    @staticmethod
    def _accepted_verdict(**overrides: object) -> dict:
        """Return a valid accepted verdict dict with optional overrides."""
        base: dict = {
            "decision": "accept",
            "score": 4,
            "layer_correct": True,
            "type_correct": True,
            "criteria_met": {
                "socratic_approach": True,
                "ao_accuracy": True,
                "factual_accuracy": True,
            },
            "issues": [],
            "quality_assessment": "Strong example demonstrating effective pedagogy",
        }
        base.update(overrides)
        return base

    @staticmethod
    def _rejected_verdict(**overrides: object) -> dict:
        """Return a valid rejected verdict dict with optional overrides."""
        base: dict = {
            "decision": "revise",
            "score": 2,
            "layer_correct": True,
            "type_correct": False,
            "criteria_met": {
                "socratic_approach": True,
                "ao_accuracy": False,
            },
            "issues": [
                {
                    "criterion": "ao_accuracy",
                    "severity": "blocking",
                    "description": "AO3 cited but no contextual analysis",
                    "suggestion": "Add reference to Victorian social attitudes",
                }
            ],
            "quality_assessment": "Needs revision for accuracy",
        }
        base.update(overrides)
        return base

    # --- Field type / constraint tests ---

    def test_valid_accept_verdict(self) -> None:
        v = CoachVerdict(**self._accepted_verdict())
        assert v.decision == "accept"
        assert v.score == 4
        assert v.layer_correct is True
        assert v.type_correct is True

    def test_valid_revise_verdict(self) -> None:
        v = CoachVerdict(**self._rejected_verdict())
        assert v.decision == "revise"
        assert v.score == 2
        assert len(v.issues) == 1
        assert v.issues[0].severity == "blocking"

    def test_decision_literal_rejects_invalid(self) -> None:
        with pytest.raises(ValidationError, match="decision"):
            CoachVerdict(**self._accepted_verdict(decision="reject"))

    def test_score_minimum_is_1(self) -> None:
        with pytest.raises(ValidationError, match="score"):
            CoachVerdict(**self._accepted_verdict(score=0))

    def test_score_maximum_is_5(self) -> None:
        with pytest.raises(ValidationError, match="score"):
            CoachVerdict(**self._accepted_verdict(score=6))

    def test_score_boundary_1_valid(self) -> None:
        v = CoachVerdict(**self._accepted_verdict(score=1))
        assert v.score == 1

    def test_score_boundary_5_valid(self) -> None:
        v = CoachVerdict(**self._accepted_verdict(score=5))
        assert v.score == 5

    def test_criteria_met_is_dict_str_bool(self) -> None:
        v = CoachVerdict(**self._accepted_verdict())
        assert isinstance(v.criteria_met, dict)
        for key, val in v.criteria_met.items():
            assert isinstance(key, str)
            assert isinstance(val, bool)

    def test_issues_is_list_of_issue(self) -> None:
        v = CoachVerdict(**self._rejected_verdict())
        assert isinstance(v.issues, list)
        assert all(isinstance(i, Issue) for i in v.issues)

    def test_empty_issues_list_valid(self) -> None:
        v = CoachVerdict(**self._accepted_verdict(issues=[]))
        assert v.issues == []

    def test_quality_assessment_is_string(self) -> None:
        v = CoachVerdict(**self._accepted_verdict())
        assert isinstance(v.quality_assessment, str)

    # --- is_accepted property tests ---

    def test_is_accepted_true_for_clean_accept(self) -> None:
        v = CoachVerdict(**self._accepted_verdict())
        assert v.is_accepted is True

    def test_is_accepted_false_when_decision_revise(self) -> None:
        v = CoachVerdict(**self._rejected_verdict())
        assert v.is_accepted is False

    def test_is_accepted_false_when_score_below_3(self) -> None:
        v = CoachVerdict(**self._accepted_verdict(score=2))
        assert v.is_accepted is False

    def test_is_accepted_true_when_score_exactly_3(self) -> None:
        v = CoachVerdict(**self._accepted_verdict(score=3))
        assert v.is_accepted is True

    def test_is_accepted_false_when_layer_incorrect(self) -> None:
        v = CoachVerdict(**self._accepted_verdict(layer_correct=False))
        assert v.is_accepted is False

    def test_is_accepted_false_when_type_incorrect(self) -> None:
        v = CoachVerdict(**self._accepted_verdict(type_correct=False))
        assert v.is_accepted is False

    def test_is_accepted_false_when_blocking_issue_present(self) -> None:
        issues = [
            {
                "criterion": "ao_accuracy",
                "severity": "blocking",
                "description": "Problem found",
                "suggestion": "Fix it",
            }
        ]
        v = CoachVerdict(**self._accepted_verdict(issues=issues))
        assert v.is_accepted is False

    def test_is_accepted_true_with_minor_issues_only(self) -> None:
        issues = [
            {
                "criterion": "factual_accuracy",
                "severity": "minor",
                "description": "Small issue",
                "suggestion": "Minor tweak",
            }
        ]
        v = CoachVerdict(**self._accepted_verdict(issues=issues))
        assert v.is_accepted is True

    def test_is_accepted_false_when_multiple_conditions_fail(self) -> None:
        v = CoachVerdict(**self._accepted_verdict(
            score=1,
            layer_correct=False,
            type_correct=False,
        ))
        assert v.is_accepted is False

    # --- Serialization tests ---

    def test_round_trip_json(self) -> None:
        original = CoachVerdict(**self._accepted_verdict())
        json_str = original.model_dump_json()
        restored = CoachVerdict.model_validate_json(json_str)
        assert restored == original

    def test_round_trip_dict(self) -> None:
        original = CoachVerdict(**self._rejected_verdict())
        d = original.model_dump()
        restored = CoachVerdict(**d)
        assert restored == original
