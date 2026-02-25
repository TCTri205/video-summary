#!/usr/bin/env python3
"""
Validate Module 3 artifacts with:
1) JSON Schema checks
2) Cross-file consistency checks
3) QA gate threshold checks (optional)

Usage example:
python docs/Reasoning-NLP/schema/validate_artifacts.py \
  --alignment docs/Reasoning-NLP/schema/examples/alignment_result.valid.json \
  --script docs/Reasoning-NLP/schema/examples/summary_script.valid.json \
  --manifest docs/Reasoning-NLP/schema/examples/summary_video_manifest.valid.json \
  --report docs/Reasoning-NLP/schema/examples/quality_report.valid.json \
  --contracts-dir contracts/v1/template \
  --source-duration-ms 200000 \
  --enforce-thresholds

By default:
- summary_script + summary_video_manifest are validated against contracts/v1/template (global contract location in this repo).
- alignment_result + quality_report are validated against local internal schemas.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import jsonschema
except Exception:
    jsonschema = None


TIMESTAMP_RE = re.compile(r"^\d{2}:[0-5]\d:[0-5]\d\.\d{3}$")


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def to_ms(ts: str) -> int:
    if not TIMESTAMP_RE.match(ts):
        raise ValueError(f"Invalid timestamp format: {ts}")
    hh = int(ts[0:2])
    mm = int(ts[3:5])
    ss = int(ts[6:8])
    ms = int(ts[9:12])
    return (((hh * 60) + mm) * 60 + ss) * 1000 + ms


def validate_schema(data: Dict[str, Any], schema: Dict[str, Any], name: str) -> List[str]:
    if jsonschema is None:
        return [
            "jsonschema package is not installed; schema validation skipped. "
            "Install with: pip install jsonschema"
        ]
    errors = []
    validator = jsonschema.Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(data), key=lambda e: str(e.path)):
        loc = ".".join(str(x) for x in err.path) or "<root>"
        errors.append(f"[{name}] {loc}: {err.message}")
    return errors


def check_unique_segment_ids(items: List[Dict[str, Any]], field: str, label: str) -> List[str]:
    seen = set()
    errors = []
    for i, item in enumerate(items):
        val = item.get(field)
        if val in seen:
            errors.append(f"[{label}] duplicate {field}={val} at index {i}")
        seen.add(val)
    return errors


def check_time_order(segments: List[Dict[str, Any]], label: str) -> List[str]:
    errors = []
    for i, seg in enumerate(segments):
        start = seg.get("source_start")
        end = seg.get("source_end")
        try:
            if not isinstance(start, str) or not isinstance(end, str):
                raise ValueError("source_start/source_end must be strings")
            s_ms = to_ms(start)
            e_ms = to_ms(end)
            if e_ms <= s_ms:
                errors.append(f"[{label}] segment index {i}: source_end must be > source_start")
        except Exception as exc:
            errors.append(f"[{label}] segment index {i}: {exc}")
    return errors


def check_role_coverage(script_segments: List[Dict[str, Any]]) -> List[str]:
    required = {"setup", "development", "resolution"}
    present = {seg.get("role") for seg in script_segments}
    missing = required - present
    return [f"[cross] missing required role: {x}" for x in sorted(missing)]


def check_segment_duration_policy(script_segments: List[Dict[str, Any]]) -> List[str]:
    errors = []
    for i, seg in enumerate(script_segments):
        start = seg.get("source_start")
        end = seg.get("source_end")
        if not isinstance(start, str) or not isinstance(end, str):
            errors.append(f"[cross] segment index {i} missing valid source_start/source_end")
            continue
        s_ms = to_ms(start)
        e_ms = to_ms(end)
        dur = e_ms - s_ms
        if dur < 1200:
            errors.append(f"[cross] segment_id={seg.get('segment_id')} duration {dur}ms < 1200ms")
        if dur > 15000:
            errors.append(f"[cross] segment_id={seg.get('segment_id')} duration {dur}ms > 15000ms")
        curr_id = seg.get("segment_id")
        prev_id = script_segments[i - 1].get("segment_id") if i > 0 else None
        if i > 0 and isinstance(curr_id, int) and isinstance(prev_id, int) and curr_id <= prev_id:
            errors.append("[cross] script segments must be strictly increasing by segment_id")
    return errors


def check_manifest_against_script(
    script: Dict[str, Any], manifest: Dict[str, Any], source_duration_ms: int | None, enforce_role_coverage: bool
) -> List[str]:
    errors = []
    script_segments = script.get("segments", [])
    manifest_segments = manifest.get("segments", [])

    errors.extend(check_unique_segment_ids(script_segments, "segment_id", "script"))
    errors.extend(check_unique_segment_ids(manifest_segments, "segment_id", "manifest"))
    errors.extend(check_time_order(script_segments, "script"))
    errors.extend(check_time_order(manifest_segments, "manifest"))
    if enforce_role_coverage:
        errors.extend(check_role_coverage(script_segments))
    errors.extend(check_segment_duration_policy(script_segments))

    script_by_id = {s["segment_id"]: s for s in script_segments}
    for i, m in enumerate(manifest_segments):
        script_ref = m.get("script_ref")
        if script_ref not in script_by_id:
            errors.append(f"[cross] manifest index {i}: script_ref={script_ref} not found in script")
            continue
        s = script_by_id[script_ref]
        if m.get("source_start") != s.get("source_start") or m.get("source_end") != s.get("source_end"):
            errors.append(
                f"[cross] segment_id={m.get('segment_id')} timestamps mismatch between script and manifest"
            )

        if source_duration_ms is not None:
            try:
                start = m.get("source_start")
                end = m.get("source_end")
                if not isinstance(start, str) or not isinstance(end, str):
                    raise ValueError("source_start/source_end must be strings")
                s_ms = to_ms(start)
                e_ms = to_ms(end)
                if s_ms < 0 or e_ms > source_duration_ms:
                    errors.append(
                        f"[cross] segment_id={m.get('segment_id')} out of source duration range 0..{source_duration_ms}"
                    )
            except Exception as exc:
                errors.append(f"[cross] segment_id={m.get('segment_id')} invalid range timestamps: {exc}")
    return errors


def check_quality_report(report: Dict[str, Any], enforce_thresholds: bool) -> List[str]:
    errors = []
    stage_results = report.get("stage_results", [])
    statuses = [x.get("status") for x in stage_results]
    any_fail = any(s == "fail" for s in statuses)
    overall = report.get("overall_status")
    if any_fail and overall != "fail":
        errors.append("[quality_report] overall_status must be fail when any stage fails")
    if (not any_fail) and overall != "pass":
        errors.append("[quality_report] overall_status must be pass when all stages pass/skipped")

    required_stages = {"validate", "align", "context_build", "summarize", "segment_plan", "manifest", "assemble", "qc"}
    present_stages = {x.get("stage") for x in stage_results}
    missing = required_stages - present_stages
    for m in sorted(missing):
        errors.append(f"[quality_report] missing stage result: {m}")

    metrics = report.get("metrics", {})
    if enforce_thresholds:
        threshold_checks: List[Tuple[str, bool, str]] = [
            ("parse_validity_rate", metrics.get("parse_validity_rate", 0) >= 0.995, ">= 0.995"),
            ("timeline_consistency_score", metrics.get("timeline_consistency_score", 0) >= 0.90, ">= 0.90"),
            ("grounding_score", metrics.get("grounding_score", 0) >= 0.85, ">= 0.85"),
            ("manifest_consistency_pass", metrics.get("manifest_consistency_pass") is True, "== true"),
            ("render_success", metrics.get("render_success") is True, "== true"),
            ("audio_present", metrics.get("audio_present") is True, "== true"),
            ("black_frame_ratio", metrics.get("black_frame_ratio", 1) <= 0.02, "<= 0.02"),
            ("no_match_rate", metrics.get("no_match_rate", 1) <= 0.30, "<= 0.30"),
            ("median_confidence", metrics.get("median_confidence", 0) >= 0.60, ">= 0.60"),
            ("high_confidence_ratio", metrics.get("high_confidence_ratio", 0) >= 0.50, ">= 0.50"),
        ]
        for metric, ok, expect in threshold_checks:
            if not ok:
                errors.append(f"[quality_report] metric {metric} failed threshold ({expect})")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Module 3 artifacts")
    parser.add_argument("--alignment", required=True, type=Path)
    parser.add_argument("--script", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--schema-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--contracts-dir", type=Path, default=None)
    parser.add_argument("--use-internal-summary-schemas", action="store_true")
    parser.add_argument("--source-duration-ms", type=int, default=None)
    parser.add_argument("--enforce-thresholds", action="store_true")
    args = parser.parse_args()

    alignment = load_json(args.alignment)
    script = load_json(args.script)
    manifest = load_json(args.manifest)
    report = load_json(args.report)

    schema_alignment = load_json(args.schema_dir / "alignment_result.schema.json")
    schema_report = load_json(args.schema_dir / "quality_report.schema.json")

    if args.use_internal_summary_schemas:
        schema_script = load_json(args.schema_dir / "summary_script.internal.schema.json")
        schema_manifest = load_json(args.schema_dir / "summary_video_manifest.internal.schema.json")
    else:
        if args.contracts_dir is None:
            repo_root = Path(__file__).resolve().parents[3]
            contracts_dir = repo_root / "contracts" / "v1" / "template"
        else:
            contracts_dir = args.contracts_dir
        schema_script = load_json(contracts_dir / "summary_script.schema.json")
        schema_manifest = load_json(contracts_dir / "summary_video_manifest.schema.json")

    errors: List[str] = []
    warnings: List[str] = []

    for name, data, schema in [
        ("alignment_result", alignment, schema_alignment),
        ("summary_script", script, schema_script),
        ("summary_video_manifest", manifest, schema_manifest),
        ("quality_report", report, schema_report),
    ]:
        result = validate_schema(data, schema, name)
        if result and "schema validation skipped" in result[0]:
            warnings.extend(result)
        else:
            errors.extend(result)

    errors.extend(
        check_manifest_against_script(
            script,
            manifest,
            args.source_duration_ms,
            enforce_role_coverage=args.use_internal_summary_schemas,
        )
    )
    errors.extend(check_quality_report(report, args.enforce_thresholds))

    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"- {w}")

    if errors:
        print("Validation failed:")
        for e in errors:
            print(f"- {e}")
        return 1

    print("Validation passed: schema + cross-file + quality checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
