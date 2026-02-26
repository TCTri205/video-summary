from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from reasoning_nlp.pipeline_runner import PipelineConfig, run_pipeline_g1_g8


class PipelineDeterminismTests(unittest.TestCase):
    def test_g1_g8_deterministic_json_outputs(self) -> None:
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
                        {"start": "00:00:00.000", "end": "00:00:02.000", "text": "mo dau"},
                        {"start": "00:00:02.000", "end": "00:00:04.000", "text": "dien bien"},
                        {"start": "00:00:04.000", "end": "00:00:06.000", "text": "ket thuc"},
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
                        {"timestamp": "00:00:00.500", "caption": "canh 1"},
                        {"timestamp": "00:00:02.500", "caption": "canh 2"},
                        {"timestamp": "00:00:04.500", "caption": "canh 3"},
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            result_1 = run_pipeline_g1_g8(
                PipelineConfig(
                    audio_transcripts_path=str(transcripts),
                    visual_captions_path=str(captions),
                    raw_video_path=str(source_video),
                    artifacts_root=str(root / "artifacts"),
                    run_id="det_run_1",
                    summarize_seed=42,
                    summarize_backend="heuristic",
                    summarize_fallback_backend="heuristic",
                    summarize_production_strict=False,
                    allow_heuristic_for_tests=True,
                )
            )
            result_2 = run_pipeline_g1_g8(
                PipelineConfig(
                    audio_transcripts_path=str(transcripts),
                    visual_captions_path=str(captions),
                    raw_video_path=str(source_video),
                    artifacts_root=str(root / "artifacts"),
                    run_id="det_run_2",
                    summarize_seed=42,
                    summarize_backend="heuristic",
                    summarize_fallback_backend="heuristic",
                    summarize_production_strict=False,
                    allow_heuristic_for_tests=True,
                )
            )

            self.assertEqual(result_1["summary_script"], result_2["summary_script"])
            self.assertEqual(result_1["summary_video_manifest"], result_2["summary_video_manifest"])

            report_1 = result_1["quality_report"]
            report_2 = result_2["quality_report"]
            self.assertEqual(report_1["metrics"], report_2["metrics"])
            self.assertEqual(report_1["warnings"], report_2["warnings"])

            statuses_1 = [(x["stage"], x["status"]) for x in result_1["stage_results"]]
            statuses_2 = [(x["stage"], x["status"]) for x in result_2["stage_results"]]
            self.assertEqual(statuses_1, statuses_2)

            output_video_1 = Path(result_1["artifacts"]["summary_video"])
            output_video_2 = Path(result_2["artifacts"]["summary_video"])
            final_video_1 = Path(result_1["artifacts"]["final_summary_video"])
            final_video_2 = Path(result_2["artifacts"]["final_summary_video"])
            final_text_1 = Path(result_1["artifacts"]["final_summary_text"])
            final_text_2 = Path(result_2["artifacts"]["final_summary_text"])
            self.assertTrue(output_video_1.exists())
            self.assertTrue(output_video_2.exists())
            self.assertGreater(output_video_1.stat().st_size, 0)
            self.assertGreater(output_video_2.stat().st_size, 0)
            self.assertTrue(final_video_1.exists())
            self.assertTrue(final_video_2.exists())
            self.assertTrue(final_text_1.exists())
            self.assertTrue(final_text_2.exists())
            self.assertGreater(final_text_1.stat().st_size, 0)
            self.assertGreater(final_text_2.stat().st_size, 0)

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
