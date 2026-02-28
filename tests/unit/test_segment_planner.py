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

    def test_longer_source_uses_more_segments_under_ratio_budget(self) -> None:
        context_blocks = []
        for idx in range(20):
            total_sec = idx * 10
            mm = total_sec // 60
            ss = total_sec % 60
            context_blocks.append(
                {
                    "timestamp": f"00:{mm:02d}:{ss:02d}.000",
                    "dialogue_text": f"noi dung {idx}",
                    "image_text": f"canh {idx}",
                    "confidence": 0.8,
                    "fallback_type": "containment",
                }
            )

        budget = BudgetConfig(
            min_segment_duration_ms=2000,
            max_segment_duration_ms=8000,
            min_total_duration_ms=30000,
            max_total_duration_ms=90000,
            target_ratio=0.035,
        )

        segments = plan_segments_from_context(
            context_blocks=context_blocks,
            summary_plot="plot",
            budget=budget,
            source_duration_ms=30 * 60 * 1000,
        )

        self.assertGreaterEqual(len(segments), 8)
        self.assertLessEqual(len(segments), 12)
        self.assertEqual(segments[0].role, "setup")
        self.assertEqual(segments[-1].role, "resolution")

    def test_dynamic_planner_avoids_cta_when_alternatives_exist(self) -> None:
        context_blocks = [
            {
                "timestamp": "00:00:05.000",
                "dialogue_text": "Mo dau hop le",
                "image_text": "Canh 1",
                "confidence": 0.70,
                "fallback_type": "containment",
            },
            {
                "timestamp": "00:00:15.000",
                "dialogue_text": "Hay like comment subscribe ngay",
                "image_text": "CTA",
                "confidence": 0.99,
                "fallback_type": "containment",
            },
            {
                "timestamp": "00:00:25.000",
                "dialogue_text": "Dien bien 2",
                "image_text": "Canh 2",
                "confidence": 0.80,
                "fallback_type": "containment",
            },
            {
                "timestamp": "00:00:35.000",
                "dialogue_text": "Dien bien 3",
                "image_text": "Canh 3",
                "confidence": 0.82,
                "fallback_type": "containment",
            },
            {
                "timestamp": "00:00:45.000",
                "dialogue_text": "Ket thuc hop le",
                "image_text": "Canh 4",
                "confidence": 0.78,
                "fallback_type": "containment",
            },
        ]
        budget = BudgetConfig(
            min_segment_duration_ms=2000,
            max_segment_duration_ms=5000,
            min_total_duration_ms=10000,
            max_total_duration_ms=15000,
            target_ratio=None,
        )

        segments = plan_segments_from_context(
            context_blocks=context_blocks,
            summary_plot="plot",
            budget=budget,
            source_duration_ms=60000,
        )

        joined = " ".join(seg.script_text.lower() for seg in segments)
        self.assertNotIn("subscribe", joined)


if __name__ == "__main__":
    unittest.main()
