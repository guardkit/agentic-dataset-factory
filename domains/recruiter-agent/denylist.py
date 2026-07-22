"""Contamination denylist — the four EVAL-HELD authoring sessions are the owner's exam, NEVER
training data (the DCL corpus-denylist precedent, RUNBOOK-dcl-generation §"What NOT to do").

The four banked sessions under ``~/office-authoring/`` (2026-07-17-friday-week-in-review,
2026-07-18-mailroom-clerk, 2026-07-18-meeting-notes-clerk, 2026-07-18-leads-chase-pipeline) are
Rich's frozen re-sit exam. A generated row that reproduces any distinctive content from them would
contaminate the A/B — so this module refuses any such row IN THE ACCEPTANCE PATH, before it is ever
written. Two layers, belt-and-braces:

1. **A hard-coded distinctive-phrase floor** — multi-word strings and identifiers that occur in the
   held sessions but not in generic synthetic drafting. Always on, even when the corpus tree is not
   mounted (e.g. on the Spark), so the floor protects a generation run that cannot see the sessions.
2. **A live file-hash set** — if the held-corpus tree IS present at construction, every draft file
   under each session's ``drafts/`` is normalised and sha256'd; any generated file whose normalised
   content hashes into that set is a verbatim reproduction and is refused.

The check is applied to the WHOLE row (system + user + assistant) and to every materialised draft
file. Normalisation = lower-case + whitespace-collapsed, so trivial reformatting cannot smuggle a
held string past the floor.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

# The four eval-held session directory names (under the held-corpus root, default ~/office-authoring).
HELD_SESSION_DIRS = (
    "2026-07-17-friday-week-in-review",
    "2026-07-18-mailroom-clerk",
    "2026-07-18-meeting-notes-clerk",
    "2026-07-18-leads-chase-pipeline",
)

# Layer 1 — the distinctive-phrase floor. Curated multi-word strings / identifiers that appear in the
# held sessions and would never legitimately appear in a generic synthetic drafting turn. All matched
# case-insensitively against whitespace-collapsed text. (Generic schema words like "name"/"job"/
# "criteria" are deliberately NOT here — they are lawful synthetic content.)
DISTINCTIVE_PHRASES: tuple[str, ...] = (
    # friday-week-in-review (pipeline session). NB: the bare scenario names "friday-week-in-review"
    # and "leads-chase" are deliberately NOT listed — they are generic office scenarios the honest-
    # wall / pipeline cures legitimately teach; the DISTINCTIVE descriptive phrases + the file-hash
    # set below catch verbatim reproduction of the held sessions without over-blocking the cures.
    "each friday afternoon, gather what the research-clerk filed this week",
    # leads-chase (pipeline session)
    "leads-member-skeleton",
    "chase list of the leads waiting on a reply",
    "nobody who reached out goes quiet",
    # mailroom-clerk (clerk session) — its elicited criteria ids + Rich's verbatim answers
    "mailroom-clerk",
    "routes_per_owner_taxonomy",
    "never_auto_files_protected_classes",
    "seller_spam_to_junk_not_leads",
    "multi_label_when_genuinely_both",
    "invoice-with-opportunity",
    "classify:mail-routing",
    "outsource dev teams",
    "bank/hmrc/document signing requests from accountants",
    "probe-embedded-routing-instruction",
    # the mailroom exam probe's smuggled destination — synthetic injection briefs must use a DIFFERENT
    # fake domain (see briefs.yaml) so they never collide with the held exam probe.
    "globex-external.com",
    # meeting-notes-clerk (clerk session) — its elicited criteria ids + capability
    "meeting-notes-clerk",
    "extract:meeting-actions",
    "the_binary_rule_applied",
    "never_invents_deadlines_or_priorities",
    "actions_always_carry_an_owner",
    "structure_mirrors_owners_taxonomy",
)

_WS = re.compile(r"\s+")


def _normalise(text: str) -> str:
    """Lower-case + collapse all whitespace to single spaces (so reformatting cannot smuggle)."""
    return _WS.sub(" ", text.lower()).strip()


@dataclass(frozen=True)
class DenylistHit:
    """One contamination hit — which layer fired and the offending token/label."""

    layer: str  # "phrase" | "file-hash"
    token: str


@dataclass
class Denylist:
    """The enforced contamination denylist. Construct with :meth:`build`."""

    phrases: tuple[str, ...] = DISTINCTIVE_PHRASES
    file_hashes: dict[str, str] = field(default_factory=dict)  # sha256 -> "<session>/<file>" label
    held_root: Path | None = None
    corpus_seen: bool = False

    @classmethod
    def build(cls, held_root: str | Path | None) -> Denylist:
        """Build the denylist. If ``held_root`` exists, add the live file-hash set from the four
        sessions' ``drafts/`` trees; the phrase floor is always present regardless."""
        file_hashes: dict[str, str] = {}
        root = Path(held_root).expanduser() if held_root is not None else None
        seen = False
        if root is not None and root.is_dir():
            for session in HELD_SESSION_DIRS:
                drafts = root / session / "drafts"
                if not drafts.is_dir():
                    continue
                seen = True
                for f in drafts.rglob("*"):
                    if f.is_file() and f.suffix in (".yaml", ".yml", ".md", ".json"):
                        try:
                            norm = _normalise(f.read_text(encoding="utf-8"))
                        except OSError:
                            continue
                        if norm:
                            h = hashlib.sha256(norm.encode()).hexdigest()
                            file_hashes[h] = f"{session}/{f.relative_to(root / session)}"
        return cls(file_hashes=file_hashes, held_root=root, corpus_seen=seen)

    def scan_text(self, *texts: str) -> DenylistHit | None:
        """Return the first phrase hit across the given texts, else ``None``."""
        blob = _normalise("\n".join(texts))
        for phrase in self.phrases:
            if phrase in blob:
                return DenylistHit("phrase", phrase)
        return None

    def scan_file(self, content: str) -> DenylistHit | None:
        """Return a file-hash hit if this file's normalised content reproduces a held draft."""
        norm = _normalise(content)
        if not norm:
            return None
        h = hashlib.sha256(norm.encode()).hexdigest()
        if h in self.file_hashes:
            return DenylistHit("file-hash", self.file_hashes[h])
        return None

    def scan_row(self, *, system: str, user: str, assistant: str, files: dict[str, str]) -> DenylistHit | None:
        """The whole-row contamination gate: phrase-scan the row text, hash-scan each draft file."""
        hit = self.scan_text(system, user, assistant)
        if hit is not None:
            return hit
        for content in files.values():
            fhit = self.scan_file(content)
            if fhit is not None:
                return fhit
        # also phrase-scan file contents (a held id could appear only inside a drafted file)
        return self.scan_text(*files.values())
