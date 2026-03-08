from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from reasoning_nlp.validators.input_validator import validate_and_normalize_inputs


class InputValidatorTests(unittest.TestCase):
    def test_strict_profile_normalizes_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "audio_transcripts.json"
            captions = root / "visual_captions.json"
            scene_metadata = root / "scene_metadata.json"
            video = root / "raw_video.mp4"

            audio.write_text(
                """
[
  {"start": "00:00:01.000", "end": "00:00:02.000", "text": " hello "}
]
""".strip(),
                encoding="utf-8",
            )
            captions.write_text(
                """
[
  {"timestamp": "00:00:01.500", "caption": " image "}
]
""".strip(),
                encoding="utf-8",
            )
            scene_metadata.write_text(
                """
{
  "total_keyframes": 1,
  "frames": [
    {"frame_id": 1, "timestamp": "00:00:01.500", "file_path": "keyframes/f1.jpg"}
  ]
}
""".strip(),
                encoding="utf-8",
            )
            video.write_bytes(b"dummy")

            validated = validate_and_normalize_inputs(
                audio_transcripts_path=audio,
                visual_captions_path=captions,
                scene_metadata_path=scene_metadata,
                raw_video_path=video,
                profile="strict_contract_v1",
            )

            self.assertEqual(validated.transcripts[0].transcript_id, "t_0001")
            self.assertEqual(validated.captions[0].caption_id, "c_0001")
            self.assertEqual(validated.transcripts[0].text, "hello")
            self.assertEqual(validated.captions[0].caption, "image")
            self.assertEqual(validated.scene_timestamps_ms, [1500])

    def test_legacy_profile_float_seconds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "audio_transcripts.json"
            captions = root / "visual_captions.json"
            scene_metadata = root / "scene_metadata.json"
            video = root / "raw_video.mp4"

            audio.write_text(
                """
{
  "language": "vi",
  "duration": 10.0,
  "segments": [
    {"start": 1.2, "end": 3.4, "text": "xin chao"}
  ]
}
""".strip(),
                encoding="utf-8",
            )
            captions.write_text(
                """
[
  {"timestamp": "00:00:01.500", "caption": "khung hinh"}
]
""".strip(),
                encoding="utf-8",
            )
            scene_metadata.write_text(
                """
{
  "total_keyframes": 2,
  "frames": [
    {"frame_id": 1, "timestamp": "00:00:03.000", "file_path": "keyframes/f1.jpg"},
    {"frame_id": 2, "timestamp": "00:00:01.000", "file_path": "keyframes/f2.jpg"}
  ]
}
""".strip(),
                encoding="utf-8",
            )
            video.write_bytes(b"dummy")

            validated = validate_and_normalize_inputs(
                audio_transcripts_path=audio,
                visual_captions_path=captions,
                scene_metadata_path=scene_metadata,
                raw_video_path=video,
                profile="legacy_member1",
            )

            self.assertEqual(validated.transcripts[0].start, "00:00:01.200")
            self.assertEqual(validated.transcripts[0].end, "00:00:03.400")
            self.assertEqual(validated.scene_timestamps_ms, [1000, 3000])


if __name__ == "__main__":
    unittest.main()
