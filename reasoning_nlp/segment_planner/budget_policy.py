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


def validate_segment_duration(duration_ms: int, config: BudgetConfig) -> bool:
    return config.min_segment_duration_ms <= duration_ms <= config.max_segment_duration_ms


def validate_total_duration(total_ms: int, source_duration_ms: int | None, config: BudgetConfig) -> list[str]:
    errors: list[str] = []
    if config.min_total_duration_ms is not None and total_ms < config.min_total_duration_ms:
        errors.append("BUDGET_UNDERFLOW")
    if config.max_total_duration_ms is not None and total_ms > config.max_total_duration_ms:
        errors.append("BUDGET_OVERFLOW")
    if config.target_ratio is not None:
        if source_duration_ms is None or source_duration_ms <= 0:
            errors.append("BUDGET_TARGET_RATIO")
        else:
            expected = source_duration_ms * config.target_ratio
            delta = expected * config.target_ratio_tolerance
            if total_ms < expected - delta:
                errors.append("BUDGET_UNDERFLOW")
            if total_ms > expected + delta:
                errors.append("BUDGET_OVERFLOW")
    return errors
