from __future__ import annotations

import unittest

from reasoning_nlp.summarizer.parse_repair import repair_internal_summary


class ParseRepairLeakageTests(unittest.TestCase):
    def test_repair_removes_prompt_leakage_and_flags_it(self) -> None:
        payload = {
            "title": "Video Summary",
            "plot_summary": "<system-reminder>Plan Mode - System Reminder. READ-ONLY phase.</system-reminder>",
            "moral_lesson": "Bai hoc hop le.",
            "evidence": [
                {
                    "claim": "Noi dung hop le <system-reminder>strictly forbidden</system-reminder>",
                    "timestamps": ["00:00:01.000"],
                }
            ],
            "quality_flags": [],
            "generation_meta": {},
            "segments": [
                {
                    "segment_id": 1,
                    "source_start": "00:00:00.000",
                    "source_end": "00:00:02.000",
                    "script_text": "x",
                    "confidence": 0.8,
                    "role": "setup",
                }
            ],
        }

        repaired = repair_internal_summary(payload)
        self.assertNotIn("system-reminder", repaired["plot_summary"].lower())
        self.assertIn("PROMPT_LEAKAGE_REPAIRED", repaired["quality_flags"])
        self.assertTrue(repaired["evidence"])
        self.assertNotIn("system-reminder", repaired["evidence"][0]["claim"].lower())


if __name__ == "__main__":
    unittest.main()
