"""Tests for business-rule validation logic: think-block, split tracking,
duplicate detection, routing, and the validate_example orchestrator."""

import pytest

from synthesis.validator import (
    DuplicateDetector,
    Message,
    Metadata,
    SplitTracker,
    TrainingExample,
    ValidationResult,
    route_example,
    validate_example,
    validate_think_block,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_example(
    *,
    type_: str = "reasoning",
    layer: str = "behaviour",
    assistant_content: str = "<think>plan</think> Answer.",
    extra_turns: int = 0,
) -> TrainingExample:
    """Build a minimal TrainingExample with controllable assistant content."""
    messages: list[Message] = [
        Message(role="system", content="You are a tutor."),
        Message(role="user", content="Question?"),
        Message(role="assistant", content=assistant_content),
    ]
    for i in range(extra_turns):
        messages.append(Message(role="user", content=f"Follow-up {i}?"))
        messages.append(Message(role="assistant", content=assistant_content))

    metadata = Metadata(
        layer=layer,  # type: ignore[arg-type]
        type=type_,  # type: ignore[arg-type]
        text="macbeth",
        topic="character_analysis",
    )
    return TrainingExample(messages=messages, metadata=metadata)


def _make_direct(assistant_content: str = "Plain answer.") -> TrainingExample:
    return _make_example(type_="direct", assistant_content=assistant_content)


def _make_reasoning(assistant_content: str = "<think>plan</think> Answer.") -> TrainingExample:
    return _make_example(type_="reasoning", assistant_content=assistant_content)


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


class TestValidationResult:
    def test_valid_minimal(self):
        r = ValidationResult(is_valid=True)
        assert r.is_valid is True
        assert r.reason is None
        assert r.route is None

    def test_invalid_with_reason(self):
        r = ValidationResult(is_valid=False, reason="bad")
        assert r.is_valid is False
        assert r.reason == "bad"

    def test_valid_with_route(self):
        r = ValidationResult(is_valid=True, route="output/train.jsonl")
        assert r.route == "output/train.jsonl"


# ---------------------------------------------------------------------------
# validate_think_block
# ---------------------------------------------------------------------------


class TestValidateThinkBlock:
    # --- reasoning examples ---

    def test_reasoning_with_think_block_is_valid(self):
        ex = _make_reasoning("<think>plan</think> Answer.")
        result = validate_think_block(ex)
        assert result.is_valid is True

    def test_reasoning_missing_think_block_is_invalid(self):
        ex = _make_reasoning("Answer with no think block.")
        result = validate_think_block(ex)
        assert result.is_valid is False
        assert "reasoning" in result.reason
        assert "<think>" in result.reason

    def test_reasoning_with_only_open_tag_is_invalid(self):
        """<think> without closing </think> does not satisfy the pattern."""
        ex = _make_reasoning("<think>incomplete answer")
        result = validate_think_block(ex)
        assert result.is_valid is False

    def test_reasoning_multi_turn_all_assistant_must_have_think(self):
        messages = [
            Message(role="system", content="sys"),
            Message(role="user", content="q1"),
            Message(role="assistant", content="<think>ok</think> ans1"),
            Message(role="user", content="q2"),
            Message(role="assistant", content="no think block"),  # missing
        ]
        meta = Metadata(layer="behaviour", type="reasoning", text="macbeth", topic="character_analysis")
        ex = TrainingExample(messages=messages, metadata=meta)
        result = validate_think_block(ex)
        assert result.is_valid is False

    def test_reasoning_multi_turn_all_have_think_is_valid(self):
        messages = [
            Message(role="system", content="sys"),
            Message(role="user", content="q1"),
            Message(role="assistant", content="<think>plan1</think> ans1"),
            Message(role="user", content="q2"),
            Message(role="assistant", content="<think>plan2</think> ans2"),
        ]
        meta = Metadata(layer="behaviour", type="reasoning", text="macbeth", topic="character_analysis")
        ex = TrainingExample(messages=messages, metadata=meta)
        result = validate_think_block(ex)
        assert result.is_valid is True

    # --- direct examples ---

    def test_direct_without_think_block_is_valid(self):
        ex = _make_direct("Plain helpful answer.")
        result = validate_think_block(ex)
        assert result.is_valid is True

    def test_direct_with_think_block_is_invalid(self):
        ex = _make_direct("<think>hidden thought</think> Answer.")
        result = validate_think_block(ex)
        assert result.is_valid is False
        assert "direct" in result.reason
        assert "<think>" in result.reason

    def test_direct_multi_turn_one_has_think_is_invalid(self):
        messages = [
            Message(role="system", content="sys"),
            Message(role="user", content="q1"),
            Message(role="assistant", content="Plain answer."),
            Message(role="user", content="q2"),
            Message(role="assistant", content="<think>oops</think> second answer"),
        ]
        meta = Metadata(layer="behaviour", type="direct", text="macbeth", topic="character_analysis")
        ex = TrainingExample(messages=messages, metadata=meta)
        result = validate_think_block(ex)
        assert result.is_valid is False

    # --- no assistant messages ---

    def test_no_assistant_messages_reasoning_is_valid(self):
        """System + user only — nothing to validate, passes."""
        messages = [
            Message(role="system", content="sys"),
            Message(role="user", content="q"),
        ]
        meta = Metadata(layer="behaviour", type="reasoning", text="macbeth", topic="character_analysis")
        ex = TrainingExample(messages=messages, metadata=meta)
        result = validate_think_block(ex)
        assert result.is_valid is True

    # --- case insensitivity ---

    def test_think_block_uppercase_tags(self):
        """Tags are matched case-insensitively."""
        ex = _make_reasoning("<THINK>plan</THINK> Answer.")
        result = validate_think_block(ex)
        assert result.is_valid is True

    def test_direct_uppercase_think_tag_detected(self):
        ex = _make_direct("<THINK>hidden</THINK> answer")
        result = validate_think_block(ex)
        assert result.is_valid is False


# ---------------------------------------------------------------------------
# SplitTracker
# ---------------------------------------------------------------------------


class TestSplitTracker:
    def test_initial_ratio_is_zero_zero(self):
        tracker = SplitTracker()
        assert tracker.ratio() == (0.0, 0.0)

    def test_initial_is_within_tolerance(self):
        tracker = SplitTracker()
        assert tracker.is_within_tolerance() is True

    def test_initial_warning_message_is_none(self):
        tracker = SplitTracker()
        assert tracker.warning_message() is None

    def test_single_reasoning_example(self):
        tracker = SplitTracker()
        tracker.track(_make_reasoning())
        reasoning_pct, direct_pct = tracker.ratio()
        assert reasoning_pct == pytest.approx(1.0)
        assert direct_pct == pytest.approx(0.0)

    def test_single_direct_example(self):
        tracker = SplitTracker()
        tracker.track(_make_direct())
        reasoning_pct, direct_pct = tracker.ratio()
        assert reasoning_pct == pytest.approx(0.0)
        assert direct_pct == pytest.approx(1.0)

    def test_exact_75_25_split(self):
        tracker = SplitTracker()
        for _ in range(3):
            tracker.track(_make_reasoning())
        tracker.track(_make_direct())
        reasoning_pct, direct_pct = tracker.ratio()
        assert reasoning_pct == pytest.approx(0.75)
        assert direct_pct == pytest.approx(0.25)
        assert tracker.is_within_tolerance() is True
        assert tracker.warning_message() is None

    def test_within_tolerance_boundary_lower(self):
        """70% reasoning is exactly at the ±5% boundary — warns (not within)."""
        tracker = SplitTracker()
        for _ in range(7):
            tracker.track(_make_reasoning())
        for _ in range(3):
            tracker.track(_make_direct())
        reasoning_pct, _ = tracker.ratio()
        assert reasoning_pct == pytest.approx(0.70)
        assert tracker.is_within_tolerance(tolerance=0.05) is False

    def test_within_tolerance_boundary_upper(self):
        """80% reasoning is exactly at the ±5% boundary — warns (not within)."""
        tracker = SplitTracker()
        for _ in range(4):
            tracker.track(_make_reasoning())
        tracker.track(_make_direct())
        reasoning_pct, _ = tracker.ratio()
        assert reasoning_pct == pytest.approx(0.80)
        assert tracker.is_within_tolerance(tolerance=0.05) is False

    def test_drifted_below_tolerance(self):
        """60% reasoning exceeds the ±5% tolerance."""
        tracker = SplitTracker()
        for _ in range(3):
            tracker.track(_make_reasoning())
        for _ in range(2):
            tracker.track(_make_direct())
        reasoning_pct, _ = tracker.ratio()
        assert reasoning_pct == pytest.approx(0.60)
        assert tracker.is_within_tolerance(tolerance=0.05) is False

    def test_drifted_above_tolerance(self):
        """90% reasoning exceeds the ±5% tolerance."""
        tracker = SplitTracker()
        for _ in range(9):
            tracker.track(_make_reasoning())
        tracker.track(_make_direct())
        assert tracker.is_within_tolerance(tolerance=0.05) is False

    def test_warning_message_when_drifted(self):
        tracker = SplitTracker()
        for _ in range(9):
            tracker.track(_make_reasoning())
        tracker.track(_make_direct())
        msg = tracker.warning_message()
        assert msg is not None
        assert "90.0%" in msg or "90%" in msg
        assert "75/25" in msg

    def test_warning_message_none_when_on_target(self):
        tracker = SplitTracker()
        for _ in range(3):
            tracker.track(_make_reasoning())
        tracker.track(_make_direct())
        assert tracker.warning_message() is None

    def test_custom_tolerance(self):
        tracker = SplitTracker()
        for _ in range(3):
            tracker.track(_make_reasoning())
        for _ in range(2):
            tracker.track(_make_direct())
        # 60% reasoning — within ±20% but not ±5%
        assert tracker.is_within_tolerance(tolerance=0.20) is True
        assert tracker.is_within_tolerance(tolerance=0.05) is False

    def test_counts_accumulate_across_many_calls(self):
        tracker = SplitTracker()
        for _ in range(75):
            tracker.track(_make_reasoning())
        for _ in range(25):
            tracker.track(_make_direct())
        reasoning_pct, direct_pct = tracker.ratio()
        assert reasoning_pct == pytest.approx(0.75)
        assert direct_pct == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# DuplicateDetector
# ---------------------------------------------------------------------------


class TestDuplicateDetector:
    def test_first_example_is_not_duplicate(self):
        detector = DuplicateDetector()
        ex = _make_reasoning("<think>x</think> unique content")
        assert detector.check(ex) is False

    def test_identical_example_is_duplicate(self):
        detector = DuplicateDetector()
        ex = _make_reasoning("<think>x</think> same content")
        detector.check(ex)  # record
        assert detector.check(ex) is True

    def test_different_content_not_duplicate(self):
        detector = DuplicateDetector()
        ex1 = _make_reasoning("<think>a</think> content A")
        ex2 = _make_reasoning("<think>b</think> content B")
        detector.check(ex1)
        assert detector.check(ex2) is False

    def test_same_content_different_metadata_is_duplicate(self):
        """Hash is content-only; metadata differences don't prevent detection."""
        detector = DuplicateDetector()
        assistant_content = "<think>plan</think> Answer about Macbeth."
        ex1 = _make_example(type_="reasoning", layer="behaviour", assistant_content=assistant_content)
        ex2 = _make_example(type_="reasoning", layer="knowledge", assistant_content=assistant_content)
        detector.check(ex1)
        assert detector.check(ex2) is True

    def test_only_assistant_content_hashed(self):
        """Two examples differing only in system/user messages but sharing
        identical assistant content are considered duplicates."""
        detector = DuplicateDetector()
        assistant_content = "<think>same</think> same answer"

        msgs1 = [
            Message(role="system", content="System prompt A"),
            Message(role="user", content="Different question"),
            Message(role="assistant", content=assistant_content),
        ]
        msgs2 = [
            Message(role="system", content="System prompt B"),
            Message(role="user", content="Different question 2"),
            Message(role="assistant", content=assistant_content),
        ]
        meta = Metadata(layer="behaviour", type="reasoning", text="macbeth", topic="character_analysis")
        ex1 = TrainingExample(messages=msgs1, metadata=meta)
        ex2 = TrainingExample(messages=msgs2, metadata=meta)

        detector.check(ex1)
        assert detector.check(ex2) is True

    def test_multiple_unique_examples_none_duplicate(self):
        detector = DuplicateDetector()
        for i in range(10):
            ex = _make_reasoning(f"<think>plan {i}</think> unique answer {i}")
            assert detector.check(ex) is False

    def test_duplicate_detection_across_different_example_instances(self):
        """Two independently constructed examples with identical assistant content."""
        detector = DuplicateDetector()
        content = "<think>shared</think> shared answer text"
        ex1 = _make_reasoning(content)
        ex2 = _make_reasoning(content)
        assert ex1 is not ex2  # different objects
        detector.check(ex1)
        assert detector.check(ex2) is True


# ---------------------------------------------------------------------------
# route_example
# ---------------------------------------------------------------------------


class TestRouteExample:
    def test_behaviour_routes_to_train_jsonl(self):
        ex = _make_example(layer="behaviour")
        assert route_example(ex) == "output/train.jsonl"

    def test_knowledge_routes_to_rag_index(self):
        ex = _make_example(layer="knowledge")
        assert route_example(ex) == "output/rag_index/knowledge.jsonl"


# ---------------------------------------------------------------------------
# validate_example (orchestrator)
# ---------------------------------------------------------------------------


class TestValidateExample:
    def _fresh(self):
        return SplitTracker(), DuplicateDetector()

    def test_valid_reasoning_example(self):
        tracker, detector = self._fresh()
        ex = _make_reasoning("<think>plan</think> Answer.")
        result = validate_example(ex, tracker, detector)
        assert result.is_valid is True
        assert result.route == "output/train.jsonl"

    def test_valid_direct_example(self):
        tracker, detector = self._fresh()
        ex = _make_direct("Plain answer.")
        result = validate_example(ex, tracker, detector)
        assert result.is_valid is True
        assert result.route == "output/train.jsonl"

    def test_valid_knowledge_example_routes_correctly(self):
        tracker, detector = self._fresh()
        ex = _make_example(type_="direct", layer="knowledge", assistant_content="Knowledge answer.")
        result = validate_example(ex, tracker, detector)
        assert result.is_valid is True
        assert result.route == "output/rag_index/knowledge.jsonl"

    def test_think_block_failure_returns_invalid(self):
        tracker, detector = self._fresh()
        ex = _make_reasoning("No think block here.")
        result = validate_example(ex, tracker, detector)
        assert result.is_valid is False
        assert result.reason is not None
        assert result.route is None

    def test_duplicate_returns_invalid(self):
        tracker, detector = self._fresh()
        ex = _make_reasoning("<think>plan</think> Answer.")
        validate_example(ex, tracker, detector)  # first pass records it
        result = validate_example(ex, tracker, detector)
        assert result.is_valid is False
        assert "duplicate" in result.reason

    def test_split_warning_included_in_reason(self):
        """After 10 examples all-reasoning (100% >> 75%), warning should appear."""
        tracker, detector = self._fresh()
        for i in range(10):
            ex = _make_reasoning(f"<think>p{i}</think> a{i}")
            result = validate_example(ex, tracker, detector)
        # Last result after drifting should carry a warning
        assert result.is_valid is True
        assert result.reason is not None
        assert "75/25" in result.reason

    def test_no_split_warning_on_target_ratio(self):
        """3 reasoning + 1 direct = 75/25 — no warning."""
        tracker, detector = self._fresh()
        for i in range(3):
            result = validate_example(
                _make_reasoning(f"<think>p{i}</think> a{i}"), tracker, detector
            )
        result = validate_example(_make_direct(f"plain {i}"), tracker, detector)
        assert result.is_valid is True
        assert result.reason is None

    def test_think_block_failure_does_not_update_tracker(self):
        """Failed examples must not pollute the split tracker."""
        tracker, detector = self._fresh()
        bad = _make_reasoning("No think block.")
        validate_example(bad, tracker, detector)
        # Tracker should still show no examples counted
        assert tracker.ratio() == (0.0, 0.0)

    def test_duplicate_does_not_update_tracker(self):
        """Duplicates must not be counted in the split tracker."""
        tracker, detector = self._fresh()
        ex = _make_reasoning("<think>plan</think> Answer.")
        validate_example(ex, tracker, detector)  # valid — counts as 1 reasoning
        validate_example(ex, tracker, detector)  # duplicate — should not count
        reasoning_pct, _ = tracker.ratio()
        assert reasoning_pct == pytest.approx(1.0)
        # Total tracked should be 1, not 2
        tracker2 = SplitTracker()
        tracker2.track(ex)
        assert tracker.ratio() == tracker2.ratio()

    def test_orchestration_order_think_before_duplicate(self):
        """An example that would be a duplicate but also fails think-block check
        should return the think-block error (checked first)."""
        tracker, detector = self._fresh()
        ex_good = _make_reasoning("<think>plan</think> Answer.")
        validate_example(ex_good, tracker, detector)

        # Same assistant content but wrong type — think-block fails first
        bad_meta = Metadata(
            layer="behaviour", type="direct", text="macbeth", topic="character_analysis"
        )
        bad_ex = TrainingExample(
            messages=[
                Message(role="system", content="sys"),
                Message(role="user", content="q"),
                # same content as ex_good, but type=direct → has <think> → invalid
                Message(role="assistant", content="<think>plan</think> Answer."),
            ],
            metadata=bad_meta,
        )
        result = validate_example(bad_ex, tracker, detector)
        assert result.is_valid is False
        assert "direct" in result.reason  # think-block error, not duplicate


# ---------------------------------------------------------------------------
# Import contract
# ---------------------------------------------------------------------------


class TestImportContract:
    def test_new_symbols_importable(self):
        from synthesis.validator import (
            DuplicateDetector,
            SplitTracker,
            ValidationResult,
            route_example,
            validate_example,
            validate_think_block,
        )

        assert all(
            obj is not None
            for obj in [
                ValidationResult,
                validate_think_block,
                SplitTracker,
                DuplicateDetector,
                route_example,
                validate_example,
            ]
        )
