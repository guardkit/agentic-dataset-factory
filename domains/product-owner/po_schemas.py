"""Vendored PO serving schemas — specialist-agent pin ``69c8620`` (2026-07-07).

Built per SPEC-po-phase2-harvest-lift.md §2.7-1: fields + validators
byte-identical to the pinned sources modulo import paths, flattened into one
module; I/O helpers and non-model functions excluded. No runtime import from
specialist-agent.

Class → source module @ 69c8620:
    SourceDocument     — src/specialist_agent/roles/architect/types.py@69c8620
    Assumption         — src/specialist_agent/roles/architect/types.py@69c8620
    SourceCitation     — src/specialist_agent/roles/product_owner/types.py@69c8620
    FeatureSpecInput   — src/specialist_agent/roles/product_owner/types.py@69c8620
    Epic               — src/specialist_agent/roles/product_owner/types.py@69c8620
    ProductRoadmap     — src/specialist_agent/roles/product_owner/types.py@69c8620
    FeatureStub        — src/specialist_agent/roles/product_owner/phased_extraction.py@69c8620
    EpicStub           — src/specialist_agent/roles/product_owner/phased_extraction.py@69c8620
    EpicPlan           — src/specialist_agent/roles/product_owner/phased_extraction.py@69c8620
    FeatureEnrichment  — src/specialist_agent/roles/product_owner/phase_b_delta.py@69c8620
    EnrichmentBatch    — src/specialist_agent/roles/product_owner/phase_b_delta.py@69c8620
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# src/specialist_agent/roles/architect/types.py @ 69c8620
# ---------------------------------------------------------------------------


class SourceDocument(BaseModel):
    """A product doc that was read and what it contributed.

    Invariants:
        - ``filename`` must be a non-empty string.
        - ``contribution`` must be a non-empty string.

    Attributes:
        filename: Filename of the document (e.g. "overview.md").
        contribution: 1-2 sentence summary of what this doc added.
    """

    filename: str
    contribution: str

    @field_validator("filename")
    @classmethod
    def _filename_not_empty(cls, v: str) -> str:
        if not v.strip():
            msg = "SourceDocument.filename must not be empty."
            raise ValueError(msg)
        return v

    @field_validator("contribution")
    @classmethod
    def _contribution_not_empty(cls, v: str) -> str:
        if not v.strip():
            msg = "SourceDocument.contribution must not be empty."
            raise ValueError(msg)
        return v


class Assumption(BaseModel):
    """An architectural assumption identified during generation.

    Captures assumptions surfaced (or inferred) during architecture generation
    so they can be explicitly reviewed, challenged, or validated.

    Attributes:
        id: Sequential ID, e.g. "ASM-001".
        category: Classification of the assumption, e.g. "technology",
            "scale", "integration", "security".
        statement: The assumption text.
        source: Where the assumption came from, or "unstated" if inferred.
        confidence: Confidence level — "high", "medium", or "low".
        impact_if_wrong: What breaks if this assumption is invalid.

    TASK-AD-001: Created for architectural assumption tracking.
    """

    id: str
    category: str
    statement: str
    source: str
    confidence: Literal["high", "medium", "low"]
    impact_if_wrong: str


# ---------------------------------------------------------------------------
# src/specialist_agent/roles/product_owner/types.py @ 69c8620
# ---------------------------------------------------------------------------


class SourceCitation(BaseModel):
    """Precise provenance: document + section path + optional line range + quote.

    Provides section-level traceability for enrichment fields.  Every field
    populated by ``/po-extract*`` skill passes should carry at least one
    ``SourceCitation`` linking it back to the source document and heading path.

    Invariants:
        - ``section_path`` must have at least one heading segment.
        - ``line_end`` must be >= ``line_start`` when both are provided.
        - ``quote`` must be <= 200 characters (cite the snippet, not the section).

    Attributes:
        document: Filename as on disk.
        section_path: Heading breadcrumb, e.g. ``["Overview", "Payments"]``.
        line_start: 1-indexed inclusive start line (optional).
        line_end: 1-indexed inclusive end line (optional).
        quote: Verbatim excerpt (<= 200 chars, optional).

    TASK-PEX-003: Created for section-level traceability.
    """

    document: str
    section_path: list[str]
    line_start: int | None = None
    line_end: int | None = None
    quote: str | None = None

    @property
    def section_path_str(self) -> str:
        """Render section_path as ``"A > B > C"``."""
        return " > ".join(self.section_path)

    @model_validator(mode="after")
    def _valid(self) -> SourceCitation:
        if self.line_start is not None and self.line_end is not None:
            if self.line_end < self.line_start:
                raise ValueError("line_end must be >= line_start")
        if self.quote is not None and len(self.quote) > 200:
            raise ValueError(
                "quote must be <= 200 characters — cite the snippet, not the section"
            )
        if not self.section_path:
            raise ValueError("section_path must have at least one heading segment")
        return self


class FeatureSpecInput(BaseModel):
    """Per-feature description ready for ``/feature-spec --from``.

    Captures a single feature extracted from product documentation, with
    enough context for the downstream ``/feature-spec`` command to generate
    Gherkin acceptance criteria.

    Invariants:
        - ``description`` must contain at least 2 sentences.

    Attributes:
        feature_id: Feature identifier, e.g. "FEAT-PO-001".
        title: Human-readable feature title.
        description: Behavioural description in domain language (>= 2 sentences).
        bounded_context: Which bounded context this feature belongs to.
        source_documents: Doc filenames that ground this feature.
        constraints: Known constraints from docs.
        suggested_context_files: Files to pass as --context to /feature-spec.
        depends_on: Feature IDs this depends on.
        type: Optional ticket type, e.g. "Dev: Feature", "Design / UX".
        role: Optional domain-specific actor, e.g. "Customer".
        priority: Optional priority level (Low / Normal / High / Critical).
        moscow: Optional MoSCoW classification.
        value: Optional business value on a 1-5 scale.
        complexity: Optional complexity estimate.
        acceptance_criteria: Additional acceptance criteria sentences.
        technical_notes: Implementation-level notes.
        risks: Known risks associated with this feature.
        open_questions: Unresolved questions specific to this feature.
        links: Related URLs or document references.
        field_citations: Per-field provenance map (field name -> citations).

    Field citation guidance:
        Required when populated: ``description``, ``type``, ``role``,
        ``priority``, ``moscow``, ``value``, ``complexity``,
        ``acceptance_criteria``, ``technical_notes``, ``risks``.
        Recommended: ``open_questions``, ``links``, ``constraints``,
        ``depends_on``.
        Not required (derivable): ``feature_id``, ``title``,
        ``bounded_context``, ``suggested_context_files``.

    Note:
        ``field_citations`` is populated ONLY by ``/po-extract*`` skill
        passes. ``/po-spreadsheet-import`` must DROP a field's
        ``field_citations`` entry when it overwrites that field with a
        human edit.

    TASK-PEX-001: Added 11 optional enrichment fields.
    TASK-PEX-003: Added field_citations for section-level traceability.
    """

    feature_id: str
    title: str
    description: str
    bounded_context: str
    source_documents: list[str]
    constraints: list[str]
    suggested_context_files: list[str]
    depends_on: list[str]

    # -- Optional enrichment fields (TASK-PEX-001) ---------------------------
    type: str | None = None
    role: str | None = None
    priority: Literal["Low", "Normal", "High", "Critical"] | None = None
    moscow: (
        Literal["Must (core)", "Must", "Should", "Could", "Won't", "N/A", "?"] | None
    ) = None
    value: (
        Literal["1 (Lowest)", "2 (Low)", "3 (Medium)", "4 (High)", "5 (Highest)"] | None
    ) = None
    complexity: (
        Literal[
            "Very easy (<.5d)",
            "Easy (\u22481d)",
            "Normal (2-5d)",
            "Complex (5-10d)",
            "Very complex (>10d)",
            "Unknown",
            "N/A",
        ]
        | None
    ) = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    technical_notes: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)

    # -- Per-field provenance (TASK-PEX-003) -----------------------------------
    field_citations: dict[str, list[SourceCitation]] = Field(default_factory=dict)

    @field_validator("description")
    @classmethod
    def _at_least_two_sentences(cls, v: str) -> str:
        """Validate that description contains at least 2 sentences.

        A sentence is detected by the presence of a period followed by a
        space or end of string, which accommodates common abbreviations
        while still catching single-sentence descriptions.
        """
        # Count sentence-ending punctuation followed by space or end-of-string
        sentences = re.split(r"[.!?]\s+|[.!?]$", v.strip())
        # Filter out empty strings from split
        non_empty = [s for s in sentences if s.strip()]
        if len(non_empty) < 2:
            msg = (
                "FeatureSpecInput.description must contain at least 2 sentences, "
                f"got {len(non_empty)}. Provide sufficient detail for "
                "/feature-spec to generate good Gherkin."
            )
            raise ValueError(msg)
        return v


class Epic(BaseModel):
    """Group of related features within a bounded context.

    Organises features into coherent delivery units aligned with bounded
    contexts from domain-driven design.

    Invariants:
        - ``features`` must contain at least 1 entry.

    Attributes:
        id: Epic identifier, e.g. "EPIC-001".
        name: Human-readable epic name, e.g. "Open Banking Integration".
        bounded_context: The bounded context this epic belongs to.
        description: What this epic delivers.
        features: Features within this epic (at least 1).
        source_documents: Doc filenames that ground this epic.
        field_citations: Per-field provenance map (field name -> citations).

    Field citation guidance:
        Required when populated: ``description``.
        Recommended: ``bounded_context``.
        Not required (derivable): ``id``, ``name``.

    TASK-PEX-003: Added field_citations for section-level traceability.
    """

    id: str
    name: str
    bounded_context: str
    description: str
    features: list[FeatureSpecInput]
    source_documents: list[str]

    # -- Per-field provenance (TASK-PEX-003) -----------------------------------
    field_citations: dict[str, list[SourceCitation]] = Field(default_factory=dict)

    @field_validator("features")
    @classmethod
    def _at_least_one_feature(cls, v: list[FeatureSpecInput]) -> list[FeatureSpecInput]:
        if len(v) < 1:
            msg = "Each epic must have at least 1 feature"
            raise ValueError(msg)
        return v


class ProductRoadmap(BaseModel):
    """Primary output artefact -- a product roadmap produced by all 6 PO modes.

    Contains epics with features, priority rationale, and pipeline-ready
    feature spec inputs. The ``feature_spec_inputs`` field is a flattened
    view of all features across all epics, validated for consistency.

    Invariants:
        - ``epics`` must contain at least 1 entry.
        - ``mode`` must be one of the 6 valid modes.
        - ``feature_spec_inputs`` must match the flattened features from all epics.

    Attributes:
        project_name: Project identifier.
        mode: Operating mode -- "idea", "extract", "greenfield", "evolve",
            "impact", or "scope".
        epics: At least 1 Epic containing features.
        priority_rationale: Advisory text explaining ordering reasoning.
        constraints_and_dependencies: Known constraints and cross-feature dependencies.
        open_questions: Genuinely ambiguous items for human resolution.
        feature_spec_inputs: Flattened features from all epics for pipeline use.
        change_summary: Summary of changes (optional, for impact/evolve modes).
        coverage_score: Fraction of doc sections with >= 1 feature (optional).
        source_documents: Product docs read and what each contributed.
        assumptions: Assumptions identified during generation.
        estimate_unit: Optional estimation unit used across features -- e.g.
            "story-points", "t-shirt", "person-days", "complexity-bucket",
            or "ideal-hours". Defaults to None (not set).

    TASK-POR-001: Created as replacement for ProductDocument.
    TASK-PEX-006: Added estimate_unit field for top-of-roadmap metadata.
    """

    project_name: str
    mode: Literal["idea", "extract", "greenfield", "evolve", "impact", "scope"]
    epics: list[Epic]
    priority_rationale: str
    constraints_and_dependencies: list[str]
    open_questions: list[str]
    feature_spec_inputs: list[FeatureSpecInput]
    change_summary: str | None = None
    coverage_score: float | None = None
    source_documents: list[SourceDocument] = []
    assumptions: list[Assumption] = []
    estimate_unit: (
        Literal[
            "story-points",
            "t-shirt",
            "person-days",
            "complexity-bucket",
            "ideal-hours",
        ]
        | None
    ) = None

    @field_validator("epics")
    @classmethod
    def _at_least_one_epic(cls, v: list[Epic]) -> list[Epic]:
        if len(v) < 1:
            msg = "ProductRoadmap requires at least 1 epic"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _feature_spec_inputs_match_epics(self) -> ProductRoadmap:
        """Validate that feature_spec_inputs matches the flattened features from all epics.

        The feature_spec_inputs list must contain exactly the same features
        (by feature_id) as the flattened list from all epics.
        """
        epic_feature_ids = sorted(
            feat.feature_id for epic in self.epics for feat in epic.features
        )
        input_feature_ids = sorted(feat.feature_id for feat in self.feature_spec_inputs)
        if epic_feature_ids != input_feature_ids:
            msg = (
                "feature_spec_inputs must match flattened epics. "
                f"Epic feature IDs: {epic_feature_ids}, "
                f"feature_spec_inputs IDs: {input_feature_ids}"
            )
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# src/specialist_agent/roles/product_owner/phased_extraction.py @ 69c8620
# ---------------------------------------------------------------------------


class FeatureStub(BaseModel):
    """A minimal feature reference from Phase A — no enrichment fields.

    Contains only the identity, title, one-line intent, and source citations
    linking the stub back to product documentation.

    Attributes:
        feature_id: Feature identifier, e.g. "FEAT-PO-001".
        title: Human-readable feature title.
        intent: One-line intent describing what this feature does.
        source_citations: Citations linking stub to source docs.
    """

    feature_id: str
    title: str
    intent: str
    source_citations: list[SourceCitation] = Field(default_factory=list)


class EpicStub(BaseModel):
    """An epic from Phase A with feature stubs and cited document scope.

    ``cited_docs`` defines the document subset that Phase B should read
    for this epic — Phase B must NOT read the full corpus.

    Attributes:
        epic_id: Epic identifier, e.g. "EPIC-001".
        name: Human-readable epic name.
        bounded_context: Bounded context this epic belongs to.
        cited_docs: Document filenames this epic draws from.
        feature_stubs: Minimal feature references within this epic.
    """

    epic_id: str
    name: str
    bounded_context: str
    cited_docs: list[str]
    feature_stubs: list[FeatureStub]

    @field_validator("feature_stubs")
    @classmethod
    def _at_least_one_stub(cls, v: list[FeatureStub]) -> list[FeatureStub]:
        if not v:
            msg = "Each epic must have at least 1 feature stub"
            raise ValueError(msg)
        return v


class EpicPlan(BaseModel):
    """Machine-readable Phase A -> Phase B handoff (``epic_plan.json``).

    Captures the full set of epics and their feature stubs produced by
    Phase A, along with metadata for traceability.

    Invariants:
        - At least 1 epic.
        - All feature_ids across all epics must be unique.

    Attributes:
        project_name: Project identifier.
        mode: Operating mode (always "extract" for phased extraction).
        phase_a_completed_at: ISO timestamp of Phase A completion.
        epics: List of epic stubs with feature stubs.
        open_questions: Ambiguous items for human resolution.
        coverage_score: Fraction of doc sections covered.
        priority_rationale: Advisory ordering reasoning.
        source_documents: Product docs read during Phase A.
        assumptions: Assumptions from Phase A.
        constraints_and_dependencies: Known constraints.
        nfr_candidates: NFR IDs identified in Phase A (Phase C scope).

    TASK-PEX-007: Created for phased extraction handoff.
    """

    project_name: str
    mode: Literal["extract"] = "extract"
    phase_a_completed_at: datetime | None = None
    epics: list[EpicStub]
    open_questions: list[str] = Field(default_factory=list)
    coverage_score: float | None = None
    priority_rationale: str = ""
    source_documents: list[SourceDocument] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    constraints_and_dependencies: list[str] = Field(default_factory=list)
    nfr_candidates: list[dict] = Field(default_factory=list)

    @field_validator("epics")
    @classmethod
    def _at_least_one_epic(cls, v: list[EpicStub]) -> list[EpicStub]:
        if not v:
            msg = "EpicPlan requires at least 1 epic"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _unique_feature_ids(self) -> EpicPlan:
        """All feature_ids across all epics must be unique."""
        seen: set[str] = set()
        duplicates: list[str] = []
        for epic in self.epics:
            for stub in epic.feature_stubs:
                if stub.feature_id in seen:
                    duplicates.append(stub.feature_id)
                seen.add(stub.feature_id)
        if duplicates:
            msg = (
                f"Duplicate feature_ids found across epics: "
                f"{sorted(set(duplicates))}. Each feature_id must be unique."
            )
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# src/specialist_agent/roles/product_owner/phase_b_delta.py @ 69c8620
# ---------------------------------------------------------------------------


class FeatureEnrichment(BaseModel):
    """Phase B enrichment payload keyed by ``feature_id``.

    Represents one feature's enrichment fields as a delta against a Phase A
    stub. The dispatcher merges {Phase A stub + FeatureEnrichment} into a
    full ``FeatureSpecInput`` server-side, so the Player cannot rename,
    invent, or re-theme stubs.

    Identity fields intentionally absent:
        - ``title`` — lives on the Phase A stub; dispatcher copies it in.
        - ``bounded_context`` — inherited from the epic (see design §A.1).

    Invariants:
        - ``description`` must contain at least 2 sentences (same rule as
          ``FeatureSpecInput.description``).
        - ``source_documents`` must contain at least one entry.
    """

    feature_id: str
    description: str
    source_documents: list[str]
    constraints: list[str] = Field(default_factory=list)
    suggested_context_files: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)

    type: str = "Dev: Feature"
    role: str | None = None
    priority: Literal["Low", "Normal", "High", "Critical"] | None = None
    moscow: (
        Literal["Must (core)", "Must", "Should", "Could", "Won't", "N/A", "?"]
        | None
    ) = None
    value: (
        Literal[
            "1 (Lowest)",
            "2 (Low)",
            "3 (Medium)",
            "4 (High)",
            "5 (Highest)",
        ]
        | None
    ) = None
    complexity: (
        Literal[
            "Very easy (<.5d)",
            "Easy (≈1d)",
            "Normal (2-5d)",
            "Complex (5-10d)",
            "Very complex (>10d)",
            "Unknown",
            "N/A",
        ]
        | None
    ) = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    technical_notes: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    field_citations: dict[str, list[SourceCitation]] = Field(default_factory=dict)

    @field_validator("description")
    @classmethod
    def _at_least_two_sentences(cls, v: str) -> str:
        sentences = re.split(r"[.!?]\s+|[.!?]$", v.strip())
        non_empty = [s for s in sentences if s.strip()]
        if len(non_empty) < 2:
            msg = (
                "FeatureEnrichment.description must contain at least 2 "
                f"sentences, got {len(non_empty)}. Provide sufficient detail "
                "for /feature-spec to generate good Gherkin."
            )
            raise ValueError(msg)
        return v

    @field_validator("source_documents")
    @classmethod
    def _nonempty_sources(cls, v: list[str]) -> list[str]:
        if not v:
            msg = (
                "FeatureEnrichment.source_documents must contain at least "
                "one entry — every enrichment must be grounded."
            )
            raise ValueError(msg)
        return v


class EnrichmentBatch(BaseModel):
    """Per-epic batch of ``FeatureEnrichment``s — one Player call emits one batch.

    Invariants:
        - ``enrichments`` is non-empty.
        - Every ``enrichment.feature_id`` is unique within the batch.
    """

    project_name: str
    epic_id: str
    enrichments: list[FeatureEnrichment]

    @field_validator("enrichments")
    @classmethod
    def _nonempty(cls, v: list[FeatureEnrichment]) -> list[FeatureEnrichment]:
        if not v:
            msg = "EnrichmentBatch.enrichments must be non-empty."
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _unique_feature_ids(self) -> EnrichmentBatch:
        seen: set[str] = set()
        dups: list[str] = []
        for e in self.enrichments:
            if e.feature_id in seen:
                dups.append(e.feature_id)
            seen.add(e.feature_id)
        if dups:
            msg = (
                f"Duplicate feature_id values in EnrichmentBatch: "
                f"{sorted(set(dups))}. Each enrichment must target a "
                "distinct stub."
            )
            raise ValueError(msg)
        return self
