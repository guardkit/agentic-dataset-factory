"""Feature-brief seed bank + deterministic reference-capability renderer.

The brief bank (``domains/dcl-capability-language/briefs.yaml``) holds ~50 one-paragraph
feature briefs across diverse business domains. Each brief names, in structured form, the
actor kind, the typed intent shape, the outcomes, the emitted event, one policy
family+concern, and a lifecycle — everything an author needs, and everything the
:func:`render_reference_capability` renderer needs to emit a **compiler-clean** DCL
capability offline (no model).

The renderer is what lets ``dcl_repair`` rows be minted without a live model for the
source: render a clean capability from a brief, break it with a recipe, and the corrected
text is the render output by construction. NONE of the briefs describe the frozen
hold-out endpoints (stats/version/uptime/GetStats) — enforced at load time by
:func:`load_briefs` via the contamination denylist.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from dcl import contamination

BRIEFS_YAML = (
    Path(__file__).resolve().parents[2]
    / "domains" / "dcl-capability-language" / "briefs.yaml"
)


@dataclass(frozen=True)
class Field:
    name: str
    type: str
    required: bool


# Verified step kinds a brief may drive through the deterministic renderer. `recovery`
# (supervised-only) is deliberately excluded — it is never sensible in a self-contained
# owned lifecycle (its target must be a contributor capability/effect with a `move … from`).
LIFECYCLE_STEP_KINDS = frozenset({"active", "decision", "waiting"})


@dataclass(frozen=True)
class LifecycleStep:
    """An intermediate lifecycle state between ``Started`` and ``Completed``.

    ``kind`` is one of :data:`LIFECYCLE_STEP_KINDS`. A ``decision`` step renders
    ``requires decision from <actor>``; a ``waiting`` step renders ``waits for event
    <event>`` (its exit transition is supplied by the chained ``move``)."""

    name: str
    kind: str = "active"


@dataclass(frozen=True)
class Brief:
    id: str
    domain: str
    title: str
    paragraph: str
    actor_name: str
    actor_kind: str
    shape_name: str
    fields: tuple[Field, ...]
    event_name: str
    event_fields: tuple[Field, ...]
    effect_name: str
    effect_kind: str
    policy_name: str
    policy_family: str
    concerns: tuple[str, ...]
    capability_name: str
    success_outcome: str
    failure_outcome: str
    rule_name: str
    rule_expr: str
    # Optional diversity knobs (default = the original 2-outcome / 2-state render, so the
    # existing 50 briefs stay BYTE-IDENTICAL). ``extra_outcome`` adds a third declared
    # outcome caused by ``<effect> unresolved``; ``lifecycle_steps`` inserts intermediate
    # states, growing the lifecycle to 3–4 states with active/decision/waiting kinds.
    extra_outcome: str | None = None
    lifecycle_steps: tuple[LifecycleStep, ...] = ()

    @property
    def brief_text(self) -> str:
        """The natural-language brief shown to the author model (the AUTHOR user message)."""
        return self.paragraph.strip()


def _field(d: dict[str, Any]) -> Field:
    return Field(name=d["name"], type=d["type"], required=bool(d.get("required", False)))


def _lifecycle_step(d: dict[str, Any]) -> LifecycleStep:
    kind = d.get("kind", "active")
    if kind not in LIFECYCLE_STEP_KINDS:
        raise ValueError(f"lifecycle step kind {kind!r} not in {sorted(LIFECYCLE_STEP_KINDS)}")
    return LifecycleStep(name=d["name"], kind=kind)


def _to_brief(d: dict[str, Any]) -> Brief:
    return Brief(
        id=d["id"],
        domain=d["domain"],
        title=d["title"],
        paragraph=d["paragraph"],
        actor_name=d["actor_name"],
        actor_kind=d["actor_kind"],
        shape_name=d["shape_name"],
        fields=tuple(_field(f) for f in d["fields"]),
        event_name=d["event_name"],
        event_fields=tuple(_field(f) for f in d["event_fields"]),
        effect_name=d["effect_name"],
        effect_kind=d["effect_kind"],
        policy_name=d["policy_name"],
        policy_family=d["policy_family"],
        concerns=tuple(d["concerns"]),
        capability_name=d["capability_name"],
        success_outcome=d["success_outcome"],
        failure_outcome=d["failure_outcome"],
        rule_name=d["rule_name"],
        rule_expr=d["rule_expr"],
        extra_outcome=d.get("extra_outcome"),
        lifecycle_steps=tuple(_lifecycle_step(s) for s in d.get("lifecycle_steps", ())),
    )


def load_briefs(path: Path | None = None, *, enforce_denylist: bool = True) -> list[Brief]:
    """Load the brief bank, asserting ids are unique and none is hold-out contaminated."""
    raw = yaml.safe_load((path or BRIEFS_YAML).read_text(encoding="utf-8"))
    briefs = [_to_brief(d) for d in raw["briefs"]]
    ids = [b.id for b in briefs]
    if len(set(ids)) != len(ids):
        raise ValueError("brief ids are not unique")
    if enforce_denylist:
        for b in briefs:
            # scan the natural-language brief AND the identifiers it will render into.
            contamination.assert_clean(b.brief_text, what=f"brief {b.id} paragraph")
            contamination.assert_clean(
                render_reference_capability(b), what=f"brief {b.id} rendered capability"
            )
    return briefs


def _render_fields(fields: tuple[Field, ...]) -> str:
    lines = []
    for f in fields:
        req = " required" if f.required else ""
        lines.append(f"  {f.name}: {f.type}{req}")
    return "\n".join(lines)


def _render_outcomes(brief: Brief) -> str:
    lines = [f"    {brief.success_outcome}", f"    {brief.failure_outcome}"]
    if brief.extra_outcome:
        lines.append(f"    {brief.extra_outcome}")
    return "\n".join(lines)


def _render_lifecycle(brief: Brief) -> str:
    """The lifecycle body (inside ``lifecycle {{ … }}``). Default (no steps) is the original
    2-state Started→Completed block, byte-for-byte. With ``lifecycle_steps`` it chains
    ``Started → <steps> → Completed`` (moves on the emitted event, the final move on the
    success outcome — the verified rule)."""
    if not brief.lifecycle_steps:
        return (
            "    begin step Started\n"
            "    end step Completed\n"
            "    step Started {\n"
            "      kind active\n"
            "    }\n"
            f"    move Started to Completed on outcome {brief.success_outcome}"
        )
    lines = [
        "    begin step Started",
        "    end step Completed",
        "    step Started {",
        "      kind active",
        "    }",
    ]
    for s in brief.lifecycle_steps:
        lines.append(f"    step {s.name} {{")
        lines.append(f"      kind {s.kind}")
        if s.kind == "decision":
            lines.append(f"      requires decision from {brief.actor_name}")
        elif s.kind == "waiting":
            lines.append(f"      waits for event {brief.event_name}")
        lines.append("    }")
    chain = ["Started"] + [s.name for s in brief.lifecycle_steps] + ["Completed"]
    for a, b in zip(chain, chain[1:]):
        trigger = (
            f"outcome {brief.success_outcome}" if b == "Completed"
            else f"event {brief.event_name}"
        )
        lines.append(f"    move {a} to {b} on {trigger}")
    return "\n".join(lines)


def _render_when(brief: Brief) -> str:
    lines = [f"    {brief.rule_name} violated then {brief.failure_outcome}"]
    if brief.extra_outcome:
        lines.append(f"    {brief.effect_name} unresolved then {brief.extra_outcome}")
    lines.append(f"    otherwise then {brief.success_outcome}")
    return "\n".join(lines)


def render_reference_capability(brief: Brief) -> str:
    """Render a compiler-clean DCL capability from a brief (deterministic; no model)."""
    concern_block = "\n".join("    " + c for c in brief.concerns)
    metric = f"{brief.capability_name.lower()}_duration"
    return f"""language dcl 1.0

actor {brief.actor_name} is {brief.actor_kind}

shape {brief.shape_name} {{
{_render_fields(brief.fields)}
}}

event {brief.event_name} is {{
{_render_fields(brief.event_fields)}
}}

effect {brief.effect_name} is {brief.effect_kind}

policy {brief.policy_name} {{
  {brief.policy_family} {{
{concern_block}
  }}
}}

capability {brief.capability_name} {{
  intent {brief.shape_name} from {brief.actor_name}
  outcomes {{
{_render_outcomes(brief)}
  }}
  rules {{
    {brief.rule_name}: {brief.rule_expr}
  }}
  effects {{
    {brief.effect_name}
  }}
  events {{
    emits {brief.event_name}
  }}
  policies {{
    {brief.policy_name} governs capability
  }}
  observe {{
    capability duration as {metric}
  }}
  lifecycle {{
{_render_lifecycle(brief)}
  }}
  when {{
{_render_when(brief)}
  }}
}}
"""
