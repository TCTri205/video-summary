from __future__ import annotations

from dataclasses import dataclass

from reasoning_nlp.common.errors import fail
from reasoning_nlp.common.timecode import to_ms
from reasoning_nlp.segment_planner.budget_policy import BudgetConfig, validate_segment_duration, validate_total_duration
from reasoning_nlp.segment_planner.role_coverage import assign_role, ensure_role_coverage


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
    target_count = min(3, total_blocks)
    picks = _pick_block_indexes(total_blocks, target_count)

    segments: list[PlannedSegment] = []
    prev_end_ms = 0
    for seg_id, block_index in enumerate(picks, start=1):
        block = context_blocks[block_index]
        anchor_ts = str(block.get("timestamp", "00:00:00.000"))
        anchor_ms = to_ms(anchor_ts)
        start_ms = max(anchor_ms, prev_end_ms)
        end_ms = start_ms + 1500
        if source_duration_ms is not None and source_duration_ms > 0:
            end_ms = min(end_ms, source_duration_ms)
            if end_ms <= start_ms:
                end_ms = min(source_duration_ms, start_ms + 1200)

        duration_ms = end_ms - start_ms
        if not validate_segment_duration(duration_ms, budget):
            raise fail("segment_plan", "BUDGET_SEGMENT_DURATION", f"segment_id={seg_id} duration invalid")

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
        prev_end_ms = end_ms

    total_ms = sum(to_ms(s.source_end) - to_ms(s.source_start) for s in segments)
    budget_errors = validate_total_duration(total_ms, source_duration_ms, budget)
    if budget_errors:
        raise fail("segment_plan", budget_errors[0], "Total duration violates budget policy")

    missing_roles = ensure_role_coverage([s.role for s in segments])
    if total_blocks >= 3 and missing_roles:
        raise fail("segment_plan", "BUDGET_ROLE_COVERAGE", f"Missing roles: {missing_roles}")

    return segments


def _pick_block_indexes(total_blocks: int, target_count: int) -> list[int]:
    if target_count == 1:
        return [0]
    if target_count == 2:
        return [0, total_blocks - 1]
    return [0, total_blocks // 2, total_blocks - 1]


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
    if dialogue_text and dialogue_text != "(khong co)":
        return dialogue_text
    if image_text and image_text != "(khong co)":
        return image_text
    return summary_plot


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0
