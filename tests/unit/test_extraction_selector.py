from __future__ import annotations

import unittest

from reasoning_nlp.segment_planner.extraction_selector import select_segments_from_extraction_boundaries


class ExtractionSelectorTests(unittest.TestCase):
    def test_selector_uses_extraction_boundaries_only(self) -> None:
        context_blocks = [
            {
                "timestamp": "00:00:00.500",
                "dialogue_text": "mo dau",
                "image_text": "canh 1",
                "confidence": 0.8,
                "fallback_type": "exact",
            },
            {
                "timestamp": "00:00:02.500",
                "dialogue_text": "dien bien",
                "image_text": "canh 2",
                "confidence": 0.9,
                "fallback_type": "containment",
            },
            {
                "timestamp": "00:00:04.500",
                "dialogue_text": "ket thuc",
                "image_text": "canh 3",
                "confidence": 0.7,
                "fallback_type": "containment",
            },
        ]

        segments = select_segments_from_extraction_boundaries(
            context_blocks=context_blocks,
            scene_timestamps_ms=[2000, 4000, 6000],
            source_duration_ms=8000,
            summary_plot="plot",
            min_candidate_segment_ms=500,
            max_selected_segments=3,
            min_total_duration_ms=None,
            max_total_duration_ms=None,
        )

        allowed = {
            ("00:00:00.000", "00:00:02.000"),
            ("00:00:02.000", "00:00:04.000"),
            ("00:00:04.000", "00:00:06.000"),
            ("00:00:06.000", "00:00:08.000"),
        }
        self.assertTrue(segments)
        for seg in segments:
            self.assertIn((seg.source_start, seg.source_end), allowed)

    def test_selector_filters_too_short_candidates(self) -> None:
        segments = select_segments_from_extraction_boundaries(
            context_blocks=[],
            scene_timestamps_ms=[100, 200, 300],
            source_duration_ms=1000,
            summary_plot="plot",
            min_candidate_segment_ms=500,
            max_selected_segments=5,
            min_total_duration_ms=None,
            max_total_duration_ms=None,
        )
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].source_start, "00:00:00.300")
        self.assertEqual(segments[0].source_end, "00:00:01.000")


if __name__ == "__main__":
    unittest.main()
