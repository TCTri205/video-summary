from __future__ import annotations

import unittest

from reasoning_nlp.segment_planner.budget_policy import BudgetConfig, compute_budget_window_ms, validate_total_duration


class BudgetPolicyTests(unittest.TestCase):
    def test_overflow_detected(self) -> None:
        cfg = BudgetConfig(max_total_duration_ms=5000)
        errors = validate_total_duration(total_ms=7000, source_duration_ms=None, config=cfg)
        self.assertIn("BUDGET_OVERFLOW", errors)

    def test_ratio_underflow_detected(self) -> None:
        cfg = BudgetConfig(target_ratio=0.5, target_ratio_tolerance=0.1)
        errors = validate_total_duration(total_ms=3000, source_duration_ms=10000, config=cfg)
        self.assertIn("BUDGET_UNDERFLOW", errors)

    def test_budget_window_clamps_ratio_to_total_caps(self) -> None:
        cfg = BudgetConfig(
            min_total_duration_ms=3000,
            max_total_duration_ms=180000,
            target_ratio=0.10,
            target_ratio_tolerance=0.20,
        )
        target_ms, lower_ms, upper_ms = compute_budget_window_ms(240000, cfg)
        self.assertEqual(target_ms, 24000)
        self.assertEqual(lower_ms, 19200)
        self.assertEqual(upper_ms, 28800)

    def test_budget_window_respects_floor_when_ratio_is_smaller(self) -> None:
        cfg = BudgetConfig(
            min_total_duration_ms=3000,
            max_total_duration_ms=180000,
            target_ratio=0.10,
            target_ratio_tolerance=0.20,
        )
        target_ms, lower_ms, upper_ms = compute_budget_window_ms(8000, cfg)
        self.assertEqual(target_ms, 3000)
        self.assertEqual(lower_ms, 3000)
        self.assertEqual(upper_ms, 3600)


if __name__ == "__main__":
    unittest.main()
