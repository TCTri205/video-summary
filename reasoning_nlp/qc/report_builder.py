from __future__ import annotations

from typing import Any


def build_quality_report(
    run_id: str,
    input_profile: str,
    stage_results: list[dict[str, Any]],
    metrics: dict[str, Any],
    warnings: list[str],
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    any_fail = any(x.get("status") == "fail" for x in stage_results)
    overall_status = "fail" if any_fail else "pass"
    return {
        "schema_version": "1.1",
        "run_id": run_id,
        "input_profile": input_profile,
        "overall_status": overall_status,
        "stage_results": stage_results,
        "metrics": metrics,
        "warnings": warnings,
        "errors": errors,
    }
