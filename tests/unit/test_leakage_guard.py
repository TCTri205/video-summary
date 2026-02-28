from __future__ import annotations

import unittest

from reasoning_nlp.summarizer.leakage_guard import (
    contains_hard_prompt_leakage,
    contains_soft_prompt_leakage,
    is_raw_text_unsafe_for_script,
    scrub_llm_generated_text,
)


class LeakageGuardTests(unittest.TestCase):
    def test_hard_marker_detects_system_reminder_block(self) -> None:
        text = (
            "<system-reminder> Plan Mode - System Reminder. "
            "You may ONLY observe, analyze, and plan. READ-ONLY phase. </system-reminder>"
        )
        self.assertTrue(contains_hard_prompt_leakage(text))
        self.assertTrue(is_raw_text_unsafe_for_script(text))

    def test_soft_marker_does_not_require_hard_fail(self) -> None:
        self.assertFalse(contains_hard_prompt_leakage("Critical: canh bao he thong"))
        self.assertTrue(contains_soft_prompt_leakage("Critical: canh bao he thong"))

    def test_scrub_preserves_legitimate_text_around_leak(self) -> None:
        text = (
            "Mo ta hop le. <system-reminder>Plan Mode - System Reminder. READ-ONLY phase.</system-reminder> "
            "Noi dung ket thuc."
        )
        cleaned, repaired = scrub_llm_generated_text(text)
        self.assertTrue(repaired)
        self.assertEqual(cleaned, "Mo ta hop le. Noi dung ket thuc.")

    def test_html_like_text_is_not_treated_as_hard_leak(self) -> None:
        text = "Man hinh hien thi HTML <b>tag</b> thong thuong."
        self.assertFalse(contains_hard_prompt_leakage(text))
        cleaned, repaired = scrub_llm_generated_text(text)
        self.assertEqual(cleaned, text)
        self.assertFalse(repaired)


if __name__ == "__main__":
    unittest.main()
