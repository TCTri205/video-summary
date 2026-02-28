from __future__ import annotations

import unittest

from reasoning_nlp.summarizer.prompt_builder import build_summary_prompt


class PromptBuilderTests(unittest.TestCase):
    def test_build_prompt_without_budget_keeps_all_blocks(self) -> None:
        blocks = [
            {"context_text": "a", "timestamp": "00:00:00.100", "dialogue_text": "a", "confidence": 0.2},
            {"context_text": "b", "timestamp": "00:00:01.100", "dialogue_text": "b", "confidence": 0.3},
            {"context_text": "c", "timestamp": "00:00:02.100", "dialogue_text": "c", "confidence": 0.4},
        ]
        out = build_summary_prompt(blocks)
        self.assertIn("[Block 1]", out)
        self.assertIn("timestamp=00:00:00.100", out)
        self.assertIn("dialogue_text=a", out)

    def test_build_prompt_with_budget_keeps_balanced_anchors(self) -> None:
        blocks = [
            {"context_text": "start", "dialogue_text": "start", "confidence": 0.1},
            {"context_text": "middle", "dialogue_text": "middle", "confidence": 0.9},
            {"context_text": "end", "dialogue_text": "end", "confidence": 0.2},
        ]
        out = build_summary_prompt(blocks, max_chars=200)
        self.assertIn("start", out)
        self.assertIn("middle", out)


if __name__ == "__main__":
    unittest.main()
