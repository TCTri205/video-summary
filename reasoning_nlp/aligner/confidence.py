from __future__ import annotations


def compute_confidence(fallback_type: str, distance_ms: int, delta_ms: int) -> float:
    if delta_ms <= 0:
        return 0.0
    containment_bonus = 0.45 if fallback_type == "containment" else 0.0
    distance_score = max(0.0, 1.0 - (float(distance_ms) / float(delta_ms))) * 0.45
    score = containment_bonus + distance_score
    if fallback_type == "no_match":
        score = 0.0
    return max(0.0, min(1.0, round(score, 6)))


def bucketize_confidence(value: float) -> str:
    if value >= 0.75:
        return "high"
    if value >= 0.45:
        return "medium"
    return "low"
