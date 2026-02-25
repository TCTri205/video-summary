from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


def _iter_reports(artifacts_root: Path) -> list[Path]:
    reports: list[Path] = []
    for run_dir in sorted(artifacts_root.glob("*")):
        report_path = run_dir / "g8_qc" / "quality_report.json"
        if report_path.exists() and report_path.is_file():
            reports.append(report_path)
    return reports


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(statistics.mean(values))


def _bool_rate(values: list[bool]) -> float:
    if not values:
        return 0.0
    return float(sum(1 for v in values if v)) / float(len(values))


def summarize_reports(report_paths: list[Path]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for path in report_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        metrics = payload.get("metrics", {}) if isinstance(payload, dict) else {}
        rows.append(
            {
                "run_id": payload.get("run_id", path.parent.parent.name),
                "overall_status": payload.get("overall_status", "unknown"),
                "parse_validity_rate": float(metrics.get("parse_validity_rate", 0.0)),
                "timeline_consistency_score": float(metrics.get("timeline_consistency_score", 0.0)),
                "grounding_score": float(metrics.get("grounding_score", 0.0)),
                "duration_match_score": float(metrics.get("duration_match_score", 0.0)),
                "black_frame_ratio": float(metrics.get("black_frame_ratio", 1.0)),
                "no_match_rate": float(metrics.get("no_match_rate", 1.0)),
                "median_confidence": float(metrics.get("median_confidence", 0.0)),
                "high_confidence_ratio": float(metrics.get("high_confidence_ratio", 0.0)),
                "render_success": bool(metrics.get("render_success", False)),
                "audio_present": bool(metrics.get("audio_present", False)),
            }
        )

    summary = {
        "num_runs": len(rows),
        "pass_rate": _bool_rate([r["overall_status"] == "pass" for r in rows]),
        "render_success_rate": _bool_rate([r["render_success"] for r in rows]),
        "audio_present_rate": _bool_rate([r["audio_present"] for r in rows]),
        "avg_parse_validity_rate": _mean([r["parse_validity_rate"] for r in rows]),
        "avg_timeline_consistency_score": _mean([r["timeline_consistency_score"] for r in rows]),
        "avg_grounding_score": _mean([r["grounding_score"] for r in rows]),
        "avg_duration_match_score": _mean([r["duration_match_score"] for r in rows]),
        "avg_black_frame_ratio": _mean([r["black_frame_ratio"] for r in rows]),
        "avg_no_match_rate": _mean([r["no_match_rate"] for r in rows]),
        "avg_median_confidence": _mean([r["median_confidence"] for r in rows]),
        "avg_high_confidence_ratio": _mean([r["high_confidence_ratio"] for r in rows]),
    }
    return {
        "summary": summary,
        "runs": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate KPI from quality_report.json artifacts")
    parser.add_argument("--artifacts-root", type=Path, default=Path("artifacts"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/kpi_batch_report.json"))
    args = parser.parse_args()

    report_paths = _iter_reports(args.artifacts_root)
    if not report_paths:
        print("No quality reports found")
        return 1

    result = summarize_reports(report_paths)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote KPI report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
