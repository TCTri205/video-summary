from __future__ import annotations

import time
from typing import Any


def append_stage_result(
    stage_results: list[dict[str, Any]],
    stage: str,
    status: str,
    started: float,
    error_code: str | None = None,
) -> None:
    duration_ms = int((time.perf_counter() - started) * 1000)
    payload: dict[str, Any] = {
        "stage": stage,
        "status": status,
        "duration_ms": max(0, duration_ms),
    }
    if error_code:
        payload["error_code"] = error_code
    stage_results.append(payload)


def append_stage_skipped(stage_results: list[dict[str, Any]], stage: str) -> None:
    stage_results.append({"stage": stage, "status": "skipped", "duration_ms": 0})


def is_simple_runtime(config: Any) -> bool:
    return str(getattr(config, "runtime_profile", "full")).strip().lower() == "simple"
