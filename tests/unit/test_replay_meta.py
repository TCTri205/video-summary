from __future__ import annotations

import unittest

from reasoning_nlp.pipeline_runner import PipelineConfig, _build_run_meta


class ReplayMetaTests(unittest.TestCase):
    def test_run_meta_contains_runtime_and_schema_fingerprints(self) -> None:
        cfg = PipelineConfig(
            audio_transcripts_path="missing_audio.json",
            visual_captions_path="missing_caption.json",
            raw_video_path="missing_video.mp4",
        )
        meta = _build_run_meta(cfg)
        tracked = meta.get("tracked", {})
        self.assertIn("pipeline_version", tracked)
        self.assertIn("ffmpeg_version", tracked)
        self.assertIn("schema_checksums", tracked)


if __name__ == "__main__":
    unittest.main()
