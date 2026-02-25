from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class CLIRoutesTests(unittest.TestCase):
    def test_cli_routes_g3_g5_g8(self) -> None:
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

            for stage in ("g3", "g5", "g8"):
                run_id = f"cli_{stage}"
                cmd = [
                    "python",
                    "-m",
                    "reasoning_nlp.cli",
                    "--audio-transcripts",
                    str(transcripts),
                    "--visual-captions",
                    str(captions),
                    "--raw-video",
                    str(source_video),
                    "--stage",
                    stage,
                    "--run-id",
                    run_id,
                    "--artifacts-root",
                    str(root / "artifacts"),
                    "--summarize-backend",
                    "api",
                    "--summarize-fallback-backend",
                    "api",
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, msg=f"stage={stage}\nstdout={proc.stdout}\nstderr={proc.stderr}")

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
