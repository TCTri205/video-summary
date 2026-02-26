from __future__ import annotations

import unittest

from reasoning_nlp.common.timecode import to_ms
from reasoning_nlp.segment_planner.budget_policy import BudgetConfig
from reasoning_nlp.segment_planner.planner import plan_segments_from_context


class SegmentPlannerTests(unittest.TestCase):
    def test_short_tail_source_does_not_fail_budget_segment_duration(self) -> None:
        context_blocks = [
            {"timestamp": "00:00:00.100", "dialogue_text": "a", "image_text": "a", "confidence": 0.8},
            {"timestamp": "00:00:01.000", "dialogue_text": "b", "image_text": "b", "confidence": 0.8},
            {"timestamp": "00:00:02.450", "dialogue_text": "c", "image_text": "c", "confidence": 0.8},
        ]
        budget = BudgetConfig(
            min_segment_duration_ms=1200,
            max_segment_duration_ms=15000,
            min_total_duration_ms=None,
            max_total_duration_ms=None,
        )

        segments = plan_segments_from_context(
            context_blocks=context_blocks,
            summary_plot="plot",
            budget=budget,
            source_duration_ms=3000,
        )

        self.assertGreaterEqual(len(segments), 1)
        for seg in segments:
            duration = to_ms(seg.source_end) - to_ms(seg.source_start)
            self.assertGreaterEqual(duration, budget.min_segment_duration_ms)
            self.assertLessEqual(duration, budget.max_segment_duration_ms)


if __name__ == "__main__":
    unittest.main()
