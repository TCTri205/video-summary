from __future__ import annotations

from dataclasses import dataclass

from reasoning_nlp.common.errors import fail
from reasoning_nlp.common.text_safety import looks_like_cta
from reasoning_nlp.common.timecode import ms_to_timestamp, to_ms
from reasoning_nlp.segment_planner.budget_policy import (
    BudgetConfig,
    compute_budget_window_ms,
    compute_effective_target_total_ms,
    validate_total_duration,
)
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
    start_idx: int
    end_idx: int
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
    target_ratio: float | None,
    target_ratio_tolerance: float,
) -> list[ExtractionSegment]:
    if source_duration_ms <= 0:
        raise fail("segment_plan", "TIME_SOURCE_VIDEO_INVALID", "source_duration_ms must be > 0")

    boundaries = _build_boundaries(scene_timestamps_ms, source_duration_ms)
    budget = BudgetConfig(
        min_segment_duration_ms=max(1, int(min_candidate_segment_ms)),
        max_segment_duration_ms=max(1, source_duration_ms),
        min_total_duration_ms=min_total_duration_ms,
        max_total_duration_ms=max_total_duration_ms,
        target_ratio=target_ratio,
        target_ratio_tolerance=target_ratio_tolerance,
    )
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
                start_idx=0,
                end_idx=max(1, len(boundaries) - 1),
                start_ms=0,
                end_ms=source_duration_ms,
                score=0.0,
                confidence=0.0,
                script_text=fallback_text,
            )
        ]

    picked = _pick_candidates(
        candidates=candidates,
        boundaries=boundaries,
        context_blocks=context_blocks,
        summary_plot=summary_plot,
        budget=budget,
        max_selected=max(1, int(max_selected_segments)),
    )
    if not picked:
        raise fail("segment_plan", "BUDGET_SEGMENTS_EMPTY", "No extraction-based segment selected")
    total_duration_ms = sum(seg.end_ms - seg.start_ms for seg in picked)
    budget_errors = validate_total_duration(total_duration_ms, source_duration_ms, budget)
    if budget_errors:
        raise fail("segment_plan", budget_errors[0], "Selected extraction-based segments violate duration budget")

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
                start_idx=idx,
                end_idx=idx + 1,
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
    boundaries: list[int],
    context_blocks: list[dict[str, object]],
    summary_plot: str,
    budget: BudgetConfig,
    max_selected: int,
) -> list[CandidateSegment]:
    if not candidates:
        return []

    target_ms, lower_ms, upper_ms = compute_budget_window_ms(boundaries[-1], budget)
    if target_ms is None:
        target_ms = compute_effective_target_total_ms(boundaries[-1], budget)
    if target_ms is None:
        target_ms = int(budget.min_total_duration_ms or max(1, candidates[0].end_ms - candidates[0].start_ms))
    if lower_ms is None:
        lower_ms = int(budget.min_total_duration_ms or target_ms)
    if upper_ms is None:
        upper_ms = int(budget.max_total_duration_ms or max(target_ms, lower_ms))
    upper_ms = max(lower_ms, upper_ms)

    selected = _select_subset_to_budget(candidates, target_ms=target_ms, lower_ms=lower_ms, upper_ms=upper_ms, max_selected=max_selected)
    if not selected:
        selected = [max(candidates, key=lambda x: (x.score, -(x.end_ms - x.start_ms), -x.start_ms))]

    selected = _expand_selected_ranges(
        selected=selected,
        interval_candidates=candidates,
        boundaries=boundaries,
        context_blocks=context_blocks,
        summary_plot=summary_plot,
        lower_ms=lower_ms,
        target_ms=target_ms,
        upper_ms=upper_ms,
    )

    selected = sorted(selected, key=lambda x: (x.start_ms, x.end_ms))
    return selected


def _select_subset_to_budget(
    candidates: list[CandidateSegment],
    *,
    target_ms: int,
    lower_ms: int,
    upper_ms: int,
    max_selected: int,
) -> list[CandidateSegment]:
    quantum_ms = 250
    duration_cap_ms = max(upper_ms, target_ms, 1)
    max_units = max(1, (duration_cap_ms + quantum_ms - 1) // quantum_ms)
    states: dict[tuple[int, int], tuple[float, tuple[int, ...]]] = {(0, 0): (0.0, tuple())}

    for idx, candidate in enumerate(candidates):
        duration_ms = candidate.end_ms - candidate.start_ms
        if duration_ms <= 0:
            continue
        duration_units = max(1, (duration_ms + quantum_ms - 1) // quantum_ms)
        next_states = dict(states)
        for (count, used_units), (score, picks) in states.items():
            next_count = count + 1
            next_units = used_units + duration_units
            if next_count > max_selected or next_units > max_units:
                continue
            current = next_states.get((next_count, next_units))
            next_value = (score + float(candidate.score), picks + (idx,))
            if current is None or _state_score(next_value, candidates, quantum_ms, target_ms, lower_ms, upper_ms) > _state_score(
                current,
                candidates,
                quantum_ms,
                target_ms,
                lower_ms,
                upper_ms,
            ):
                next_states[(next_count, next_units)] = next_value
        states = next_states

    best_picks: tuple[int, ...] = tuple()
    best_rank: tuple[int, int, float, int] | None = None
    for (count, units), state in states.items():
        if count <= 0:
            continue
        total_ms = sum(candidates[idx].end_ms - candidates[idx].start_ms for idx in state[1])
        if total_ms > upper_ms:
            continue
        rank = _selection_rank(total_ms=total_ms, score=state[0], count=count, target_ms=target_ms, lower_ms=lower_ms, upper_ms=upper_ms)
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_picks = state[1]

    return [candidates[idx] for idx in best_picks]


def _state_score(
    state: tuple[float, tuple[int, ...]],
    candidates: list[CandidateSegment],
    quantum_ms: int,
    target_ms: int,
    lower_ms: int,
    upper_ms: int,
) -> tuple[int, int, float]:
    total_ms = sum(candidates[idx].end_ms - candidates[idx].start_ms for idx in state[1])
    return _selection_rank(
        total_ms=total_ms,
        score=state[0],
        count=len(state[1]),
        target_ms=target_ms,
        lower_ms=lower_ms,
        upper_ms=upper_ms,
    )[:3]


def _selection_rank(*, total_ms: int, score: float, count: int, target_ms: int, lower_ms: int, upper_ms: int) -> tuple[int, int, float, int]:
    in_window = 1 if lower_ms <= total_ms <= upper_ms else 0
    delta = abs(target_ms - total_ms)
    return (in_window, -delta, float(score), -count)


def _expand_selected_ranges(
    *,
    selected: list[CandidateSegment],
    interval_candidates: list[CandidateSegment],
    boundaries: list[int],
    context_blocks: list[dict[str, object]],
    summary_plot: str,
    lower_ms: int,
    target_ms: int,
    upper_ms: int,
) -> list[CandidateSegment]:
    if not selected:
        return selected

    interval_map = {seg.start_idx: seg for seg in interval_candidates if seg.end_idx == seg.start_idx + 1}
    ranges = sorted([(seg.start_idx, seg.end_idx) for seg in selected], key=lambda item: item[0])
    total_ms = sum(boundaries[end] - boundaries[start] for start, end in ranges)

    while total_ms < lower_ms:
        best_option: tuple[tuple[int, int, int], list[tuple[int, int]]] | None = None
        for idx, (start_idx, end_idx) in enumerate(ranges):
            left_idx = start_idx - 1
            if left_idx >= 0 and left_idx not in {r_end - 1 for _, r_end in ranges[:idx]}:
                updated = list(ranges)
                updated[idx] = (left_idx, end_idx)
                merged = _merge_ranges(updated)
                new_total = sum(boundaries[end] - boundaries[start] for start, end in merged)
                if new_total <= upper_ms and left_idx in interval_map:
                    score = interval_map[left_idx].score
                    rank = _expansion_rank(new_total=new_total, added_score=score, target_ms=target_ms, lower_ms=lower_ms)
                    if best_option is None or rank > best_option[0]:
                        best_option = (rank, merged)
            right_idx = end_idx
            if right_idx < len(boundaries) - 1 and right_idx not in {r_start for r_start, _ in ranges[idx + 1:]}:
                updated = list(ranges)
                updated[idx] = (start_idx, right_idx + 1)
                merged = _merge_ranges(updated)
                new_total = sum(boundaries[end] - boundaries[start] for start, end in merged)
                if new_total <= upper_ms and right_idx in interval_map:
                    score = interval_map[right_idx].score
                    rank = _expansion_rank(new_total=new_total, added_score=score, target_ms=target_ms, lower_ms=lower_ms)
                    if best_option is None or rank > best_option[0]:
                        best_option = (rank, merged)
        if best_option is None:
            break
        ranges = best_option[1]
        total_ms = sum(boundaries[end] - boundaries[start] for start, end in ranges)

    expanded = [
        _candidate_from_range(
            boundaries=boundaries,
            context_blocks=context_blocks,
            summary_plot=summary_plot,
            start_idx=start_idx,
            end_idx=end_idx,
        )
        for start_idx, end_idx in ranges
    ]
    expanded = [seg for seg in expanded if seg is not None]
    if not expanded:
        return selected
    return expanded


def _expansion_rank(*, new_total: int, added_score: float, target_ms: int, lower_ms: int) -> tuple[int, int, float]:
    reaches_window = 1 if new_total >= lower_ms else 0
    return (reaches_window, -abs(target_ms - new_total), float(added_score))


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not ranges:
        return []
    ordered = sorted(ranges, key=lambda item: (item[0], item[1]))
    merged: list[tuple[int, int]] = [ordered[0]]
    for start_idx, end_idx in ordered[1:]:
        last_start, last_end = merged[-1]
        if start_idx <= last_end:
            merged[-1] = (last_start, max(last_end, end_idx))
        else:
            merged.append((start_idx, end_idx))
    return merged


def _candidate_from_range(
    *,
    boundaries: list[int],
    context_blocks: list[dict[str, object]],
    summary_plot: str,
    start_idx: int,
    end_idx: int,
) -> CandidateSegment | None:
    start_ms = boundaries[start_idx]
    end_ms = boundaries[end_idx]
    if end_ms <= start_ms:
        return None
    seg_blocks = _blocks_in_range(context_blocks, start_ms, end_ms)
    confidence = _segment_confidence(seg_blocks)
    script_text = _segment_script_text(seg_blocks, summary_plot)
    score = _segment_score(seg_blocks, confidence, script_text)
    return CandidateSegment(
        start_idx=start_idx,
        end_idx=end_idx,
        start_ms=start_ms,
        end_ms=end_ms,
        score=score,
        confidence=confidence,
        script_text=script_text,
    )


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
