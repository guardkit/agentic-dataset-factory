"""Contamination + hold-out discipline for the dcl domain — enforced in code, not convention.

Two guarantees, both mechanical:

1. **Hold-out denylist (the four frozen ``dcl-heldout`` exam capabilities).** No brief, no
   source capability, and no emitted capability may reproduce a hold-out — by CONTENT
   (sha256 of a hold-out solution / the 004 broken input) OR by IDENTITY (the exam
   capability/endpoint names: ``stats`` / ``/stats`` / ``GetStats``, ``version`` / ``/version``,
   ``uptime`` / ``/uptime``). :func:`assert_clean` refuses on a hit LOUDLY at brief-load and
   at row-mint time (the M-22 refuse-on-hit rule), so a poisoned input can never enter the
   corpus.

2. **Train/eval split disjointness.** ``train.row_id ∩ eval.row_id = ∅`` (content-addressed).
   :func:`assign_split` freezes an eval_dcl slice at creation by a recorded seed +
   ``holdout_fraction``.

The identity scan is scoped to the SEMANTIC content — briefs and the fenced ``dcl``
capability text — never the embedded vocabulary reference (which legitimately contains the
word "version" in its ``DCL_VERSION_*`` diagnostics). A capability drifting toward a hold-out
endpoint is exactly what must be refused; boilerplate is not.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dcl.contracts import extract_capability

# --------------------------------------------------------------------------------------
# The denylist — content sha256s + identity strings of the four frozen hold-out exams.
# (fleet-evals/tasks/dcl-held-00{1,2,3}/solution/response.dcl + dcl-held-004
#  solution/response.dcl + input/broken.dcl. Computed 2026-07-17; READ-ONLY sources.)
# --------------------------------------------------------------------------------------
DENYLIST_CONTENT_SHAS: frozenset[str] = frozenset({
    "50029444e177b922113263ac8e2b64c6559c507826d2d0ee74462fc7adb28ad4",  # held-001 stats
    "c371c648fc8b3069bc342ddfb249a8aa99c162fe10391304a985608227ae2416",  # held-002 version
    "239f1b70f30092dd36c01c6dfc0c73afdcbd539b577a5e557d55ea8c278af965",  # held-003 uptime
    "a9b74c76080907aa1ba8d1e97f2302eb623e4918226d24050548b6d91fcfa699",  # held-004 solution
    "cbaeb01ce4bae2d78f438edc62315824b6daa10c0e7f672f0530466295922c28",  # held-004 broken input
})

# Whole-word identity tokens (matched after camelCase + non-alnum splitting).
DENYLIST_WORD_TOKENS: frozenset[str] = frozenset({
    "stats", "statistics", "getstats", "version", "uptime",
})
# Raw lowercased endpoint substrings.
DENYLIST_PATH_SUBSTRINGS: tuple[str, ...] = ("/stats", "/version", "/uptime")


class ContaminationError(RuntimeError):
    """A brief / source / emitted capability matched a hold-out — refused loudly."""


def content_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")


def _tokenize(text: str) -> set[str]:
    """Lowercased word tokens, camelCase split so ``GetStats`` -> {get, stats}."""
    return {t.lower() for t in _CAMEL_RE.findall(text)}


def scan(text: str) -> list[str]:
    """Return denylist hits in ``text`` (empty = clean). Checks content sha, identity
    tokens, and endpoint substrings."""
    hits: list[str] = []
    if content_sha(text) in DENYLIST_CONTENT_SHAS:
        hits.append("content-sha256 matches a frozen hold-out solution/input")
    tokens = _tokenize(text)
    for tok in sorted(DENYLIST_WORD_TOKENS & tokens):
        hits.append(f"hold-out identity token {tok!r}")
    low = text.lower()
    for sub in DENYLIST_PATH_SUBSTRINGS:
        if sub in low:
            hits.append(f"hold-out endpoint path {sub!r}")
    return hits


def assert_clean(text: str, *, what: str) -> None:
    """Refuse LOUDLY (M-22) if ``text`` matches a hold-out by content or identity."""
    hits = scan(text)
    if hits:
        raise ContaminationError(
            f"{what} is contaminated by a frozen dcl-heldout exam: {'; '.join(hits)}. "
            "Hold-out capabilities (stats/version/uptime/GetStats) are the exam — no brief, "
            "source, or emitted row may reproduce them."
        )


# --------------------------------------------------------------------------------------
# Stratified hold-out split — frozen at creation by a recorded seed.
# --------------------------------------------------------------------------------------
def assign_split(row_id: str, *, holdout_fraction: float, seed: str = "dcl-phase1") -> str:
    """Deterministically assign ``train`` | ``eval_dcl`` (stable across processes)."""
    if not 0.0 <= holdout_fraction <= 1.0:
        raise ValueError("holdout_fraction must be in [0, 1]")
    bucket = int(hashlib.sha256(f"{seed}:{row_id}".encode()).hexdigest()[:8], 16) % 10_000
    return "eval_dcl" if bucket < round(holdout_fraction * 10_000) else "train"


# --------------------------------------------------------------------------------------
# Train/eval contamination check — embeds in the manifest.
# --------------------------------------------------------------------------------------
def _row_id(row: dict[str, Any]) -> str:
    return row["metadata"]["row_id"]


def _semantic_texts(row: dict[str, Any]) -> list[str]:
    """The capability text (+ the broken dcl for repair rows) — the denylist scan surface."""
    texts = [extract_capability(row)]
    user = row["messages"][1]["content"]
    for m in re.finditer(r"```dcl\s*\n(.*?)\n```", user, re.S):
        texts.append(m.group(1))
    return texts


@dataclass
class ContaminationResult:
    status: str  # "pass" | "fail"
    method: str
    intersection: list[str]
    denylist_violations: list[dict[str, str]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "method": self.method,
            "intersection": len(self.intersection),
            "intersection_row_ids": self.intersection,
            "denylist_violations": self.denylist_violations,
        }


CHECK_METHOD = (
    "row_id set intersection (train ∩ eval) + hold-out denylist scan "
    "(content-sha256 + capability/endpoint identity) over every row's capability text"
)


def check_contamination(
    train_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
) -> ContaminationResult:
    """row_id disjointness across the split + a denylist sweep over all rows."""
    train_ids = {_row_id(r) for r in train_rows}
    eval_ids = {_row_id(r) for r in eval_rows}
    intersection = sorted(train_ids & eval_ids)

    violations: list[dict[str, str]] = []
    for split_name, rows in (("train", train_rows), ("eval_dcl", eval_rows)):
        for r in rows:
            for text in _semantic_texts(r):
                for hit in scan(text):
                    violations.append(
                        {"split": split_name, "row_id": _row_id(r), "hit": hit}
                    )

    status = "pass" if not (intersection or violations) else "fail"
    return ContaminationResult(
        status=status,
        method=CHECK_METHOD,
        intersection=intersection,
        denylist_violations=violations,
    )


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows
