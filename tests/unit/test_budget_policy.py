from __future__ import annotations

import unittest

from reasoning_nlp.segment_planner.budget_policy import BudgetConfig, validate_total_duration


class BudgetPolicyTests(unittest.TestCase):
    def test_overflow_detected(self) -> None:
        cfg = BudgetConfig(max_total_duration_ms=5000)
        errors = validate_total_duration(total_ms=7000, source_duration_ms=None, config=cfg)
        self.assertIn("BUDGET_OVERFLOW", errors)

    def test_ratio_underflow_detected(self) -> None:
        cfg = BudgetConfig(target_ratio=0.5, target_ratio_tolerance=0.1)
        errors = validate_total_duration(total_ms=3000, source_duration_ms=10000, config=cfg)
        self.assertIn("BUDGET_UNDERFLOW", errors)


if __name__ == "__main__":
    unittest.main()
