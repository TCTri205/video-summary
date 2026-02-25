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
import statistics
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


def check_segment_id_strict_increasing(segments: List[Dict[str, Any]], label: str) -> List[str]:
    errors = []
    prev_id = None
    for i, seg in enumerate(segments):
        curr_id = seg.get("segment_id")
        if not isinstance(curr_id, int):
            errors.append(f"[{label}] segment index {i}: segment_id must be integer")
            continue
        if prev_id is not None and curr_id <= prev_id:
            errors.append(f"[{label}] [MANIFEST_SEGMENT_ID_ORDER] segment_id must be strictly increasing")
        prev_id = curr_id
    return errors


def check_non_overlap_monotonic_timeline(segments: List[Dict[str, Any]], label: str) -> List[str]:
    errors = []
    prev_start_ms = None
    prev_end_ms = None
    prev_id = None
    for i, seg in enumerate(segments):
        start = seg.get("source_start")
        end = seg.get("source_end")
        curr_id = seg.get("segment_id")
        if not isinstance(start, str) or not isinstance(end, str):
            errors.append(f"[{label}] segment index {i}: source_start/source_end must be strings")
            continue
        try:
            s_ms = to_ms(start)
            e_ms = to_ms(end)
        except Exception as exc:
            errors.append(f"[{label}] segment index {i}: {exc}")
            continue

        if prev_start_ms is not None and s_ms < prev_start_ms:
            errors.append(
                f"[{label}] [MANIFEST_TIME_ORDER] segment_id={curr_id} source_start must be non-decreasing"
            )
        if prev_end_ms is not None and s_ms < prev_end_ms:
            errors.append(
                f"[{label}] [MANIFEST_OVERLAP] segment_id={curr_id} overlaps previous segment_id={prev_id}"
            )

        prev_start_ms = s_ms
        prev_end_ms = e_ms
        prev_id = curr_id
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


def get_total_duration_ms(segments: List[Dict[str, Any]], label: str) -> Tuple[int | None, List[str]]:
    errors = []
    total = 0
    for i, seg in enumerate(segments):
        start = seg.get("source_start")
        end = seg.get("source_end")
        if not isinstance(start, str) or not isinstance(end, str):
            errors.append(f"[{label}] segment index {i}: source_start/source_end must be strings")
            continue
        try:
            s_ms = to_ms(start)
            e_ms = to_ms(end)
        except Exception as exc:
            errors.append(f"[{label}] segment index {i}: {exc}")
            continue
        total += e_ms - s_ms

    if errors:
        return None, errors
    return total, []


def check_total_duration_budget(
    script_segments: List[Dict[str, Any]],
    source_duration_ms: int | None,
    min_total_duration_ms: int | None,
    max_total_duration_ms: int | None,
    target_ratio: float | None,
    target_ratio_tolerance: float,
) -> List[str]:
    errors = []
    total_duration_ms, duration_errors = get_total_duration_ms(script_segments, "cross")
    errors.extend(duration_errors)
    if total_duration_ms is None:
        return errors

    if min_total_duration_ms is not None and total_duration_ms < min_total_duration_ms:
        errors.append(
            f"[cross] [BUDGET_UNDERFLOW] total duration {total_duration_ms}ms < min_total_duration_ms={min_total_duration_ms}"
        )
    if max_total_duration_ms is not None and total_duration_ms > max_total_duration_ms:
        errors.append(
            f"[cross] [BUDGET_OVERFLOW] total duration {total_duration_ms}ms > max_total_duration_ms={max_total_duration_ms}"
        )

    if target_ratio is not None:
        if source_duration_ms is None:
            errors.append("[cross] [BUDGET_TARGET_RATIO] source_duration_ms is required when target_ratio is set")
            return errors
        expected = source_duration_ms * target_ratio
        delta = expected * target_ratio_tolerance
        lower = expected - delta
        upper = expected + delta
        if total_duration_ms < lower:
            errors.append(
                f"[cross] [BUDGET_UNDERFLOW] total duration {total_duration_ms}ms < target lower bound {int(lower)}ms"
            )
        if total_duration_ms > upper:
            errors.append(
                f"[cross] [BUDGET_OVERFLOW] total duration {total_duration_ms}ms > target upper bound {int(upper)}ms"
            )

    return errors


def check_alignment_block_semantics(alignment: Dict[str, Any]) -> List[str]:
    errors = []
    blocks = alignment.get("blocks", [])
    prev_ts = None
    for i, block in enumerate(blocks):
        ts = block.get("timestamp")
        fallback_type = block.get("fallback_type")
        matched_ids = block.get("matched_transcript_ids")
        dialogue = block.get("dialogue_text")
        confidence = block.get("confidence")

        if not isinstance(ts, str):
            errors.append(f"[alignment] block index {i}: timestamp must be string")
            continue
        try:
            ts_ms = to_ms(ts)
        except Exception as exc:
            errors.append(f"[alignment] block index {i}: {exc}")
            continue

        if prev_ts is not None and ts_ms < prev_ts:
            errors.append("[alignment] [ALIGN_TIME_ORDER] blocks must be sorted by non-decreasing timestamp")
        prev_ts = ts_ms

        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            errors.append(f"[alignment] block index {i}: confidence must be in [0,1]")

        if fallback_type == "no_match":
            if matched_ids:
                errors.append(
                    f"[alignment] [ALIGN_NO_MATCH_CONSISTENCY] block index {i}: no_match must have empty matched_transcript_ids"
                )
            if dialogue != "(khong co)":
                errors.append(
                    f"[alignment] [ALIGN_NO_MATCH_CONSISTENCY] block index {i}: no_match must use dialogue_text='(khong co)'"
                )
        elif fallback_type in {"containment", "nearest"}:
            if not isinstance(matched_ids, list) or len(matched_ids) == 0:
                errors.append(
                    f"[alignment] [ALIGN_MATCH_CONSISTENCY] block index {i}: {fallback_type} must have matched_transcript_ids"
                )
        else:
            errors.append(f"[alignment] block index {i}: unknown fallback_type={fallback_type}")

    return errors


def recompute_alignment_metrics(alignment: Dict[str, Any]) -> Tuple[Dict[str, float], List[str]]:
    errors = []
    blocks = alignment.get("blocks")
    if not isinstance(blocks, list) or len(blocks) == 0:
        return {}, ["[alignment] [ALIGN_BLOCKS_EMPTY] blocks must be a non-empty array"]

    confidences: List[float] = []
    no_match_count = 0
    high_conf_count = 0

    for i, block in enumerate(blocks):
        confidence = block.get("confidence")
        if not isinstance(confidence, (int, float)):
            errors.append(f"[alignment] block index {i}: confidence must be numeric")
            continue
        c = float(confidence)
        if c < 0 or c > 1:
            errors.append(f"[alignment] block index {i}: confidence out of range [0,1]")
            continue
        confidences.append(c)
        if c >= 0.75:
            high_conf_count += 1
        if block.get("fallback_type") == "no_match":
            no_match_count += 1

    if not confidences:
        errors.append("[alignment] [ALIGN_CONFIDENCE_EMPTY] no valid confidence values")
        return {}, errors

    total = len(blocks)
    metrics = {
        "no_match_rate": no_match_count / total,
        "median_confidence": float(statistics.median(confidences)),
        "high_confidence_ratio": high_conf_count / total,
    }
    return metrics, errors


def check_report_metric_consistency(
    report: Dict[str, Any], recomputed_metrics: Dict[str, float], metric_tolerance: float
) -> List[str]:
    errors = []
    report_metrics = report.get("metrics", {})
    for metric_name, recomputed in recomputed_metrics.items():
        reported = report_metrics.get(metric_name)
        if not isinstance(reported, (int, float)):
            errors.append(f"[quality_report] metric {metric_name} must be numeric")
            continue
        diff = abs(float(reported) - recomputed)
        if diff > metric_tolerance:
            errors.append(
                f"[quality_report] [QC_METRIC_MISMATCH] metric {metric_name} mismatch: "
                f"reported={float(reported):.6f}, recomputed={recomputed:.6f}, tolerance={metric_tolerance:.6f}"
            )
    return errors


def check_manifest_against_script(
    script: Dict[str, Any], manifest: Dict[str, Any], source_duration_ms: int | None, enforce_role_coverage: bool
) -> List[str]:
    errors = []
    script_segments = script.get("segments", [])
    manifest_segments = manifest.get("segments", [])

    errors.extend(check_unique_segment_ids(script_segments, "segment_id", "script"))
    errors.extend(check_unique_segment_ids(manifest_segments, "segment_id", "manifest"))
    errors.extend(check_segment_id_strict_increasing(script_segments, "script"))
    errors.extend(check_segment_id_strict_increasing(manifest_segments, "manifest"))
    errors.extend(check_time_order(script_segments, "script"))
    errors.extend(check_time_order(manifest_segments, "manifest"))
    errors.extend(check_non_overlap_monotonic_timeline(script_segments, "script"))
    errors.extend(check_non_overlap_monotonic_timeline(manifest_segments, "manifest"))
    if enforce_role_coverage:
        errors.extend(check_role_coverage(script_segments))
    errors.extend(check_segment_duration_policy(script_segments))
    errors.extend(check_segment_duration_policy(manifest_segments))

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
    parser.add_argument("--min-total-duration-ms", type=int, default=None)
    parser.add_argument("--max-total-duration-ms", type=int, default=None)
    parser.add_argument("--target-ratio", type=float, default=None)
    parser.add_argument("--target-ratio-tolerance", type=float, default=0.20)
    parser.add_argument("--metric-tolerance", type=float, default=0.02)
    parser.add_argument("--enforce-thresholds", action="store_true")
    args = parser.parse_args()

    if jsonschema is None:
        print("Validation failed:")
        print("- [SCHEMA_ENGINE_MISSING] jsonschema package is not installed. Install with: pip install jsonschema")
        return 2

    if args.min_total_duration_ms is not None and args.min_total_duration_ms < 0:
        print("Validation failed:")
        print("- [ARGUMENT_ERROR] --min-total-duration-ms must be >= 0")
        return 2
    if args.max_total_duration_ms is not None and args.max_total_duration_ms < 0:
        print("Validation failed:")
        print("- [ARGUMENT_ERROR] --max-total-duration-ms must be >= 0")
        return 2
    if (
        args.min_total_duration_ms is not None
        and args.max_total_duration_ms is not None
        and args.min_total_duration_ms > args.max_total_duration_ms
    ):
        print("Validation failed:")
        print("- [ARGUMENT_ERROR] --min-total-duration-ms must be <= --max-total-duration-ms")
        return 2
    if args.target_ratio is not None and not (0 < args.target_ratio <= 1):
        print("Validation failed:")
        print("- [ARGUMENT_ERROR] --target-ratio must be in (0,1]")
        return 2
    if not (0 <= args.target_ratio_tolerance <= 1):
        print("Validation failed:")
        print("- [ARGUMENT_ERROR] --target-ratio-tolerance must be in [0,1]")
        return 2
    if not (0 <= args.metric_tolerance <= 1):
        print("Validation failed:")
        print("- [ARGUMENT_ERROR] --metric-tolerance must be in [0,1]")
        return 2

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

    for name, data, schema in [
        ("alignment_result", alignment, schema_alignment),
        ("summary_script", script, schema_script),
        ("summary_video_manifest", manifest, schema_manifest),
        ("quality_report", report, schema_report),
    ]:
        errors.extend(validate_schema(data, schema, name))

    errors.extend(
        check_manifest_against_script(
            script,
            manifest,
            args.source_duration_ms,
            enforce_role_coverage=args.use_internal_summary_schemas,
        )
    )
    errors.extend(
        check_total_duration_budget(
            script.get("segments", []),
            args.source_duration_ms,
            args.min_total_duration_ms,
            args.max_total_duration_ms,
            args.target_ratio,
            args.target_ratio_tolerance,
        )
    )
    errors.extend(check_alignment_block_semantics(alignment))

    recomputed_metrics, metric_errors = recompute_alignment_metrics(alignment)
    errors.extend(metric_errors)
    if recomputed_metrics:
        errors.extend(check_report_metric_consistency(report, recomputed_metrics, args.metric_tolerance))

    errors.extend(check_quality_report(report, args.enforce_thresholds))

    if errors:
        print("Validation failed:")
        for e in errors:
            print(f"- {e}")
        return 1

    print("Validation passed: schema + cross-file + quality checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
