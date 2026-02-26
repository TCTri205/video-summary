from __future__ import annotations

import unittest

from reasoning_nlp.summarizer.prompt_builder import build_summary_prompt


class PromptBuilderTests(unittest.TestCase):
    def test_build_prompt_without_budget_keeps_all_blocks(self) -> None:
        blocks = [
            {"context_text": "a"},
            {"context_text": "b"},
            {"context_text": "c"},
        ]
        out = build_summary_prompt(blocks)
        self.assertEqual(out, "a\n\nb\n\nc")

    def test_build_prompt_with_budget_keeps_balanced_anchors(self) -> None:
        blocks = [
            {"context_text": "start", "confidence": 0.1},
            {"context_text": "middle", "confidence": 0.9},
            {"context_text": "end", "confidence": 0.2},
        ]
        out = build_summary_prompt(blocks, max_chars=15)
        self.assertIn("start", out)
        self.assertIn("middle", out)


if __name__ == "__main__":
    unittest.main()
