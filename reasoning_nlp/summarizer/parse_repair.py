from __future__ import annotations

from typing import Any

from reasoning_nlp.summarizer.leakage_guard import scrub_llm_generated_text


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

    leak_repaired = False

    raw_title = str(fixed.get("title", "Video Summary")).strip() or "Video Summary"
    title_clean, title_was_repaired = scrub_llm_generated_text(raw_title)
    leak_repaired = leak_repaired or title_was_repaired
    fixed["title"] = title_clean or "Video Summary"

    raw_plot_summary = str(fixed.get("plot_summary", "")).strip()
    plot_clean, plot_was_repaired = scrub_llm_generated_text(raw_plot_summary)
    leak_repaired = leak_repaired or plot_was_repaired
    fixed["plot_summary"] = plot_clean or "Không đủ dữ liệu để tóm tắt."

    raw_moral_lesson = str(fixed.get("moral_lesson", "")).strip()
    moral_clean, moral_was_repaired = scrub_llm_generated_text(raw_moral_lesson)
    leak_repaired = leak_repaired or moral_was_repaired
    fixed["moral_lesson"] = moral_clean or "Cần đối chiếu thêm bằng chứng."

    evidence = fixed.get("evidence")
    if not isinstance(evidence, list):
        fixed["evidence"] = []
    else:
        repaired_evidence: list[dict[str, Any]] = []
        for item in evidence:
            if not isinstance(item, dict):
                continue
            claim_raw = str(item.get("claim", "")).strip()
            claim_clean, claim_was_repaired = scrub_llm_generated_text(claim_raw)
            leak_repaired = leak_repaired or claim_was_repaired
            timestamps = item.get("timestamps")
            if not isinstance(timestamps, list):
                continue
            clean_timestamps = [str(x) for x in timestamps if str(x).strip()]
            if not claim_clean:
                continue
            if not clean_timestamps:
                continue
            repaired_evidence.append({
                "claim": claim_clean,
                "timestamps": clean_timestamps,
            })
        fixed["evidence"] = repaired_evidence

    quality_flags = fixed.get("quality_flags")
    if not isinstance(quality_flags, list):
        fixed["quality_flags"] = []
    if leak_repaired:
        fixed["quality_flags"] = list(fixed["quality_flags"])
        fixed["quality_flags"].append("PROMPT_LEAKAGE_REPAIRED")
        fixed["quality_flags"] = sorted(set(str(x) for x in fixed["quality_flags"] if str(x).strip()))

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
