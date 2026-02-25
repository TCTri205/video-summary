from __future__ import annotations

from typing import Any


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
        fixed["generation_meta"] = {"model": "unknown", "seed": 0, "temperature": 0.1}

    fixed["schema_version"] = "1.1"
    return fixed
