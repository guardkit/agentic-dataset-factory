"""Per-sample quote-verification (fabrication) gate — Stage 2 of the GCSE
regeneration lane.

Extracts quoted spans from an ACCEPTED sample's assistant turns and
verifies each against the sample's subject corpus.  A failed sample is
routed back into the revise loop by the orchestrator with the fabricated
span named in the Coach feedback; a per-run gate report
(checked / passed / revised / dropped / unverifiable / duplicates) lands
in the run output directory and the log.

The extraction + windowed-difflib metric approach is lifted from the
study-tutor golden-quote fabrication harness (READ-ONLY reference:
``study-tutor/scripts/eval/run_fabrication_eval.py`` — the handoff brief
pinned it under fleet-evals ``multisubject/harness``, but the harness
lives in study-tutor) and RE-IMPLEMENTED here — no cross-repo import.

Quote extraction (independent of any runtime extractor):
  * double-quoted spans — straight ``"..."`` and curly ``“...”``;
  * markdown block-quote runs — contiguous ``> ...`` lines joined with
    `` / `` (the verse linebreak convention), treated as one span;
  * the ``/`` verse-linebreak convention inside spans is preserved at
    extraction and neutralised at match time;
  * spans under ``min_quote_words`` words are not treated as quotations.

Windowed fuzzy metric (stdlib — rapidfuzz is not a dependency):
  for a normalised quote ``q`` of ``n`` words and a normalised chunk, word
  windows of size ``n-2 .. n+2`` slide over the chunk and
  ``difflib.SequenceMatcher(None, q, window).ratio()`` is computed; the
  span verifies when its best ratio across all windows of all chunks is
  ``>= match_threshold`` (exact normalised substring short-circuits to
  1.0).  Normalisation: '/' -> space, curly quotes -> straight,
  whitespace runs collapsed, surrounding punctuation stripped,
  lower-cased.

Corpus access is READ-ONLY: ``chroma.sqlite3`` opened with sqlite
``immutable=1`` (no lock, journal, or WAL write can touch the store),
reading the ``chunk_json`` rows of ``embedding_metadata`` — the
study-tutor store layout.  Honest degradation: a subject with NO
configured corpus makes the sample ``unverifiable`` — counted and loud in
the report, never a block on analysis-mode content.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Literal, Sequence

if TYPE_CHECKING:
    from config.models import GatesConfig, QuoteGateConfig
    from synthesis.validator import DuplicateDetector

logger = logging.getLogger(__name__)

GATE_REPORT_FILENAME = "gate_report.json"

#: Revision feedback for a duplicate sample (dedup wiring).
DUPLICATE_FEEDBACK = (
    "Duplicate content: this example's assistant reply is identical to an "
    "already-accepted example. Produce a distinctly different example for "
    "the same target — different scenario, different wording, different "
    "supporting evidence."
)

_DOUBLE_QUOTE = re.compile(r'"([^"\n]+)"|“([^”\n]+)”')
_BLOCK_QUOTE_LINE = re.compile(r"^\s{0,3}>\s?(.*)$")


# ---------------------------------------------------------------------------
# Extraction + normalisation + windowed fuzzy match
# ---------------------------------------------------------------------------


def normalise_for_match(text: str) -> str:
    """Normalise for matching: '/' -> space, curly -> straight quotes,
    collapse whitespace, strip surrounding punctuation, lower-case."""
    text = (
        text.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("/", " ")
    )
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(".,;:!?\"' ")
    return text.lower()


def extract_quoted_spans(text: str, min_quote_words: int = 4) -> list[str]:
    """Extract quoted spans: straight/curly double quotes + block quotes.

    Contiguous markdown block-quote lines are joined with `` / `` (the
    verse linebreak convention) into one span.  Spans under
    ``min_quote_words`` normalised words are dropped.
    """
    spans: list[str] = []
    for m in _DOUBLE_QUOTE.finditer(text):
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        if inner:
            spans.append(inner.strip())

    block_run: list[str] = []
    for line in text.splitlines() + [""]:
        bm = _BLOCK_QUOTE_LINE.match(line)
        if bm and bm.group(1).strip():
            block_run.append(bm.group(1).strip())
        else:
            if block_run:
                spans.append(" / ".join(block_run))
                block_run = []

    return [
        s
        for s in spans
        if len(normalise_for_match(s).split()) >= min_quote_words
    ]


def best_window_ratio(quote_norm: str, chunk_norm: str) -> float:
    """Best SequenceMatcher ratio of the quote vs word windows of the chunk.

    Exact normalised substring short-circuits to 1.0.  Windows span
    ``n-2 .. n+2`` words (n = quote word count), bounded to the chunk;
    ``quick_ratio`` upper bounds prune full computations.
    """
    if not quote_norm or not chunk_norm:
        return 0.0
    if quote_norm in chunk_norm:
        return 1.0
    chunk_words = chunk_norm.split()
    n = len(quote_norm.split())
    best = 0.0
    matcher = SequenceMatcher(None, "", quote_norm)
    for size in range(max(1, n - 2), min(len(chunk_words), n + 2) + 1):
        for start in range(0, len(chunk_words) - size + 1):
            window = " ".join(chunk_words[start : start + size])
            matcher.set_seq1(window)
            if matcher.real_quick_ratio() <= best or matcher.quick_ratio() <= best:
                continue
            ratio = matcher.ratio()
            if ratio > best:
                best = ratio
                if best == 1.0:
                    return best
    return best


def best_corpus_match(
    quote: str, chunks: Sequence[dict[str, Any]]
) -> tuple[float, int | None]:
    """Best ratio for ``quote`` across ``chunks`` -> (ratio, chunk_index)."""
    qn = normalise_for_match(quote)
    best, best_idx = 0.0, None
    for chunk in chunks:
        ratio = best_window_ratio(qn, normalise_for_match(chunk["text"]))
        if ratio > best:
            best, best_idx = ratio, chunk.get("chunk_index")
            if best == 1.0:
                break
    return best, best_idx


# ---------------------------------------------------------------------------
# Corpus loading (read-only sqlite immutable=1 — study-tutor store layout)
# ---------------------------------------------------------------------------


def load_corpus_from_sqlite(persist_dir: Path) -> list[dict[str, Any]]:
    """Read every ``chunk_json`` row from the store's sqlite, READ-ONLY.

    Opens ``chroma.sqlite3`` with ``immutable=1`` so no lock, journal, or
    WAL write can touch the store.  Returns the flat chunk list for the
    whole store (a subject store may span several text_names; a quote
    verifying against ANY of them is verified — comparative answers quote
    across texts).
    """
    db = Path(persist_dir) / "chroma.sqlite3"
    if not db.exists():
        raise FileNotFoundError(f"chroma.sqlite3 not found in store: {persist_dir}")
    con = sqlite3.connect(f"file:{db}?immutable=1", uri=True)
    try:
        rows = [
            json.loads(r[0])
            for r in con.execute(
                "select string_value from embedding_metadata"
                " where key='chunk_json'"
            )
        ]
    finally:
        con.close()
    rows.sort(key=lambda c: (c.get("text_name", ""), c.get("chunk_index", 0)))
    return rows


# ---------------------------------------------------------------------------
# Gate verdicts
# ---------------------------------------------------------------------------


@dataclass
class QuoteCheck:
    """One quoted span's verification verdict."""

    span: str
    best_ratio: float
    best_chunk_index: int | None
    fabricated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "span": self.span,
            "best_ratio": round(self.best_ratio, 4),
            "best_chunk_index": self.best_chunk_index,
            "fabricated": self.fabricated,
        }


@dataclass
class QuoteGateResult:
    """Gate verdict for one accepted sample.

    ``status``:
      * ``passed`` — every extracted quote verified (or there were none;
        analysis-mode content without quotations passes trivially).
      * ``failed`` — at least one quoted span had no corpus match at the
        threshold; the sample must be revised.
      * ``unverifiable`` — the sample's subject has no configured corpus
        (or no subject could be resolved); counted loudly, never blocked.
    """

    status: Literal["passed", "failed", "unverifiable"]
    subject: str | None
    quotes: list[QuoteCheck] = field(default_factory=list)
    reason: str | None = None

    @property
    def fabricated_spans(self) -> list[QuoteCheck]:
        return [q for q in self.quotes if q.fabricated]


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def _assistant_contents(example: dict[str, Any]) -> list[str]:
    """The assistant-turn content strings of a parsed example dict."""
    return [
        m.get("content", "")
        for m in example.get("messages", [])
        if isinstance(m, dict) and m.get("role") == "assistant"
    ]


class QuoteGate:
    """Per-sample quote-verification gate over per-subject corpus stores.

    Construction fails fast (``FileNotFoundError``) when a CONFIGURED
    store path has no ``chroma.sqlite3`` — a configured-but-missing store
    is an operator error, not an unverifiable subject.  Corpora load
    lazily on first use per subject and are cached for the run.
    """

    def __init__(self, config: QuoteGateConfig) -> None:
        self._config = config
        self._corpora: dict[str, list[dict[str, Any]]] = {}
        for subject, store in config.corpus_stores.items():
            db = Path(store) / "chroma.sqlite3"
            if not db.exists():
                raise FileNotFoundError(
                    f"quote_gate corpus store for subject '{subject}' has no "
                    f"chroma.sqlite3: {store}"
                )

    def _corpus_for(self, subject: str) -> list[dict[str, Any]]:
        if subject not in self._corpora:
            store = Path(self._config.corpus_stores[subject])
            chunks = load_corpus_from_sqlite(store)
            logger.info(
                "quote_gate corpus loaded: subject=%s, chunks=%d, store=%s",
                subject,
                len(chunks),
                store,
            )
            self._corpora[subject] = chunks
        return self._corpora[subject]

    def _resolve_subject(self, metadata: dict[str, Any]) -> str | None:
        subject = metadata.get(self._config.subject_key)
        if isinstance(subject, str) and subject:
            return subject
        return self._config.default_subject

    def check_assistant_texts(
        self, texts: Iterable[str], subject: str | None
    ) -> QuoteGateResult:
        """Verify the quoted spans of assistant texts for one subject."""
        if subject is None:
            return QuoteGateResult(
                status="unverifiable",
                subject=None,
                reason=(
                    f"no subject resolved (metadata key "
                    f"{self._config.subject_key!r} absent and no "
                    f"default_subject configured)"
                ),
            )
        if subject not in self._config.corpus_stores:
            return QuoteGateResult(
                status="unverifiable",
                subject=subject,
                reason=f"no corpus configured for subject '{subject}'",
            )

        spans: list[str] = []
        for text in texts:
            spans.extend(
                extract_quoted_spans(text, self._config.min_quote_words)
            )

        chunks = self._corpus_for(subject)
        quotes: list[QuoteCheck] = []
        for span in spans:
            ratio, chunk_idx = best_corpus_match(span, chunks)
            quotes.append(
                QuoteCheck(
                    span=span,
                    best_ratio=ratio,
                    best_chunk_index=chunk_idx,
                    fabricated=ratio < self._config.match_threshold,
                )
            )
        status: Literal["passed", "failed"] = (
            "failed" if any(q.fabricated for q in quotes) else "passed"
        )
        return QuoteGateResult(status=status, subject=subject, quotes=quotes)

    def check_example(self, example_json: str) -> QuoteGateResult:
        """Verify one accepted sample's example JSON.

        The whole assistant content is checked — think blocks included: a
        fabricated quotation anywhere in the sample is still trained.
        """
        try:
            example = json.loads(example_json)
        except (ValueError, TypeError):
            return QuoteGateResult(
                status="unverifiable",
                subject=None,
                reason="example JSON unparseable",
            )
        metadata = example.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        return self.check_assistant_texts(
            _assistant_contents(example), self._resolve_subject(metadata)
        )

    def feedback_for(self, result: QuoteGateResult) -> str:
        """Coach-feedback text naming each fabricated span (revise-loop)."""
        spans = result.fabricated_spans
        lines = [
            f"Fabrication gate failed: {len(spans)} quoted span(s) in your "
            f"example could not be verified against the "
            f"'{result.subject}' corpus:"
        ]
        for q in spans:
            lines.append(
                f'- "{q.span}" (best corpus similarity {q.best_ratio:.2f})'
            )
        lines.append(
            "Every direct quotation must reproduce the source text EXACTLY. "
            "Replace each span above with the exact wording from the source, "
            "or rephrase it without quotation marks if you are paraphrasing."
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# The per-run gate report
# ---------------------------------------------------------------------------


@dataclass
class GateReport:
    """Run-level gate accounting, persisted to the run output directory.

    Counting is per gate CHECK (a sample revised and re-accepted is
    checked again):

    * ``checked`` — accepted samples the gate examined.
    * ``passed`` — checks where every quote verified (``no_quotes`` of
      those had no quotations at all — analysis-mode content).
    * ``revised`` — checks that failed and routed the sample back into
      the revise loop.
    * ``dropped`` — targets terminally rejected after at least one gate
      flag (quote failure or duplicate) at some pass.
    * ``unverifiable`` — checks skipped because the sample's subject has
      no configured corpus; LOUD: warned in the log and called out in the
      report file.
    * ``duplicates`` — samples routed to revision by the dedup wiring.

    ``load_or_new`` restores a previous invocation's counts so the
    multi-invocation batch windows (and sequential ``--resume``)
    accumulate one honest per-run report.
    """

    output_dir: Path
    checked: int = 0
    passed: int = 0
    no_quotes: int = 0
    revised: int = 0
    dropped: int = 0
    unverifiable: int = 0
    duplicates: int = 0
    unverifiable_subjects: dict[str, int] = field(default_factory=dict)
    failures: list[dict[str, Any]] = field(default_factory=list)
    flagged_indices: set[int] = field(default_factory=set)

    @classmethod
    def load_or_new(cls, output_dir: Path, resume: bool = False) -> GateReport:
        """A fresh report, or the persisted one when resuming a run."""
        path = Path(output_dir) / GATE_REPORT_FILENAME
        report = cls(output_dir=Path(output_dir))
        if resume and path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            report.checked = data.get("checked", 0)
            report.passed = data.get("passed", 0)
            report.no_quotes = data.get("no_quotes", 0)
            report.revised = data.get("revised", 0)
            report.dropped = data.get("dropped", 0)
            report.unverifiable = data.get("unverifiable", 0)
            report.duplicates = data.get("duplicates", 0)
            report.unverifiable_subjects = dict(
                data.get("unverifiable_subjects", {})
            )
            report.failures = list(data.get("failures", []))
            report.flagged_indices = set(data.get("flagged_indices", []))
        return report

    def record(self, result: QuoteGateResult, index: int) -> None:
        """Account one gate check for the sample at ``index``."""
        self.checked += 1
        if result.status == "passed":
            self.passed += 1
            if not result.quotes:
                self.no_quotes += 1
        elif result.status == "failed":
            self.revised += 1
            self.flagged_indices.add(index)
            self.failures.append(
                {
                    "index": index,
                    "subject": result.subject,
                    "spans": [q.to_dict() for q in result.fabricated_spans],
                }
            )
        else:  # unverifiable
            self.unverifiable += 1
            key = result.subject or "(unresolved)"
            self.unverifiable_subjects[key] = (
                self.unverifiable_subjects.get(key, 0) + 1
            )

    def record_duplicate(self, index: int) -> None:
        """Account one dedup rejection for the sample at ``index``."""
        self.duplicates += 1
        self.flagged_indices.add(index)

    def note_terminal_rejection(self, index: int) -> None:
        """Count a terminally rejected target as dropped if the gate
        flagged it at any pass."""
        if index in self.flagged_indices:
            self.dropped += 1

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "checked": self.checked,
            "passed": self.passed,
            "no_quotes": self.no_quotes,
            "revised": self.revised,
            "dropped": self.dropped,
            "unverifiable": self.unverifiable,
            "duplicates": self.duplicates,
            "unverifiable_subjects": self.unverifiable_subjects,
            "failures": self.failures,
            "flagged_indices": sorted(self.flagged_indices),
        }
        if self.unverifiable:
            data["unverifiable_note"] = (
                f"{self.unverifiable} accepted sample(s) were NOT "
                f"quote-verified — no corpus configured for: "
                + ", ".join(sorted(self.unverifiable_subjects))
            )
        return data

    def write_and_log(self) -> Path:
        """Persist the report to the output dir and log the summary, loud
        on unverifiable counts."""
        path = Path(self.output_dir) / GATE_REPORT_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.info(
            "gate_report: checked=%d, passed=%d (no_quotes=%d), revised=%d, "
            "dropped=%d, unverifiable=%d, duplicates=%d -> %s",
            self.checked,
            self.passed,
            self.no_quotes,
            self.revised,
            self.dropped,
            self.unverifiable,
            self.duplicates,
            path,
        )
        if self.unverifiable:
            logger.warning(
                "gate_report: %d sample(s) UNVERIFIABLE — no corpus "
                "configured for subject(s): %s. These samples were NOT "
                "quote-verified.",
                self.unverifiable,
                ", ".join(sorted(self.unverifiable_subjects)),
            )
        return path


# ---------------------------------------------------------------------------
# Construction + dedup seeding
# ---------------------------------------------------------------------------


def seed_duplicate_detector(detector: DuplicateDetector, train_path: Path) -> int:
    """Seed the detector from already-written accepted rows (resume).

    Without seeding, a resumed run's fresh in-memory detector would let a
    duplicate of a pre-crash accepted row through.  Malformed lines are
    skipped — seeding must never block a resume.
    """
    seeded = 0
    for line in Path(train_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            example = json.loads(line)
        except ValueError:
            continue
        detector.record_contents(_assistant_contents(example))
        seeded += 1
    return seeded


def build_gates(
    gates_config: GatesConfig | None,
    output_dir: Path,
    resume: bool = False,
) -> tuple[QuoteGate | None, DuplicateDetector | None, GateReport | None]:
    """Construct the gate machinery from the (optional) ``gates:`` block.

    Returns ``(None, None, None)`` when the block is absent or nothing in
    it is enabled — both loops then behave exactly as before (the
    byte-compatibility guarantee for existing domains).
    """
    if gates_config is None:
        return None, None, None

    quote_gate: QuoteGate | None = None
    if gates_config.quote_gate.enabled:
        quote_gate = QuoteGate(gates_config.quote_gate)

    dup_detector = None
    if gates_config.dedup.enabled:
        from synthesis.validator import DuplicateDetector

        dup_detector = DuplicateDetector()
        train_path = Path(output_dir) / "train.jsonl"
        if resume and train_path.exists():
            seeded = seed_duplicate_detector(dup_detector, train_path)
            logger.info(
                "dedup seeded from existing output: rows=%d (%s)",
                seeded,
                train_path,
            )

    if quote_gate is None and dup_detector is None:
        return None, None, None
    report = GateReport.load_or_new(output_dir, resume=resume)
    return quote_gate, dup_detector, report


def example_assistant_contents(example_json: str) -> list[str]:
    """Assistant-turn contents of an example JSON string (for dedup)."""
    try:
        example = json.loads(example_json)
    except (ValueError, TypeError):
        return []
    return _assistant_contents(example)


__all__ = [
    "DUPLICATE_FEEDBACK",
    "GATE_REPORT_FILENAME",
    "GateReport",
    "QuoteCheck",
    "QuoteGate",
    "QuoteGateResult",
    "best_corpus_match",
    "best_window_ratio",
    "build_gates",
    "example_assistant_contents",
    "extract_quoted_spans",
    "load_corpus_from_sqlite",
    "normalise_for_match",
    "seed_duplicate_detector",
]
