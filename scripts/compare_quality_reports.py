from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


_CHECKS = [
    ("timeline_consistency_score", "higher_or_equal"),
    ("grounding_score", "higher_or_equal"),
    ("text_cta_leak_ratio", "lower_or_equal"),
    ("text_video_keyword_overlap", "higher_or_equal"),
    ("text_segment_coverage_ratio", "higher_or_equal"),
]


def _load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid report payload: {path}")
    return payload


def _metric(report: dict[str, Any], name: str) -> float:
    metrics = report.get("metrics", {})
    if not isinstance(metrics, dict):
        return 0.0
    value = metrics.get(name, 0.0)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def compare_reports(baseline: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    out_rows: list[dict[str, Any]] = []
    pass_flags: list[bool] = []

    for metric_name, direction in _CHECKS:
        base_value = _metric(baseline, metric_name)
        variant_value = _metric(variant, metric_name)
        delta = variant_value - base_value

        if direction == "higher_or_equal":
            ok = variant_value >= base_value
        else:
            ok = variant_value <= base_value

        pass_flags.append(ok)
        out_rows.append(
            {
                "metric": metric_name,
                "direction": direction,
                "baseline": round(base_value, 6),
                "variant": round(variant_value, 6),
                "delta": round(delta, 6),
                "pass": ok,
            }
        )

    baseline_status = str(baseline.get("overall_status", "unknown"))
    variant_status = str(variant.get("overall_status", "unknown"))
    strict_status_ok = variant_status == "pass" and baseline_status == "pass"

    return {
        "baseline_run_id": baseline.get("run_id", "unknown"),
        "variant_run_id": variant.get("run_id", "unknown"),
        "baseline_status": baseline_status,
        "variant_status": variant_status,
        "strict_status_ok": strict_status_ok,
        "checks": out_rows,
        "all_checks_pass": all(pass_flags),
        "recommendation": "accept_variant" if strict_status_ok and all(pass_flags) else "keep_baseline",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two quality_report.json files for A/B lexical planner tuning")
    parser.add_argument("--baseline", type=Path, required=True, help="Path to baseline quality_report.json")
    parser.add_argument("--variant", type=Path, required=True, help="Path to variant quality_report.json")
    parser.add_argument("--out", type=Path, default=None, help="Optional output JSON path")
    args = parser.parse_args()

    baseline = _load_report(args.baseline)
    variant = _load_report(args.variant)
    result = compare_reports(baseline, variant)

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote comparison report: {args.out}")
    else:
        print(payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
