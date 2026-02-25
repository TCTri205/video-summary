from __future__ import annotations

import statistics

from reasoning_nlp.common.timecode import to_ms


def compute_alignment_metrics(alignment_payload: dict) -> dict[str, float]:
    blocks = alignment_payload.get("blocks", [])
    if not isinstance(blocks, list) or not blocks:
        return {
            "no_match_rate": 1.0,
            "median_confidence": 0.0,
            "high_confidence_ratio": 0.0,
        }

    confidences = [float(b.get("confidence", 0.0)) for b in blocks]
    no_match_count = sum(1 for b in blocks if b.get("fallback_type") == "no_match")
    high_count = sum(1 for c in confidences if c >= 0.75)
    total = len(blocks)

    return {
        "no_match_rate": no_match_count / total,
        "median_confidence": float(statistics.median(confidences)),
        "high_confidence_ratio": high_count / total,
    }


def compute_timeline_consistency(script_payload: dict, manifest_payload: dict) -> float:
    script = script_payload.get("segments", [])
    manifest = manifest_payload.get("segments", [])
    if not isinstance(script, list) or not isinstance(manifest, list) or len(script) == 0:
        return 0.0
    if len(script) != len(manifest):
        return 0.0
    matches = 0
    for s, m in zip(script, manifest):
        if s.get("source_start") == m.get("source_start") and s.get("source_end") == m.get("source_end"):
            matches += 1
    return matches / len(script)


def compute_compression_ratio(script_payload: dict, source_duration_ms: int | None) -> float:
    if source_duration_ms is None or source_duration_ms <= 0:
        return 0.0
    segments = script_payload.get("segments", [])
    if not isinstance(segments, list) or not segments:
        return 0.0
    total = 0
    for seg in segments:
        try:
            total += to_ms(str(seg.get("source_end"))) - to_ms(str(seg.get("source_start")))
        except Exception:
            continue
    return max(0.0, float(total) / float(source_duration_ms))
