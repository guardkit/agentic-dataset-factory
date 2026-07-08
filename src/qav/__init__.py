"""QA Verifier (QAV) Phase-1 dataset-generation code half — WS2-B11 code half.

The seeded-defect generation mode and its supporting transforms. This package is the
*mechanism*; running it against real repos to emit rows is a **generation run** (GB10,
post-window, per the program-plan calendar) and lives outside this package. Everything
here is library + CLI code, unit-tested on small local fixtures — no generation runs.

Binding spec (adf ``11db17a``): ``domains/qa-verifier/{GOAL,OUTPUT-CONTRACT,
PLAN-qav-phase1-dataset-generation,SPEC-qav-gold-negatives}.md`` + ``agent-config.draft.yaml``.
Umbrella: ``ai-transition/docs/qav-fine-tune-build-plan.md`` Step 1.
"""

from __future__ import annotations

from qav.contracts import (
    BUNDLE_FIELDS,
    GENERATION_MODES,
    GROUND_TRUTH_SOURCES,
    PHASE1_DC_CLASSES,
    PINNED_BUNDLE_SCHEMA_SHA,
    SPLITS,
    SYSTEM_PROMPT,
    RowValidationError,
    assistant_content,
    build_row,
    build_user_message,
    row_id,
    validate_bundle,
    validate_label,
    validate_row,
)

__all__ = [
    "BUNDLE_FIELDS",
    "GENERATION_MODES",
    "GROUND_TRUTH_SOURCES",
    "PHASE1_DC_CLASSES",
    "PINNED_BUNDLE_SCHEMA_SHA",
    "SPLITS",
    "SYSTEM_PROMPT",
    "RowValidationError",
    "assistant_content",
    "build_row",
    "build_user_message",
    "row_id",
    "validate_bundle",
    "validate_label",
    "validate_row",
]
