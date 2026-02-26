from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from reasoning_nlp.pipeline_runner import PipelineConfig, run_pipeline_g1_g8


class PipelineReplayModeTests(unittest.TestCase):
    def test_replay_skips_existing_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            source_video = data_dir / "raw_video.mp4"
            self._make_test_video(source_video)

            transcripts = data_dir / "audio_transcripts.json"
            captions = data_dir / "visual_captions.json"
            transcripts.write_text(
                json.dumps(
                    [
                        {"start": "00:00:00.000", "end": "00:00:02.000", "text": "a"},
                        {"start": "00:00:02.000", "end": "00:00:04.000", "text": "b"},
                        {"start": "00:00:04.000", "end": "00:00:06.000", "text": "c"},
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            captions.write_text(
                json.dumps(
                    [
                        {"timestamp": "00:00:00.500", "caption": "x"},
                        {"timestamp": "00:00:02.500", "caption": "y"},
                        {"timestamp": "00:00:04.500", "caption": "z"},
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            cfg = PipelineConfig(
                audio_transcripts_path=str(transcripts),
                visual_captions_path=str(captions),
                raw_video_path=str(source_video),
                artifacts_root=str(root / "artifacts"),
                run_id="replay_case",
                summarize_backend="heuristic",
                summarize_fallback_backend="heuristic",
                replay_mode=False,
            )
            first = run_pipeline_g1_g8(cfg)
            self.assertTrue(all(x["status"] == "pass" for x in first["stage_results"]))

            replay_cfg = PipelineConfig(
                audio_transcripts_path=str(transcripts),
                visual_captions_path=str(captions),
                raw_video_path=str(source_video),
                artifacts_root=str(root / "artifacts"),
                run_id="replay_case",
                summarize_backend="heuristic",
                summarize_fallback_backend="heuristic",
                replay_mode=True,
            )
            second = run_pipeline_g1_g8(replay_cfg)

            statuses = {x["stage"]: x["status"] for x in second["stage_results"]}
            self.assertEqual(statuses["validate"], "skipped")
            self.assertEqual(statuses["align"], "skipped")
            self.assertEqual(statuses["context_build"], "skipped")
            self.assertEqual(statuses["summarize"], "skipped")
            self.assertEqual(statuses["segment_plan"], "skipped")
            self.assertEqual(statuses["manifest"], "skipped")
            self.assertEqual(statuses["assemble"], "skipped")
            self.assertEqual(statuses["qc"], "pass")

    def test_replay_invalidation_on_summarize_config_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            source_video = data_dir / "raw_video.mp4"
            self._make_test_video(source_video)

            transcripts = data_dir / "audio_transcripts.json"
            captions = data_dir / "visual_captions.json"
            transcripts.write_text(
                json.dumps(
                    [
                        {"start": "00:00:00.000", "end": "00:00:02.000", "text": "a"},
                        {"start": "00:00:02.000", "end": "00:00:04.000", "text": "b"},
                        {"start": "00:00:04.000", "end": "00:00:06.000", "text": "c"},
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            captions.write_text(
                json.dumps(
                    [
                        {"timestamp": "00:00:00.500", "caption": "x"},
                        {"timestamp": "00:00:02.500", "caption": "y"},
                        {"timestamp": "00:00:04.500", "caption": "z"},
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            first_cfg = PipelineConfig(
                audio_transcripts_path=str(transcripts),
                visual_captions_path=str(captions),
                raw_video_path=str(source_video),
                artifacts_root=str(root / "artifacts"),
                run_id="replay_invalidate_case",
                summarize_backend="heuristic",
                summarize_fallback_backend="heuristic",
                model_version="model_a",
                replay_mode=False,
            )
            run_pipeline_g1_g8(first_cfg)

            replay_changed_cfg = PipelineConfig(
                audio_transcripts_path=str(transcripts),
                visual_captions_path=str(captions),
                raw_video_path=str(source_video),
                artifacts_root=str(root / "artifacts"),
                run_id="replay_invalidate_case",
                summarize_backend="heuristic",
                summarize_fallback_backend="heuristic",
                model_version="model_b",
                replay_mode=True,
            )
            second = run_pipeline_g1_g8(replay_changed_cfg)

            statuses = {x["stage"]: x["status"] for x in second["stage_results"]}
            self.assertEqual(statuses["validate"], "skipped")
            self.assertEqual(statuses["align"], "skipped")
            self.assertEqual(statuses["context_build"], "skipped")
            self.assertEqual(statuses["summarize"], "pass")
            self.assertEqual(statuses["segment_plan"], "pass")
            self.assertEqual(statuses["manifest"], "pass")
            self.assertEqual(statuses["assemble"], "pass")
            self.assertEqual(statuses["qc"], "pass")

    def _make_test_video(self, output_path: Path) -> None:
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=24:duration=8",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=8",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            self.fail(f"Failed to create test video: {proc.stderr}")


if __name__ == "__main__":
    unittest.main()
