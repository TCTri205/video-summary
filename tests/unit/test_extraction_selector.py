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
            target_ratio=None,
            target_ratio_tolerance=0.20,
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
            target_ratio=None,
            target_ratio_tolerance=0.20,
        )
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].source_start, "00:00:00.300")
        self.assertEqual(segments[0].source_end, "00:00:01.000")

    def test_selector_targets_ratio_budget_by_expanding_adjacent_scenes(self) -> None:
        context_blocks = []
        for idx in range(12):
            context_blocks.append(
                {
                    "timestamp": f"00:00:{idx * 2 + 1:02d}.000",
                    "dialogue_text": f"noi dung {idx}",
                    "image_text": f"canh {idx}",
                    "confidence": 0.85,
                    "fallback_type": "containment",
                }
            )

        segments = select_segments_from_extraction_boundaries(
            context_blocks=context_blocks,
            scene_timestamps_ms=[2000 * (idx + 1) for idx in range(11)],
            source_duration_ms=240000,
            summary_plot="plot",
            min_candidate_segment_ms=500,
            max_selected_segments=15,
            min_total_duration_ms=3000,
            max_total_duration_ms=180000,
            target_ratio=0.10,
            target_ratio_tolerance=0.20,
        )

        total_ms = 0
        for seg in segments:
            def to_ms(ts: str) -> int:
                hh, mm, tail = ts.split(":")
                ss, ms = tail.split(".")
                return (((int(hh) * 60) + int(mm)) * 60 + int(ss)) * 1000 + int(ms)

            total_ms += to_ms(seg.source_end) - to_ms(seg.source_start)

        self.assertGreaterEqual(total_ms, 19200)
        self.assertLessEqual(total_ms, 28800)

    def test_selector_fails_when_only_candidate_exceeds_budget(self) -> None:
        with self.assertRaisesRegex(Exception, "BUDGET_OVERFLOW"):
            select_segments_from_extraction_boundaries(
                context_blocks=[],
                scene_timestamps_ms=[],
                source_duration_ms=60000,
                summary_plot="plot",
                min_candidate_segment_ms=500,
                max_selected_segments=5,
                min_total_duration_ms=3000,
                max_total_duration_ms=10000,
                target_ratio=0.10,
                target_ratio_tolerance=0.20,
            )


if __name__ == "__main__":
    unittest.main()
