from __future__ import annotations

from dataclasses import dataclass
import re

from reasoning_nlp.common.errors import fail
from reasoning_nlp.common.timecode import to_ms
from reasoning_nlp.segment_planner.budget_policy import BudgetConfig, validate_segment_duration, validate_total_duration
from reasoning_nlp.segment_planner.role_coverage import assign_role, ensure_role_coverage
from reasoning_nlp.summarizer.leakage_guard import is_raw_text_unsafe_for_script


@dataclass(frozen=True)
class PlannedSegment:
    segment_id: int
    source_start: str
    source_end: str
    script_text: str
    confidence: float
    role: str


def plan_segments_from_context(
    context_blocks: list[dict[str, object]],
    summary_plot: str,
    budget: BudgetConfig,
    source_duration_ms: int | None,
) -> list[PlannedSegment]:
    if not context_blocks:
        raise fail("segment_plan", "BUDGET_NO_CONTEXT", "No context blocks to plan segments")

    total_blocks = len(context_blocks)
    target_total_ms = _compute_target_total_ms(budget, source_duration_ms)
    preferred_segment_ms = _compute_preferred_segment_ms(budget, source_duration_ms)
    target_count = _compute_target_count(
        total_blocks=total_blocks,
        target_total_ms=target_total_ms,
        preferred_segment_ms=preferred_segment_ms,
    )
    picks = _pick_block_indexes(context_blocks, target_count)

    segments: list[PlannedSegment] = []
    total_duration_ms = 0
    prev_end_ms = 0
    for pick_idx, block_index in enumerate(picks):
        block = context_blocks[block_index]
        anchor_ts = str(block.get("timestamp", "00:00:00.000"))
        anchor_ms = to_ms(anchor_ts)

        remaining_slots = max(1, len(picks) - pick_idx)
        remaining_budget_ms = max(0, target_total_ms - total_duration_ms)
        dynamic_target_ms = (
            remaining_budget_ms // remaining_slots if remaining_budget_ms > 0 else preferred_segment_ms
        )
        target_segment_ms = max(budget.min_segment_duration_ms, min(budget.max_segment_duration_ms, dynamic_target_ms))

        start_ms = max(anchor_ms, prev_end_ms)
        end_ms = start_ms + target_segment_ms
        if source_duration_ms is not None and source_duration_ms > 0:
            latest_start_ms = max(prev_end_ms, source_duration_ms - budget.min_segment_duration_ms)
            if start_ms > latest_start_ms:
                start_ms = latest_start_ms
            end_ms = min(end_ms, source_duration_ms)
            if end_ms - start_ms < budget.min_segment_duration_ms:
                start_ms = max(prev_end_ms, source_duration_ms - budget.min_segment_duration_ms)
                end_ms = min(source_duration_ms, start_ms + budget.max_segment_duration_ms)

        duration_ms = end_ms - start_ms
        if not validate_segment_duration(duration_ms, budget):
            continue

        seg_id = len(segments) + 1
        role = assign_role(seg_id - 1, target_count)
        script_text = _script_text_from_block(summary_plot, block)
        confidence = _to_float(block.get("confidence", 0.0))
        segments.append(
            PlannedSegment(
                segment_id=seg_id,
                source_start=_ms_to_ts(start_ms),
                source_end=_ms_to_ts(end_ms),
                script_text=script_text,
                confidence=max(0.0, min(1.0, confidence)),
                role=role,
            )
        )
        total_duration_ms += duration_ms
        prev_end_ms = end_ms

    if not segments:
        raise fail("segment_plan", "BUDGET_SEGMENT_DURATION", "No segments satisfy duration budget")

    if len(segments) != target_count:
        segments = [
            PlannedSegment(
                segment_id=seg.segment_id,
                source_start=seg.source_start,
                source_end=seg.source_end,
                script_text=seg.script_text,
                confidence=seg.confidence,
                role=assign_role(idx, len(segments)),
            )
            for idx, seg in enumerate(segments)
        ]

    budget_errors = validate_total_duration(total_duration_ms, source_duration_ms, budget)
    if budget_errors:
        raise fail("segment_plan", budget_errors[0], "Total duration violates budget policy")

    missing_roles = ensure_role_coverage([s.role for s in segments])
    if len(segments) >= 3 and missing_roles:
        raise fail("segment_plan", "BUDGET_ROLE_COVERAGE", f"Missing roles: {missing_roles}")

    return segments


def _pick_block_indexes(context_blocks: list[dict[str, object]], target_count: int) -> list[int]:
    total_blocks = len(context_blocks)
    if total_blocks == 0:
        return []

    scores = [_score_block(x) for x in context_blocks]
    target = max(1, min(target_count, total_blocks))

    picks: list[int] = []
    seen: set[int] = set()
    min_gap = 1 if target <= 3 else max(1, total_blocks // (target * 3))

    for bucket_idx in range(target):
        start = int((bucket_idx * total_blocks) / target)
        end = int(((bucket_idx + 1) * total_blocks) / target)
        end = max(start + 1, end)

        candidate = _best_in_range_with_diversity(
            total_blocks=total_blocks,
            start=start,
            end=end,
            scores=scores,
            selected=picks,
            min_gap=min_gap,
            exclude=seen,
        )
        if candidate is not None and candidate not in seen:
            picks.append(candidate)
            seen.add(candidate)

    if len(picks) < target:
        ordered = sorted(range(total_blocks), key=lambda i: (-scores[i], i))
        for idx in ordered:
            if idx in seen:
                continue
            if _is_too_close_to_selected(idx, picks, min_gap):
                continue
            picks.append(idx)
            seen.add(idx)
            if len(picks) == target:
                break

    if len(picks) < target:
        ordered = sorted(range(total_blocks), key=lambda i: (-scores[i], i))
        for idx in ordered:
            if idx in seen:
                continue
            picks.append(idx)
            seen.add(idx)
            if len(picks) == target:
                break

    picks = _reduce_cta_candidates(picks, scores, context_blocks, target)
    return sorted(picks)


def _compute_target_total_ms(budget: BudgetConfig, source_duration_ms: int | None) -> int:
    floor_ms = int(budget.min_total_duration_ms) if budget.min_total_duration_ms is not None else 3000
    cap_ms = int(budget.max_total_duration_ms) if budget.max_total_duration_ms is not None else 45000
    floor_ms = max(1000, floor_ms)
    cap_ms = max(floor_ms, cap_ms)

    if source_duration_ms is not None and source_duration_ms > 0:
        if budget.target_ratio is not None:
            derived = int(source_duration_ms * float(budget.target_ratio))
        else:
            derived = int(source_duration_ms * 0.035)
        return max(floor_ms, min(cap_ms, derived))

    default_target = min(cap_ms, max(floor_ms, 9000))
    return default_target


def _compute_preferred_segment_ms(budget: BudgetConfig, source_duration_ms: int | None) -> int:
    base = 4000
    if source_duration_ms is not None and source_duration_ms > 15 * 60 * 1000:
        base = 6000
    return max(budget.min_segment_duration_ms, min(budget.max_segment_duration_ms, base))


def _compute_target_count(total_blocks: int, target_total_ms: int, preferred_segment_ms: int) -> int:
    if total_blocks <= 0:
        return 0
    denom = max(1, preferred_segment_ms)
    raw = int(round(target_total_ms / denom))
    capped = max(1, min(raw, total_blocks, 15))
    return capped


def _best_in_range_with_diversity(
    total_blocks: int,
    start: int,
    end: int,
    scores: list[float],
    selected: list[int],
    min_gap: int,
    exclude: set[int],
) -> int | None:
    candidates = [i for i in range(max(0, start), min(total_blocks, end)) if i not in exclude]
    if not candidates:
        candidates = [i for i in range(total_blocks) if i not in exclude]
    if not candidates:
        return None

    def rank(i: int) -> tuple[float, int]:
        penalty = 0.0
        for sel in selected:
            dist = abs(i - sel)
            if dist <= min_gap:
                penalty += 0.25
        return scores[i] - penalty, -i

    return max(candidates, key=rank)


def _is_too_close_to_selected(idx: int, selected: list[int], min_gap: int) -> bool:
    for sel in selected:
        if abs(idx - sel) <= min_gap:
            return True
    return False


def _best_in_range(
    total_blocks: int,
    start: int,
    end: int,
    scores: list[float] | None = None,
    exclude: set[int] | None = None,
) -> int:
    start_idx = max(0, min(total_blocks - 1, start))
    end_idx = max(start_idx + 1, min(total_blocks, end))
    deny = exclude or set()
    if scores is None:
        candidates = [i for i in range(start_idx, end_idx) if i not in deny]
        if not candidates:
            candidates = [i for i in range(total_blocks) if i not in deny]
        if not candidates:
            return 0
        return candidates[0]

    candidates = [i for i in range(start_idx, end_idx) if i not in deny]
    if not candidates:
        candidates = [i for i in range(total_blocks) if i not in deny]
    if not candidates:
        return 0
    return max(candidates, key=lambda i: (scores[i], -i))


_CTA_PATTERNS = [
    re.compile(r"\blike\b", re.IGNORECASE),
    re.compile(r"\bcomment\b", re.IGNORECASE),
    re.compile(r"\bsubscribe\b", re.IGNORECASE),
    re.compile(r"\bdang\s*ky\b", re.IGNORECASE),
    re.compile(r"\bdang\s*ki\b", re.IGNORECASE),
]


def _score_block(block: dict[str, object]) -> float:
    confidence = max(0.0, min(1.0, _to_float(block.get("confidence", 0.0))))
    fallback_type = str(block.get("fallback_type", "")).strip().lower()
    text = " ".join(
        [
            str(block.get("dialogue_text", "")).strip(),
            str(block.get("image_text", "")).strip(),
        ]
    ).strip()

    score = confidence
    if fallback_type == "exact":
        score += 0.10
    elif fallback_type == "containment":
        score += 0.05
    elif fallback_type == "nearest":
        score -= 0.10
    elif fallback_type == "no_match":
        score -= 0.30

    if _looks_like_cta(text):
        score -= 0.50

    if not text or text == "(khong co)":
        score -= 0.20

    return score


def _looks_like_cta(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return False
    return any(pattern.search(lowered) for pattern in _CTA_PATTERNS)


def _reduce_cta_candidates(
    selected: list[int],
    scores: list[float],
    context_blocks: list[dict[str, object]],
    target_count: int,
) -> list[int]:
    if len(selected) <= 1:
        return selected

    selected_set = set(selected)
    pool = [i for i in range(len(context_blocks)) if i not in selected_set]
    if not pool:
        return selected

    def is_cta_idx(idx: int) -> bool:
        text = " ".join(
            [
                str(context_blocks[idx].get("dialogue_text", "")).strip(),
                str(context_blocks[idx].get("image_text", "")).strip(),
            ]
        )
        return _looks_like_cta(text)

    cta_selected = [i for i in selected if is_cta_idx(i)]
    if not cta_selected:
        return selected

    non_cta_pool = [i for i in pool if not is_cta_idx(i)]
    if not non_cta_pool:
        return selected

    non_cta_pool.sort(key=lambda i: (-scores[i], i))
    updated = list(selected)
    for bad in sorted(cta_selected, key=lambda i: (scores[i], i)):
        if not non_cta_pool:
            break
        candidate = non_cta_pool[0]
        if scores[candidate] <= scores[bad]:
            continue
        updated[updated.index(bad)] = candidate
        non_cta_pool.pop(0)

    dedup = []
    seen: set[int] = set()
    for idx in updated:
        if idx not in seen:
            dedup.append(idx)
            seen.add(idx)

    if len(dedup) < target_count:
        for idx in sorted(range(len(context_blocks)), key=lambda i: (-scores[i], i)):
            if idx not in seen:
                dedup.append(idx)
                seen.add(idx)
            if len(dedup) == target_count:
                break
    return dedup


def _ms_to_ts(value: int) -> str:
    hh = value // 3600000
    rem = value % 3600000
    mm = rem // 60000
    rem = rem % 60000
    ss = rem // 1000
    ms = rem % 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d}.{ms:03d}"


def _script_text_from_block(summary_plot: str, block: dict[str, object]) -> str:
    image_text = str(block.get("image_text", "")).strip()
    dialogue_text = str(block.get("dialogue_text", "")).strip()
    if dialogue_text and dialogue_text != "(khong co)" and not is_raw_text_unsafe_for_script(dialogue_text):
        return dialogue_text
    if image_text and image_text != "(khong co)" and not is_raw_text_unsafe_for_script(image_text):
        return image_text
    return summary_plot


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0
