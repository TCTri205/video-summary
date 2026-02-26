from __future__ import annotations

import unittest

from reasoning_nlp.pipeline_runner import _build_summary_text
from reasoning_nlp.segment_planner.budget_policy import BudgetConfig
from reasoning_nlp.segment_planner.planner import plan_segments_from_context


class SummaryTextAndSegmentFilterTests(unittest.TestCase):
    def test_build_summary_text_returns_single_paragraph(self) -> None:
        internal = {
            "title": "Video Summary",
            "plot_summary": "Noi dung tom tat.",
            "moral_lesson": "Bai hoc.",
        }
        script = {
            "segments": [
                {"script_text": "Noi dung chinh 1"},
                {"script_text": "Hay like, comment, subscribe"},
                {"script_text": "Noi dung chinh 2"},
            ]
        }

        text = _build_summary_text(internal, script)
        self.assertIn("Noi dung tom tat.", text)
        self.assertIn("Bai hoc.", text)
        self.assertNotIn("subscribe", text.lower())
        self.assertNotIn("Tom tat:", text)
        self.assertNotIn("Cac diem chinh:", text)

    def test_planner_avoids_cta_when_possible(self) -> None:
        context_blocks = [
            {
                "timestamp": "00:00:00.500",
                "dialogue_text": "Mo dau noi dung",
                "image_text": "Canh mo dau",
                "confidence": 0.8,
                "fallback_type": "containment",
            },
            {
                "timestamp": "00:00:03.000",
                "dialogue_text": "Hay like comment subscribe de ung ho kenh",
                "image_text": "CTA",
                "confidence": 0.95,
                "fallback_type": "containment",
            },
            {
                "timestamp": "00:00:06.000",
                "dialogue_text": "Dien bien tiep theo",
                "image_text": "Canh giua",
                "confidence": 0.82,
                "fallback_type": "containment",
            },
            {
                "timestamp": "00:00:09.000",
                "dialogue_text": "Ket thuc noi dung",
                "image_text": "Canh ket",
                "confidence": 0.78,
                "fallback_type": "containment",
            },
        ]
        budget = BudgetConfig(
            min_segment_duration_ms=1200,
            max_segment_duration_ms=5000,
            min_total_duration_ms=None,
            max_total_duration_ms=None,
        )

        segments = plan_segments_from_context(
            context_blocks=context_blocks,
            summary_plot="plot",
            budget=budget,
            source_duration_ms=12000,
        )

        joined = " ".join(seg.script_text.lower() for seg in segments)
        self.assertNotIn("subscribe", joined)


if __name__ == "__main__":
    unittest.main()
