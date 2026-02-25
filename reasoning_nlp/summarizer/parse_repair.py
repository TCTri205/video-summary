from __future__ import annotations

from typing import Any


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def repair_internal_summary(payload: dict[str, Any]) -> dict[str, Any]:
    fixed = dict(payload)

    fixed["title"] = str(fixed.get("title", "Video Summary")).strip() or "Video Summary"
    fixed["plot_summary"] = str(fixed.get("plot_summary", "")).strip() or "Khong du du lieu de tom tat."
    fixed["moral_lesson"] = str(fixed.get("moral_lesson", "")).strip() or "Can doi chieu them bang chung."

    evidence = fixed.get("evidence")
    if not isinstance(evidence, list):
        fixed["evidence"] = []

    quality_flags = fixed.get("quality_flags")
    if not isinstance(quality_flags, list):
        fixed["quality_flags"] = []

    generation_meta = fixed.get("generation_meta")
    if not isinstance(generation_meta, dict):
        fixed["generation_meta"] = {
            "model": "unknown",
            "seed": 0,
            "temperature": 0.1,
            "backend": "fallback",
            "retry_count": 0,
            "latency_ms": 0,
            "token_count": 0,
        }
    else:
        fixed["generation_meta"] = {
            "model": str(generation_meta.get("model", "unknown")) or "unknown",
            "seed": _as_int(generation_meta.get("seed", 0), 0),
            "temperature": _as_float(generation_meta.get("temperature", 0.1), 0.1),
            "backend": str(generation_meta.get("backend", "fallback")) or "fallback",
            "retry_count": max(0, _as_int(generation_meta.get("retry_count", 0), 0)),
            "latency_ms": max(0, _as_int(generation_meta.get("latency_ms", 0), 0)),
            "token_count": max(0, _as_int(generation_meta.get("token_count", 0), 0)),
        }

    fixed["schema_version"] = "1.1"
    return fixed
