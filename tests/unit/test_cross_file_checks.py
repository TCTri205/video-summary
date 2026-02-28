from __future__ import annotations

import unittest

from reasoning_nlp.validators.cross_file_checks import check_script_manifest_consistency


class CrossFileChecksTests(unittest.TestCase):
    def test_consistency_pass(self) -> None:
        script = {
            "segments": [
                {"segment_id": 1, "source_start": "00:00:01.000", "source_end": "00:00:04.000", "script_text": "a"},
                {"segment_id": 2, "source_start": "00:00:05.000", "source_end": "00:00:08.000", "script_text": "b"},
            ]
        }
        manifest = {
            "segments": [
                {"segment_id": 1, "source_start": "00:00:01.000", "source_end": "00:00:04.000", "script_ref": 1},
                {"segment_id": 2, "source_start": "00:00:05.000", "source_end": "00:00:08.000", "script_ref": 2},
            ]
        }
        errors = check_script_manifest_consistency(script, manifest, source_duration_ms=10000)
        self.assertEqual(errors, [])

    def test_detects_overlap_and_missing_ref(self) -> None:
        script = {
            "segments": [
                {"segment_id": 1, "source_start": "00:00:01.000", "source_end": "00:00:04.000", "script_text": "a"},
                {"segment_id": 2, "source_start": "00:00:03.500", "source_end": "00:00:06.000", "script_text": "b"},
            ]
        }
        manifest = {
            "segments": [
                {"segment_id": 1, "source_start": "00:00:01.000", "source_end": "00:00:04.000", "script_ref": 1},
                {"segment_id": 2, "source_start": "00:00:03.500", "source_end": "00:00:06.000", "script_ref": 99},
            ]
        }
        errors = check_script_manifest_consistency(script, manifest, source_duration_ms=10000)
        self.assertTrue(any("overlaps" in e for e in errors))
        self.assertTrue(any("script_ref=99" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
