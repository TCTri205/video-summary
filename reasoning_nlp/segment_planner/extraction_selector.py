from __future__ import annotations

from dataclasses import dataclass

from reasoning_nlp.common.errors import fail
from reasoning_nlp.common.text_safety import looks_like_cta
from reasoning_nlp.common.timecode import ms_to_timestamp, to_ms
from reasoning_nlp.segment_planner.role_coverage import assign_role
from reasoning_nlp.summarizer.leakage_guard import is_raw_text_unsafe_for_script


@dataclass(frozen=True)
class ExtractionSegment:
    segment_id: int
    source_start: str
    source_end: str
    script_text: str
    confidence: float
    role: str


@dataclass(frozen=True)
class CandidateSegment:
    start_ms: int
    end_ms: int
    score: float
    confidence: float
    script_text: str


def select_segments_from_extraction_boundaries(
    context_blocks: list[dict[str, object]],
    scene_timestamps_ms: list[int],
    source_duration_ms: int,
    summary_plot: str,
    *,
    min_candidate_segment_ms: int,
    max_selected_segments: int,
    min_total_duration_ms: int | None,
    max_total_duration_ms: int | None,
) -> list[ExtractionSegment]:
    if source_duration_ms <= 0:
        raise fail("segment_plan", "TIME_SOURCE_VIDEO_INVALID", "source_duration_ms must be > 0")

    boundaries = _build_boundaries(scene_timestamps_ms, source_duration_ms)
    candidates = _build_candidates(
        boundaries=boundaries,
        context_blocks=context_blocks,
        summary_plot=summary_plot,
        min_candidate_segment_ms=max(1, int(min_candidate_segment_ms)),
    )
    if not candidates:
        fallback_text = _safe_text(summary_plot) or "Không đủ dữ liệu để dựng đoạn tóm tắt."
        candidates = [
            CandidateSegment(
                start_ms=0,
                end_ms=source_duration_ms,
                score=0.0,
                confidence=0.0,
                script_text=fallback_text,
            )
        ]

    picked = _pick_candidates(
        candidates=candidates,
        max_selected=max(1, int(max_selected_segments)),
        min_total_duration_ms=min_total_duration_ms,
        max_total_duration_ms=max_total_duration_ms,
    )
    if not picked:
        raise fail("segment_plan", "BUDGET_SEGMENTS_EMPTY", "No extraction-based segment selected")

    output: list[ExtractionSegment] = []
    for idx, seg in enumerate(picked, start=1):
        output.append(
            ExtractionSegment(
                segment_id=idx,
                source_start=ms_to_timestamp(seg.start_ms),
                source_end=ms_to_timestamp(seg.end_ms),
                script_text=seg.script_text,
                confidence=max(0.0, min(1.0, float(seg.confidence))),
                role=assign_role(idx - 1, len(picked)),
            )
        )
    return output


def _build_boundaries(scene_timestamps_ms: list[int], source_duration_ms: int) -> list[int]:
    clipped = [x for x in scene_timestamps_ms if 0 < int(x) < source_duration_ms]
    unique_sorted = sorted(set(int(x) for x in clipped))
    return [0, *unique_sorted, source_duration_ms]


def _build_candidates(
    boundaries: list[int],
    context_blocks: list[dict[str, object]],
    summary_plot: str,
    min_candidate_segment_ms: int,
) -> list[CandidateSegment]:
    candidates: list[CandidateSegment] = []
    for idx in range(len(boundaries) - 1):
        start_ms = boundaries[idx]
        end_ms = boundaries[idx + 1]
        if end_ms - start_ms < min_candidate_segment_ms:
            continue
        seg_blocks = _blocks_in_range(context_blocks, start_ms, end_ms)
        confidence = _segment_confidence(seg_blocks)
        script_text = _segment_script_text(seg_blocks, summary_plot)
        score = _segment_score(seg_blocks, confidence, script_text)
        candidates.append(
            CandidateSegment(
                start_ms=start_ms,
                end_ms=end_ms,
                score=score,
                confidence=confidence,
                script_text=script_text,
            )
        )
    return candidates


def _pick_candidates(
    candidates: list[CandidateSegment],
    max_selected: int,
    min_total_duration_ms: int | None,
    max_total_duration_ms: int | None,
) -> list[CandidateSegment]:
    ordered = sorted(candidates, key=lambda x: (-x.score, x.start_ms, x.end_ms))
    selected: list[CandidateSegment] = []
    total_ms = 0
    hard_cap = int(max_total_duration_ms) if max_total_duration_ms is not None else None

    for candidate in ordered:
        if len(selected) >= max_selected:
            break
        duration = candidate.end_ms - candidate.start_ms
        if hard_cap is not None and hard_cap > 0 and (total_ms + duration) > hard_cap:
            continue
        selected.append(candidate)
        total_ms += duration

    if not selected:
        selected = [ordered[0]]
        total_ms = selected[0].end_ms - selected[0].start_ms

    min_total = int(min_total_duration_ms) if min_total_duration_ms is not None else None
    if min_total is not None and min_total > 0 and total_ms < min_total:
        selected_set = {(x.start_ms, x.end_ms) for x in selected}
        timeline = sorted(candidates, key=lambda x: (x.start_ms, x.end_ms))
        for candidate in timeline:
            if len(selected) >= max_selected:
                break
            key = (candidate.start_ms, candidate.end_ms)
            if key in selected_set:
                continue
            duration = candidate.end_ms - candidate.start_ms
            if hard_cap is not None and hard_cap > 0 and (total_ms + duration) > hard_cap:
                continue
            selected.append(candidate)
            selected_set.add(key)
            total_ms += duration
            if total_ms >= min_total:
                break

    selected = sorted(selected, key=lambda x: (x.start_ms, x.end_ms))
    return selected


def _blocks_in_range(context_blocks: list[dict[str, object]], start_ms: int, end_ms: int) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for block in context_blocks:
        ts_raw = block.get("timestamp")
        if not isinstance(ts_raw, str):
            continue
        try:
            ts_ms = to_ms(ts_raw)
        except Exception:
            continue
        if start_ms <= ts_ms < end_ms:
            result.append(block)
    return result


def _segment_confidence(blocks: list[dict[str, object]]) -> float:
    if not blocks:
        return 0.0
    vals: list[float] = []
    for block in blocks:
        try:
            vals.append(float(block.get("confidence", 0.0)))
        except Exception:
            vals.append(0.0)
    if not vals:
        return 0.0
    return max(0.0, min(1.0, sum(vals) / len(vals)))


def _segment_script_text(blocks: list[dict[str, object]], summary_plot: str) -> str:
    parts: list[str] = []
    for block in blocks:
        for field in ("dialogue_text", "image_text"):
            raw = str(block.get(field, "")).strip()
            safe = _safe_text(raw)
            if not safe:
                continue
            if safe.lower() == "(khong co)":
                continue
            parts.append(safe)
    if parts:
        merged = " ".join(parts)
        merged = " ".join(merged.split())
        if len(merged) > 320:
            merged = merged[:317].rstrip() + "..."
        return merged

    safe_plot = _safe_text(summary_plot)
    if safe_plot:
        return safe_plot
    return "Không đủ dữ liệu để dựng đoạn tóm tắt."


def _segment_score(blocks: list[dict[str, object]], confidence: float, script_text: str) -> float:
    fallback_boost = 0.0
    for block in blocks:
        fb = str(block.get("fallback_type", "")).strip().lower()
        if fb == "exact":
            fallback_boost += 0.06
        elif fb == "containment":
            fallback_boost += 0.03
        elif fb == "nearest":
            fallback_boost -= 0.04
        elif fb == "no_match":
            fallback_boost -= 0.08
    text_penalty = -0.25 if looks_like_cta(script_text) else 0.0
    richness_bonus = 0.06 if len(script_text.split()) >= 6 else 0.0
    return float(confidence + fallback_boost + text_penalty + richness_bonus)


def _safe_text(text: str) -> str:
    normalized = " ".join(str(text or "").split()).strip()
    if not normalized:
        return ""
    if is_raw_text_unsafe_for_script(normalized):
        return ""
    return normalized
