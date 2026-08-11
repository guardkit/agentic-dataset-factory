#!/usr/bin/env python3
"""Bake-off grader — deterministic, identical for every candidate.

Implements exactly the gate set in PREDECLARATION.md, importing the frozen
fleet-evals harness read-only. Run AFTER all candidates' responses are banked:

  python3 grade_bakeoff.py            # grades every responses/T*/ dir found

Per artifact: PASS = zero blocking findings. Output: grades/<candidate>.json
plus grades/RESULTS.md with the decision table.
"""

import json
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
FLEET_EVALS = Path("/home/richardwoollcott/Projects/appmilla_github/fleet-evals/harness")
BANLIST = Path(
    "/home/richardwoollcott/Projects/appmilla_github/fleet-evals/tasks/"
    "po-held-007-feature-spec/test/reference/domain_language_banlist.json"
)
sys.path.insert(0, str(FLEET_EVALS))

import grading  # noqa: E402
import po_contract  # noqa: E402
import spec_gates  # noqa: E402

FILE_BOUNDARY = re.compile(r"^=== FILE: (.+?) ===\s*$", re.M)


def rewrap_reasoning(record):
    """Mirror run_po_eval.py: fold llama.cpp reasoning_content back into <think>."""
    content = record.get("content") or ""
    resp = record.get("response") or {}
    try:
        msg = resp["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return content
    reasoning = msg.get("reasoning_content")
    if reasoning and "<think>" not in content:
        return f"<think>{reasoning}</think>\n{content}"
    return content


def grade_roadmap(raw, mode_required, corpus_names):
    findings = []
    try:
        payload = grading.parse_response(raw)
    except grading.ShapeError as e:
        return [f"shape: {e}"], None
    except Exception as e:
        return [f"shape: unparseable ({e})"], None

    if payload.get("mode") != mode_required:
        findings.append(f"mode: expected {mode_required!r}, got {payload.get('mode')!r}")

    for issue in po_contract.validate_product_roadmap(payload):
        findings.append(f"contract: {issue}")

    cited = grading.collect_cited_documents(payload)
    if mode_required == "greenfield":
        if cited:
            findings.append(f"grounding: greenfield must cite nothing, cites {sorted(cited)[:5]}")
        if payload.get("coverage_score") is not None:
            findings.append("grounding: greenfield coverage_score must be null")
        assumptions = payload.get("assumptions") or []
        if len(assumptions) < 3:
            findings.append(f"assumptions: {len(assumptions)} < 3 floor")
    else:  # extract
        for fab in grading.fabricated_references(payload, corpus_names):
            findings.append(f"fabricated: {fab}")
    return findings, payload


def grade_spec(raw):
    findings = []
    parts = FILE_BOUNDARY.split(raw)
    # parts = [preamble, name1, body1, name2, body2, ...]
    files = {}
    for i in range(1, len(parts) - 1, 2):
        files[parts[i].strip()] = parts[i + 1].strip() + "\n"
    if not files:
        return ["layout: no '=== FILE: … ===' sections found"], None

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        feature_names = [n for n in files if n.endswith(".feature")]
        slug = feature_names[0].rsplit(".", 1)[0] if feature_names else "unknown"
        spec_dir = root / "features" / slug
        spec_dir.mkdir(parents=True)
        for name, body in files.items():
            (spec_dir / name).write_text(body)

        for f in spec_gates.spec_layout_findings(root):
            findings.append(f"layout: {f}")
        try:
            paths = spec_gates.spec_paths(root)
        except Exception as e:
            findings.append(f"layout: {e}")
            return findings, None

        feature_text = paths["feature"].read_text()
        parsed = spec_gates.parse_feature(feature_text)
        for f in parsed.get("findings", []):
            findings.append(f"gherkin: {f}")
        for f in spec_gates.wrapped_step_findings(parsed):
            findings.append(f"wrapped_step: {f}")
        banlist = json.loads(BANLIST.read_text())
        for f in spec_gates.find_banned_language(parsed, banlist):
            findings.append(f"banned_language: {f}")
        for f in spec_gates.implementation_comment_findings(feature_text):
            findings.append(f"implementation_comment: {f}")

        scenario_names = {s.get("name") for s in parsed.get("scenarios", [])}
        n_scenarios = len(parsed.get("scenarios", []))
        if n_scenarios < 8:
            findings.append(f"floor: {n_scenarios} scenarios < 8")

        try:
            manifest = spec_gates.load_assumptions_manifest(paths["assumptions"])
            for f in spec_gates.manifest_schema_findings(manifest, scenario_names):
                findings.append(f"manifest: {f}")
            for f in spec_gates.annotation_findings(parsed, manifest):
                findings.append(f"annotation: {f}")
        except Exception as e:
            findings.append(f"manifest: unloadable ({e})")
            manifest = None

        try:
            summary = spec_gates.parse_summary(paths["summary"].read_text())
            if manifest is not None:
                entries = manifest.get("assumptions", manifest if isinstance(manifest, list) else [])
                n_assum = len(entries)
                for key, expect in (("scenarios", n_scenarios), ("assumptions", n_assum)):
                    got = summary.get(key)
                    if got is not None and got != expect:
                        findings.append(f"coherence: summary {key}={got} but actual {expect}")
        except Exception as e:
            findings.append(f"summary: unparseable ({e})")

    return findings, {"files": sorted(files), "scenarios": n_scenarios}


def grade_record(record, input_payload):
    bid = record["bakeoff_id"]
    raw = rewrap_reasoning(record)
    if not raw:
        return {"bakeoff_id": bid, "pass": False, "findings": ["no_response"], "n_findings": 1}
    if bid.startswith("GF"):
        findings, _ = grade_roadmap(raw, "greenfield", set())
    elif bid.startswith("EX"):
        m = re.search(r"^## File: (.+)$", input_payload["messages"][-1]["content"], re.M)
        corpus = {m.group(1).strip()} if m else set()
        findings, _ = grade_roadmap(raw, "extract", corpus)
    else:
        findings, _ = grade_spec(raw)
    findings = [str(f) for f in findings]
    return {"bakeoff_id": bid, "pass": not findings, "findings": findings, "n_findings": len(findings)}


def main():
    grades_dir = HERE / "grades"
    grades_dir.mkdir(exist_ok=True)
    inputs = {p.stem: json.loads(p.read_text()) for p in (HERE / "inputs").glob("*.json") if p.stem != "MANIFEST"}

    summary_rows = []
    for cand_dir in sorted((HERE / "responses").iterdir()):
        if not cand_dir.is_dir():
            continue
        cand = cand_dir.name
        results = []
        for rf in sorted(cand_dir.glob("*.json")):
            if rf.name == "models_probe.json":
                continue
            record = json.loads(rf.read_text())
            results.append(grade_record(record, inputs[record["bakeoff_id"]]))
        n_pass = sum(1 for r in results if r["pass"])
        mean_findings = round(sum(r["n_findings"] for r in results) / max(len(results), 1), 2)
        (grades_dir / f"{cand}.json").write_text(json.dumps(results, indent=2))
        summary_rows.append((cand, n_pass, len(results), mean_findings))
        print(f"{cand}: {n_pass}/{len(results)} gate-clean, mean findings {mean_findings}")

    lines = [
        "# Bake-off results — deterministic gates, graded " + __import__("time").strftime("%Y-%m-%d %H:%M UTC", __import__("time").gmtime()),
        "",
        "| Candidate | Gate-clean | Mean blocking findings |",
        "|---|---|---|",
    ]
    for cand, n_pass, n_total, mean_f in summary_rows:
        lines.append(f"| {cand} | {n_pass}/{n_total} | {mean_f} |")
    (grades_dir / "RESULTS.md").write_text("\n".join(lines) + "\n")
    print(f"written: {grades_dir}/RESULTS.md")


if __name__ == "__main__":
    main()
