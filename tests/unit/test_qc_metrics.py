from __future__ import annotations

import unittest

from reasoning_nlp.qc.metrics import (
    compute_black_frame_ratio,
    compute_grounding_score,
    compute_parse_validity_rate,
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


if __name__ == "__main__":
    unittest.main()
