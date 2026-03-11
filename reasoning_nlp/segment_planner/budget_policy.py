from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetConfig:
    min_segment_duration_ms: int = 1200
    max_segment_duration_ms: int = 15000
    min_total_duration_ms: int | None = None
    max_total_duration_ms: int | None = None
    target_ratio: float | None = None
    target_ratio_tolerance: float = 0.20


def compute_effective_target_total_ms(source_duration_ms: int | None, config: BudgetConfig) -> int | None:
    floor_ms = int(config.min_total_duration_ms) if config.min_total_duration_ms is not None else None
    cap_ms = int(config.max_total_duration_ms) if config.max_total_duration_ms is not None else None

    target_ms: int | None = None
    if config.target_ratio is not None:
        if source_duration_ms is None or source_duration_ms <= 0:
            return None
        target_ms = int(round(float(source_duration_ms) * float(config.target_ratio)))
    elif floor_ms is not None:
        target_ms = floor_ms
    elif cap_ms is not None:
        target_ms = cap_ms

    if target_ms is None:
        return None
    if floor_ms is not None:
        target_ms = max(target_ms, floor_ms)
    if cap_ms is not None:
        target_ms = min(target_ms, cap_ms)
    return max(0, int(target_ms))


def compute_budget_window_ms(source_duration_ms: int | None, config: BudgetConfig) -> tuple[int | None, int | None, int | None]:
    target_ms = compute_effective_target_total_ms(source_duration_ms, config)
    floor_ms = int(config.min_total_duration_ms) if config.min_total_duration_ms is not None else None
    cap_ms = int(config.max_total_duration_ms) if config.max_total_duration_ms is not None else None
    lower_ms = floor_ms
    upper_ms = cap_ms

    if target_ms is not None and config.target_ratio is not None:
        delta = int(round(float(target_ms) * float(config.target_ratio_tolerance)))
        lower_ms = target_ms - delta
        upper_ms = target_ms + delta
        if floor_ms is not None:
            lower_ms = max(lower_ms, floor_ms)
        if cap_ms is not None:
            upper_ms = min(upper_ms, cap_ms)
        if upper_ms is not None:
            lower_ms = min(lower_ms, upper_ms)
    return target_ms, lower_ms, upper_ms


def validate_segment_duration(duration_ms: int, config: BudgetConfig) -> bool:
    return config.min_segment_duration_ms <= duration_ms <= config.max_segment_duration_ms


def validate_total_duration(total_ms: int, source_duration_ms: int | None, config: BudgetConfig) -> list[str]:
    errors: list[str] = []
    target_ms, lower_ms, upper_ms = compute_budget_window_ms(source_duration_ms, config)

    if lower_ms is not None and total_ms < lower_ms:
        errors.append("BUDGET_UNDERFLOW")
    if upper_ms is not None and total_ms > upper_ms:
        errors.append("BUDGET_OVERFLOW")
    if config.target_ratio is not None:
        if target_ms is None:
            errors.append("BUDGET_TARGET_RATIO")
    return errors
