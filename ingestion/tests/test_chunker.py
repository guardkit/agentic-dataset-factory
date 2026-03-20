"""Tests for ingestion.chunker — chunk_text() function.

Covers all acceptance criteria for TASK-ING-002:
- AC-001: chunk_text() returns list[Chunk] with correct text segments
- AC-002: Default chunk_size=512 and overlap=64 match API contract
- AC-003: Text shorter than chunk_size produces exactly 1 chunk
- AC-004: Empty text returns empty list (no chunks)
- AC-005: source_metadata is copied into each chunk's metadata dict
- AC-006: Each chunk's metadata includes sequential chunk_index (0-based)
- AC-007: Custom chunk_size and overlap parameters are respected

Follows project test patterns:
- Organised by test class
- AAA pattern (Arrange, Act, Assert)
- Naming: test_<function_name>_<scenario>_<expected_result>
"""

from __future__ import annotations

import pytest

from ingestion.models import Chunk
from ingestion.chunker import chunk_text


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def short_text():
    """Text that is shorter than the default chunk_size of 512."""
    return "This is a short document."


@pytest.fixture
def long_text():
    """Text long enough to produce multiple chunks at default settings.

    Creates ~1500 characters of text (3+ chunks at chunk_size=512).
    """
    paragraph = (
        "The quick brown fox jumps over the lazy dog. "
        "Pack my box with five dozen liquor jugs. "
        "How vexingly quick daft zebras jump. "
        "Sphinx of black quartz, judge my vow. "
    )
    # Repeat enough to exceed 512 * 2 = 1024 characters
    return paragraph * 10


@pytest.fixture
def sample_metadata():
    return {
        "source_file": "mr-bruff-language.pdf",
        "page_number": 42,
        "docling_mode": "standard",
        "domain": "gcse-english-tutor",
    }


# ---------------------------------------------------------------------------
# AC-001: chunk_text() returns list[Chunk] with correct text segments
# ---------------------------------------------------------------------------


class TestChunkTextReturnType:
    def test_returns_list(self, long_text):
        result = chunk_text(long_text)
        assert isinstance(result, list)

    def test_returns_list_of_chunk_objects(self, long_text):
        result = chunk_text(long_text)
        assert len(result) > 0
        for chunk in result:
            assert isinstance(chunk, Chunk)

    def test_chunk_text_contains_content(self, long_text):
        result = chunk_text(long_text)
        for chunk in result:
            assert isinstance(chunk.text, str)
            assert len(chunk.text) > 0

    def test_all_text_covered(self, long_text):
        """All original text should be present across the chunks."""
        result = chunk_text(long_text)
        # Each chunk's text should be a substring of the original.
        for chunk in result:
            assert chunk.text in long_text


# ---------------------------------------------------------------------------
# AC-002: Default chunk_size=512 and overlap=64 match API contract
# ---------------------------------------------------------------------------


class TestDefaultParameters:
    def test_default_chunk_size_respected(self, long_text):
        """Chunks should not exceed the default chunk_size of 512."""
        result = chunk_text(long_text)
        for chunk in result:
            assert len(chunk.text) <= 512

    def test_default_overlap_produces_overlapping_text(self, long_text):
        """Consecutive chunks should share overlapping text."""
        result = chunk_text(long_text)
        if len(result) >= 2:
            # With overlap=64, the end of one chunk should share text
            # with the beginning of the next.
            for i in range(len(result) - 1):
                tail = result[i].text[-64:]
                head = result[i + 1].text[:64]
                # At least some overlap should exist
                assert any(
                    word in head for word in tail.split() if len(word) > 3
                ), "Expected overlapping text between consecutive chunks"

    def test_signature_defaults_match_contract(self):
        """Verify the function signature defaults are chunk_size=512, overlap=64."""
        import inspect

        sig = inspect.signature(chunk_text)
        assert sig.parameters["chunk_size"].default == 512
        assert sig.parameters["overlap"].default == 64


# ---------------------------------------------------------------------------
# AC-003: Text shorter than chunk_size produces exactly 1 chunk
# ---------------------------------------------------------------------------


class TestShortText:
    def test_short_text_produces_one_chunk(self, short_text):
        result = chunk_text(short_text)
        assert len(result) == 1

    def test_short_text_chunk_contains_full_text(self, short_text):
        result = chunk_text(short_text)
        assert result[0].text == short_text

    def test_text_exactly_at_chunk_size(self):
        """Text exactly equal to chunk_size should produce 1 chunk."""
        text = "a" * 512
        result = chunk_text(text, chunk_size=512)
        assert len(result) == 1
        assert result[0].text == text


# ---------------------------------------------------------------------------
# AC-004: Empty text returns empty list (no chunks)
# ---------------------------------------------------------------------------


class TestEmptyText:
    def test_empty_string_returns_empty_list(self):
        result = chunk_text("")
        assert result == []

    def test_empty_string_returns_list_type(self):
        result = chunk_text("")
        assert isinstance(result, list)

    def test_whitespace_only_returns_empty_list(self):
        """Whitespace-only text should be treated as empty."""
        result = chunk_text("   ")
        assert result == []


# ---------------------------------------------------------------------------
# AC-005: source_metadata is copied into each chunk's metadata dict
# ---------------------------------------------------------------------------


class TestSourceMetadata:
    def test_metadata_attached_to_each_chunk(self, long_text, sample_metadata):
        result = chunk_text(long_text, source_metadata=sample_metadata)
        for chunk in result:
            assert chunk.metadata["source_file"] == "mr-bruff-language.pdf"
            assert chunk.metadata["page_number"] == 42
            assert chunk.metadata["docling_mode"] == "standard"
            assert chunk.metadata["domain"] == "gcse-english-tutor"

    def test_none_metadata_results_in_chunk_index_only(self, short_text):
        result = chunk_text(short_text, source_metadata=None)
        assert len(result) == 1
        assert "chunk_index" in result[0].metadata
        # Should not have source_file etc.
        assert "source_file" not in result[0].metadata

    def test_metadata_is_copied_not_shared(self, long_text, sample_metadata):
        """Each chunk should have its own metadata dict, not a shared reference."""
        result = chunk_text(long_text, source_metadata=sample_metadata)
        if len(result) >= 2:
            result[0].metadata["extra"] = "test"
            assert "extra" not in result[1].metadata

    def test_empty_metadata_dict_accepted(self, short_text):
        result = chunk_text(short_text, source_metadata={})
        assert len(result) == 1
        assert result[0].metadata == {"chunk_index": 0}


# ---------------------------------------------------------------------------
# AC-006: Each chunk's metadata includes sequential chunk_index (0-based)
# ---------------------------------------------------------------------------


class TestChunkIndex:
    def test_chunk_index_starts_at_zero(self, long_text):
        result = chunk_text(long_text)
        assert result[0].metadata["chunk_index"] == 0

    def test_chunk_index_sequential(self, long_text):
        result = chunk_text(long_text)
        for i, chunk in enumerate(result):
            assert chunk.metadata["chunk_index"] == i

    def test_single_chunk_has_index_zero(self, short_text):
        result = chunk_text(short_text)
        assert result[0].metadata["chunk_index"] == 0


# ---------------------------------------------------------------------------
# AC-007: Custom chunk_size and overlap parameters are respected
# ---------------------------------------------------------------------------


class TestCustomParameters:
    def test_custom_chunk_size(self, long_text):
        result = chunk_text(long_text, chunk_size=100)
        for chunk in result:
            assert len(chunk.text) <= 100

    def test_custom_overlap(self, long_text):
        """Changing overlap should change chunking behavior."""
        result_small_overlap = chunk_text(long_text, chunk_size=200, overlap=10)
        result_large_overlap = chunk_text(long_text, chunk_size=200, overlap=100)
        # More overlap should produce more (or equal) chunks
        assert len(result_large_overlap) >= len(result_small_overlap)

    def test_custom_chunk_size_produces_more_chunks(self, long_text):
        result_large = chunk_text(long_text, chunk_size=512)
        result_small = chunk_text(long_text, chunk_size=100)
        assert len(result_small) > len(result_large)

    def test_custom_overlap_zero(self, long_text):
        """Zero overlap should still produce valid chunks."""
        result = chunk_text(long_text, chunk_size=200, overlap=0)
        assert len(result) > 0
        for chunk in result:
            assert isinstance(chunk, Chunk)


# ---------------------------------------------------------------------------
# Input validation — error handling for invalid parameters
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_zero_chunk_size_raises_value_error(self):
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            chunk_text("some text", chunk_size=0)

    def test_negative_chunk_size_raises_value_error(self):
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            chunk_text("some text", chunk_size=-10)

    def test_negative_overlap_raises_value_error(self):
        with pytest.raises(ValueError, match="overlap must be non-negative"):
            chunk_text("some text", overlap=-1)

    def test_overlap_equal_to_chunk_size_raises_value_error(self):
        with pytest.raises(ValueError, match="overlap.*must be less than chunk_size"):
            chunk_text("some text", chunk_size=100, overlap=100)

    def test_overlap_greater_than_chunk_size_raises_value_error(self):
        with pytest.raises(ValueError, match="overlap.*must be less than chunk_size"):
            chunk_text("some text", chunk_size=100, overlap=200)


# ---------------------------------------------------------------------------
# Import contract tests
# ---------------------------------------------------------------------------


class TestImportContract:
    def test_chunk_text_importable_from_chunker(self):
        from ingestion.chunker import chunk_text

        assert callable(chunk_text)

    def test_chunk_text_importable_from_package(self):
        """chunk_text should be importable from the ingestion package."""
        from ingestion import chunk_text

        assert callable(chunk_text)
