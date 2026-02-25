from __future__ import annotations

import unittest

from reasoning_nlp.aligner.matcher import compute_adaptive_delta_ms, match_captions
from reasoning_nlp.common.types import CanonicalCaption, CanonicalTranscript


class MatcherTests(unittest.TestCase):
    def test_adaptive_delta_clamp(self) -> None:
        transcripts = [
            CanonicalTranscript("t1", "00:00:00.000", "00:00:01.000", 0, 1000, "a", 0, False),
            CanonicalTranscript("t2", "00:00:02.000", "00:00:04.000", 2000, 4000, "b", 1, False),
        ]
        delta = compute_adaptive_delta_ms(transcripts, k=1.2, min_delta_ms=1500, max_delta_ms=6000)
        self.assertEqual(delta, 1800)

    def test_tie_break_prefers_earlier_start(self) -> None:
        transcripts = [
            CanonicalTranscript("t_1", "00:00:01.000", "00:00:03.000", 1000, 3000, "early", 0, False),
            CanonicalTranscript("t_2", "00:00:02.000", "00:00:04.000", 2000, 4000, "late", 1, False),
        ]
        captions = [CanonicalCaption("c_1", "00:00:02.500", 2500, "img", 0, False)]
        result = match_captions(transcripts, captions, delta_ms=2000)
        self.assertEqual(result[0].fallback_type, "containment")
        self.assertEqual(result[0].transcript_ids, ["t_1"])

    def test_no_match_fallback(self) -> None:
        transcripts = [CanonicalTranscript("t_1", "00:00:10.000", "00:00:12.000", 10000, 12000, "x", 0, False)]
        captions = [CanonicalCaption("c_1", "00:00:01.000", 1000, "img", 0, False)]
        result = match_captions(transcripts, captions, delta_ms=1000)
        self.assertEqual(result[0].fallback_type, "no_match")
        self.assertEqual(result[0].dialogue_text, "(khong co)")
        self.assertEqual(result[0].transcript_ids, [])


if __name__ == "__main__":
    unittest.main()
