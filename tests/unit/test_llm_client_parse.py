from __future__ import annotations

import unittest

from reasoning_nlp.summarizer.llm_client import _parse_json_payload


class LLMClientParseTests(unittest.TestCase):
    def test_parse_json_direct(self) -> None:
        payload = _parse_json_payload('{"title":"x"}')
        self.assertEqual(payload["title"], "x")

    def test_parse_json_embedded(self) -> None:
        payload = _parse_json_payload('noise before {"title":"x","plot_summary":"p"} noise after')
        self.assertEqual(payload["title"], "x")

    def test_parse_json_invalid(self) -> None:
        with self.assertRaises(RuntimeError):
            _parse_json_payload("not a json")


if __name__ == "__main__":
    unittest.main()
