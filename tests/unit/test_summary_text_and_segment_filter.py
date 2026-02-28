from __future__ import annotations

import unittest

from reasoning_nlp.pipeline_runner import _build_summary_text, _build_summary_text_internal
from reasoning_nlp.segment_planner.budget_policy import BudgetConfig
from reasoning_nlp.segment_planner.planner import plan_segments_from_context


class SummaryTextAndSegmentFilterTests(unittest.TestCase):
    def test_build_summary_text_returns_single_paragraph(self) -> None:
        script = {
            "segments": [
                {
                    "segment_id": 1,
                    "source_start": "00:00:01.000",
                    "source_end": "00:00:03.000",
                    "script_text": "Noi dung chinh 1",
                },
                {
                    "segment_id": 2,
                    "source_start": "00:00:03.000",
                    "source_end": "00:00:05.000",
                    "script_text": "Hay like, comment, subscribe",
                },
                {
                    "segment_id": 3,
                    "source_start": "00:00:05.000",
                    "source_end": "00:00:07.000",
                    "script_text": "Noi dung chinh 2",
                },
            ]
        }

        internal_text = _build_summary_text_internal(script)
        text = _build_summary_text({}, script, internal_text)
        self.assertIn("Noi dung chinh 1", text)
        self.assertIn("Noi dung chinh 2", text)
        self.assertNotIn("subscribe", text.lower())
        self.assertNotIn("Tom tat:", text)
        self.assertNotIn("Cac diem chinh:", text)

        supports = internal_text["sentences"][0]["support_segment_ids"]
        self.assertTrue(all(isinstance(x, int) for x in supports))

    def test_build_summary_text_internal_keeps_grounded_provenance(self) -> None:
        script = {
            "segments": [
                {
                    "segment_id": 1,
                    "source_start": "00:00:01.000",
                    "source_end": "00:00:03.000",
                    "script_text": "Mo dau canh hop le",
                },
                {
                    "segment_id": 2,
                    "source_start": "00:00:03.000",
                    "source_end": "00:00:05.000",
                    "script_text": "Dien bien tiep theo",
                },
                {
                    "segment_id": 3,
                    "source_start": "00:00:05.000",
                    "source_end": "00:00:07.000",
                    "script_text": "Ket thuc on dinh",
                },
            ]
        }

        internal = _build_summary_text_internal(script)
        self.assertEqual(internal["schema_version"], "1.0")
        self.assertGreaterEqual(len(internal["sentences"]), 1)
        for sent in internal["sentences"]:
            self.assertTrue(sent["support_segment_ids"])
            self.assertTrue(sent["support_timestamps"])

        text = _build_summary_text({}, script, internal)
        self.assertIn("Mo dau", text)
        self.assertIn("Cuoi cung", text)

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

    def test_planner_skips_prompt_leakage_source_text(self) -> None:
        context_blocks = [
            {
                "timestamp": "00:00:00.500",
                "dialogue_text": "<system-reminder>Plan Mode - System Reminder. READ-ONLY phase.</system-reminder>",
                "image_text": "Canh hop le",
                "confidence": 0.95,
                "fallback_type": "containment",
            },
            {
                "timestamp": "00:00:04.000",
                "dialogue_text": "Noi dung binh thuong",
                "image_text": "Canh tiep theo",
                "confidence": 0.80,
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
            summary_plot="Tom tat an toan",
            budget=budget,
            source_duration_ms=9000,
        )

        joined = " ".join(seg.script_text.lower() for seg in segments)
        self.assertNotIn("system-reminder", joined)


if __name__ == "__main__":
    unittest.main()
