from __future__ import annotations

import unittest

from reasoning_nlp.qc.metrics import (
    compute_black_frame_ratio,
    compute_black_frame_ratio_with_status,
    compute_grounding_score,
    compute_parse_validity_rate,
    compute_text_video_consistency_metrics,
)


class QCMetricsTests(unittest.TestCase):
    def test_grounding_score_matches_context(self) -> None:
        summary = {
            "evidence": [
                {"claim": "c1", "timestamps": ["00:00:01.000", "00:00:02.000"]},
                {"claim": "c2", "timestamps": ["00:00:03.000"]},
            ]
        }
        context = [
            {"timestamp": "00:00:01.000"},
            {"timestamp": "00:00:02.000"},
            {"timestamp": "00:00:03.000"},
        ]
        self.assertEqual(compute_grounding_score(summary, context), 1.0)

    def test_grounding_score_partial(self) -> None:
        summary = {"evidence": [{"claim": "c1", "timestamps": ["00:00:01.000", "00:00:09.000"]}]}
        context = [{"timestamp": "00:00:01.000"}]
        self.assertAlmostEqual(compute_grounding_score(summary, context), 0.5, places=6)

    def test_parse_validity_rate(self) -> None:
        valid = {
            "title": "t",
            "plot_summary": "p",
            "moral_lesson": "m",
            "evidence": [],
            "quality_flags": [],
            "generation_meta": {},
            "segments": [1],
        }
        invalid = {"title": "x"}
        self.assertEqual(compute_parse_validity_rate(valid), 1.0)
        self.assertEqual(compute_parse_validity_rate(invalid), 0.0)

    def test_black_frame_ratio_missing_file(self) -> None:
        ratio = compute_black_frame_ratio("missing_file.mp4")
        self.assertEqual(ratio, 1.0)

    def test_black_frame_ratio_status_missing_file(self) -> None:
        result = compute_black_frame_ratio_with_status("missing_file.mp4")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], "QC_BLACKDETECT_VIDEO_INVALID")

    def test_text_video_consistency_metrics(self) -> None:
        text = "Mo dau noi dung. Sau do dien bien tiep theo."
        internal = {
            "sentences": [
                {
                    "order": 1,
                    "text": "Mo dau noi dung",
                    "support_segment_ids": [1],
                    "support_timestamps": ["00:00:01.000"],
                },
                {
                    "order": 2,
                    "text": "Sau do dien bien tiep theo",
                    "support_segment_ids": [2],
                    "support_timestamps": ["00:00:04.000"],
                },
            ]
        }
        script = {
            "segments": [
                {
                    "segment_id": 1,
                    "source_start": "00:00:01.000",
                    "source_end": "00:00:03.000",
                    "script_text": "Mo dau noi dung",
                },
                {
                    "segment_id": 2,
                    "source_start": "00:00:04.000",
                    "source_end": "00:00:06.000",
                    "script_text": "Dien bien tiep theo",
                },
            ]
        }

        metrics = compute_text_video_consistency_metrics(text, internal, script)
        self.assertEqual(metrics["text_sentence_grounded_ratio"], 1.0)
        self.assertEqual(metrics["text_segment_coverage_ratio"], 1.0)
        self.assertEqual(metrics["text_temporal_order_score"], 1.0)
        self.assertGreater(metrics["text_video_keyword_overlap"], 0.4)
        self.assertEqual(metrics["text_cta_leak_ratio"], 0.0)


if __name__ == "__main__":
    unittest.main()
