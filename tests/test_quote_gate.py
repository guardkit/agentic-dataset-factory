"""Tests for gates.quote_gate — the Stage-2 fabrication gate.

Hermetic: corpus stores are fixture sqlite files in tmp_path (the
study-tutor ``chroma.sqlite3`` / ``chunk_json`` layout), read via
``immutable=1``.  The two REAL fabricated set-text quotes documented in
``tasks/backlog/gemma4-moe-deploy/TASK-G4D-006-quote-factuality-eval.md``
(observed in GCSE smoke testing) are the must-catch fixtures.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from config.models import AgentConfig, GatesConfig, QuoteGateConfig
from gates.quote_gate import (
    GATE_REPORT_FILENAME,
    GateReport,
    QuoteGate,
    best_window_ratio,
    build_gates,
    extract_quoted_spans,
    load_corpus_from_sqlite,
    normalise_for_match,
    seed_duplicate_detector,
)
from synthesis.validator import DuplicateDetector

# ---------------------------------------------------------------------------
# The TASK-G4D-006 real fabrications (must be caught) + their real sources
# ---------------------------------------------------------------------------

FABRICATED_MACBETH = "screw your courage to the hope of belief"
REAL_MACBETH = (
    "We fail! But screw your courage to the sticking-place, And we'll not "
    "fail. When Duncan is asleep, whereto the rather shall his day's hard "
    "journey soundly invite him, his two chamberlains will I with wine and "
    "wassail so convince."
)
FABRICATED_INSPECTOR = (
    "We are all members of one body… and we must learn to live "
    "together—and not in our own circumstances"
)
REAL_INSPECTOR = (
    "We are members of one body. We are responsible for each other. And I "
    "tell you that the time will soon come when, if men will not learn "
    "that lesson, then they will be taught it in fire and blood and "
    "anguish."
)


def _make_store(
    tmp_path: Path,
    chunks: list[tuple[str, str]],
    subdir: str = "store",
) -> Path:
    """Build a fixture ChromaDB store (the study-tutor sqlite layout)."""
    store = tmp_path / subdir
    store.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(store / "chroma.sqlite3")
    con.execute(
        "create table embedding_metadata "
        "(id integer, key text, string_value text)"
    )
    for i, (text, text_name) in enumerate(chunks):
        con.execute(
            "insert into embedding_metadata values (?, 'chunk_json', ?)",
            (
                i,
                json.dumps(
                    {"text": text, "text_name": text_name, "chunk_index": i}
                ),
            ),
        )
    # A non-chunk_json row the loader must ignore.
    con.execute(
        "insert into embedding_metadata values (999, 'other_key', 'noise')"
    )
    con.commit()
    con.close()
    return store


def _english_store(tmp_path: Path) -> Path:
    return _make_store(
        tmp_path,
        [
            (REAL_MACBETH, "macbeth"),
            (REAL_INSPECTOR, "an_inspector_calls"),
        ],
        subdir="english_store",
    )


def _gate(tmp_path: Path, **overrides) -> QuoteGate:
    config = QuoteGateConfig(
        enabled=True,
        corpus_stores={"english": str(_english_store(tmp_path))},
        default_subject="english",
        **overrides,
    )
    return QuoteGate(config)


def _example_json(
    assistant_content: str, metadata: dict | None = None
) -> str:
    return json.dumps(
        {
            "messages": [
                {"role": "system", "content": "You are a GCSE tutor."},
                {"role": "user", "content": "Discuss the quotation."},
                {"role": "assistant", "content": assistant_content},
            ],
            "metadata": metadata or {"layer": "behaviour", "type": "direct"},
        }
    )


# ---------------------------------------------------------------------------
# Extraction + normalisation + metric
# ---------------------------------------------------------------------------


class TestExtraction:
    def test_straight_and_curly_double_quotes(self) -> None:
        text = (
            'She says "screw your courage to the sticking-place" and later '
            "“we are members of one body here” as well."
        )
        spans = extract_quoted_spans(text)
        assert spans == [
            "screw your courage to the sticking-place",
            "we are members of one body here",
        ]

    def test_block_quote_run_joined_with_verse_slash(self) -> None:
        text = (
            "Consider the opening:\n"
            "> So foul and fair a day\n"
            "> I have not seen\n"
            "\nA striking paradox."
        )
        assert extract_quoted_spans(text) == [
            "So foul and fair a day / I have not seen"
        ]

    def test_short_spans_ignored(self) -> None:
        assert extract_quoted_spans('He said "one body" only.') == []

    def test_min_words_configurable(self) -> None:
        spans = extract_quoted_spans(
            'He said "one body" only.', min_quote_words=2
        )
        assert spans == ["one body"]

    def test_verse_slash_neutralised_at_match_time(self) -> None:
        quote = normalise_for_match("So foul and fair a day / I have not seen")
        chunk = normalise_for_match("So foul and fair a day I have not seen.")
        assert best_window_ratio(quote, chunk) == 1.0


# ---------------------------------------------------------------------------
# The gate verdicts
# ---------------------------------------------------------------------------


class TestQuoteGateVerdicts:
    def test_task_g4d_006_macbeth_fabrication_caught(self, tmp_path) -> None:
        """The real observed misquote of Macbeth 1.7 MUST be caught."""
        gate = _gate(tmp_path)
        result = gate.check_example(
            _example_json(f'Lady Macbeth urges: "{FABRICATED_MACBETH}".')
        )
        assert result.status == "failed"
        assert [q.span for q in result.fabricated_spans] == [FABRICATED_MACBETH]
        assert result.fabricated_spans[0].best_ratio < 0.95

    def test_task_g4d_006_inspector_fabrication_caught(self, tmp_path) -> None:
        """The real mangled Inspector speech MUST be caught."""
        gate = _gate(tmp_path)
        result = gate.check_example(
            _example_json(f'The Inspector warns: "{FABRICATED_INSPECTOR}".')
        )
        assert result.status == "failed"
        assert result.fabricated_spans[0].span == FABRICATED_INSPECTOR

    def test_verbatim_quote_passes(self, tmp_path) -> None:
        gate = _gate(tmp_path)
        result = gate.check_example(
            _example_json(
                'She insists: "But screw your courage to the sticking-place" '
                "— note the imperative."
            )
        )
        assert result.status == "passed"
        assert len(result.quotes) == 1
        assert result.quotes[0].best_ratio == 1.0

    def test_no_quotes_analysis_content_passes(self, tmp_path) -> None:
        """Analysis-mode content without quotations is never blocked."""
        gate = _gate(tmp_path)
        result = gate.check_example(
            _example_json(
                "Priestley structures the play as a moral inquiry; each "
                "character's complacency is dismantled in turn."
            )
        )
        assert result.status == "passed"
        assert result.quotes == []

    def test_no_corpus_subject_is_unverifiable(self, tmp_path) -> None:
        gate = _gate(tmp_path)
        result = gate.check_example(
            _example_json(
                'The textbook notes "mitochondria are the powerhouse of the cell".',
                metadata={"subject": "biology"},
            )
        )
        assert result.status == "unverifiable"
        assert result.subject == "biology"
        assert "no corpus configured" in result.reason

    def test_unresolved_subject_is_unverifiable(self, tmp_path) -> None:
        config = QuoteGateConfig(
            enabled=True,
            corpus_stores={"english": str(_english_store(tmp_path))},
            default_subject=None,
        )
        result = QuoteGate(config).check_example(
            _example_json('A quote "we are members of one body" here.')
        )
        assert result.status == "unverifiable"
        assert result.subject is None

    def test_metadata_subject_key_wins_over_default(self, tmp_path) -> None:
        gate = _gate(tmp_path)
        result = gate.check_example(
            _example_json(
                f'"{FABRICATED_MACBETH}"', metadata={"subject": "english"}
            )
        )
        assert result.status == "failed"
        assert result.subject == "english"

    def test_feedback_names_the_fabricated_span(self, tmp_path) -> None:
        gate = _gate(tmp_path)
        result = gate.check_example(
            _example_json(f'"{FABRICATED_MACBETH}"')
        )
        feedback = gate.feedback_for(result)
        assert FABRICATED_MACBETH in feedback
        assert "Fabrication gate failed" in feedback

    def test_configured_but_missing_store_fails_fast(self, tmp_path) -> None:
        config = QuoteGateConfig(
            enabled=True,
            corpus_stores={"english": str(tmp_path / "nowhere")},
        )
        with pytest.raises(FileNotFoundError, match="english"):
            QuoteGate(config)


# ---------------------------------------------------------------------------
# Corpus loading (read-only sqlite immutable=1)
# ---------------------------------------------------------------------------


class TestCorpusLoading:
    def test_loads_only_chunk_json_rows(self, tmp_path) -> None:
        store = _english_store(tmp_path)
        chunks = load_corpus_from_sqlite(store)
        assert len(chunks) == 2
        assert {c["text_name"] for c in chunks} == {
            "macbeth",
            "an_inspector_calls",
        }

    def test_read_leaves_no_write_side_effects(self, tmp_path) -> None:
        """immutable=1 — no lock, journal, or WAL may touch the store."""
        store = _english_store(tmp_path)
        before = (store / "chroma.sqlite3").read_bytes()
        load_corpus_from_sqlite(store)
        assert (store / "chroma.sqlite3").read_bytes() == before
        assert not (store / "chroma.sqlite3-wal").exists()
        assert not (store / "chroma.sqlite3-journal").exists()

    def test_missing_store_raises(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError):
            load_corpus_from_sqlite(tmp_path / "absent")


# ---------------------------------------------------------------------------
# GateReport accounting
# ---------------------------------------------------------------------------


class TestGateReport:
    def test_counts_and_persistence_roundtrip(self, tmp_path) -> None:
        gate = _gate(tmp_path)
        report = GateReport.load_or_new(tmp_path)

        report.record(
            gate.check_example(_example_json("No quotes here at all.")), 0
        )
        report.record(
            gate.check_example(_example_json(f'"{FABRICATED_MACBETH}"')), 1
        )
        report.record(
            gate.check_example(
                _example_json('"x"', metadata={"subject": "biology"})
            ),
            2,
        )
        report.record_duplicate(3)
        report.note_terminal_rejection(1)  # gate-flagged -> dropped
        report.note_terminal_rejection(9)  # never flagged -> not dropped

        assert (report.checked, report.passed, report.no_quotes) == (3, 1, 1)
        assert (report.revised, report.dropped) == (1, 1)
        assert (report.unverifiable, report.duplicates) == (1, 1)

        path = report.write_and_log()
        assert path == tmp_path / GATE_REPORT_FILENAME
        data = json.loads(path.read_text())
        assert data["revised"] == 1
        assert data["failures"][0]["spans"][0]["span"] == FABRICATED_MACBETH
        assert "biology" in data["unverifiable_note"]

        resumed = GateReport.load_or_new(tmp_path, resume=True)
        assert resumed.checked == 3
        assert resumed.flagged_indices == {1, 3}

    def test_fresh_report_ignores_stale_file_without_resume(self, tmp_path) -> None:
        (tmp_path / GATE_REPORT_FILENAME).write_text('{"checked": 99}')
        assert GateReport.load_or_new(tmp_path).checked == 0


# ---------------------------------------------------------------------------
# Config + construction (byte-compatibility for existing domains)
# ---------------------------------------------------------------------------


def _agent_config(extra: dict | None = None) -> AgentConfig:
    data: dict = {
        "domain": "test-domain",
        "player": {
            "provider": "local",
            "model": "m",
            "endpoint": "http://localhost:9000/v1",
        },
        "coach": {
            "provider": "local",
            "model": "m",
            "endpoint": "http://localhost:9000/v1",
        },
    }
    if extra:
        data.update(extra)
    return AgentConfig.model_validate(data)


class TestGatesConfig:
    def test_absent_gates_block_is_none(self) -> None:
        """No gates block => None => existing domains byte-compatible."""
        assert _agent_config().gates is None

    def test_gates_block_defaults(self) -> None:
        config = _agent_config({"gates": {}})
        assert config.gates is not None
        assert config.gates.dedup.enabled is True  # ON for new runs
        assert config.gates.quote_gate.enabled is False  # opt-in

    def test_quote_gate_config_parses(self) -> None:
        config = _agent_config(
            {
                "gates": {
                    "quote_gate": {
                        "enabled": True,
                        "corpus_stores": {"english": "/some/store"},
                        "default_subject": "english",
                    }
                }
            }
        )
        assert config.gates.quote_gate.enabled is True
        assert config.gates.quote_gate.match_threshold == 0.95
        assert config.gates.quote_gate.min_quote_words == 4

    def test_build_gates_none_config(self, tmp_path) -> None:
        assert build_gates(None, tmp_path) == (None, None, None)

    def test_build_gates_all_disabled(self, tmp_path) -> None:
        gates = GatesConfig.model_validate({"dedup": {"enabled": False}})
        assert build_gates(gates, tmp_path) == (None, None, None)

    def test_build_gates_dedup_only(self, tmp_path) -> None:
        quote_gate, dup, report = build_gates(
            GatesConfig.model_validate({}), tmp_path
        )
        assert quote_gate is None
        assert isinstance(dup, DuplicateDetector)
        assert report is not None

    def test_build_gates_full(self, tmp_path) -> None:
        gates = GatesConfig.model_validate(
            {
                "quote_gate": {
                    "enabled": True,
                    "corpus_stores": {
                        "english": str(_english_store(tmp_path))
                    },
                    "default_subject": "english",
                }
            }
        )
        quote_gate, dup, report = build_gates(gates, tmp_path)
        assert isinstance(quote_gate, QuoteGate)
        assert isinstance(dup, DuplicateDetector)
        assert report is not None


class TestDedupSeeding:
    def test_seed_from_train_jsonl(self, tmp_path) -> None:
        train = tmp_path / "train.jsonl"
        rows = [
            _example_json("First accepted answer with enough words."),
            "not-json\n",
            _example_json("Second accepted answer, different words."),
        ]
        train.write_text("\n".join(rows) + "\n")
        detector = DuplicateDetector()
        assert seed_duplicate_detector(detector, train) == 2
        assert detector.seen_contents(
            ["First accepted answer with enough words."]
        )
        assert not detector.seen_contents(["Unseen content entirely."])

    def test_build_gates_seeds_on_resume(self, tmp_path) -> None:
        (tmp_path / "train.jsonl").write_text(
            _example_json("Already written row.") + "\n"
        )
        _, dup, _ = build_gates(
            GatesConfig.model_validate({}), tmp_path, resume=True
        )
        assert dup.seen_contents(["Already written row."])

    def test_seen_and_record_are_split(self) -> None:
        """The wiring records only AFTER a successful write."""
        detector = DuplicateDetector()
        assert not detector.seen_contents(["abc"])
        assert not detector.seen_contents(["abc"])  # still unseen: no record
        detector.record_contents(["abc"])
        assert detector.seen_contents(["abc"])
