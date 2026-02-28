import os
import json
from pathlib import Path
from faster_whisper import WhisperModel


class WhisperExtractor:
    def __init__(
        self,
        model_size="base",
        device="cpu",
        compute_type="int8"
    ):
        print("Loading Whisper model...")

        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type
        )

        print("Whisper loaded successfully!")

    @staticmethod
    def _seconds_to_timestamp(seconds: float) -> str:
        if seconds < 0:
            seconds = 0.0

        total_ms = int(round(seconds * 1000))
        hh = total_ms // 3_600_000
        rem = total_ms % 3_600_000
        mm = rem // 60_000
        rem = rem % 60_000
        ss = rem // 1000
        ms = rem % 1000
        return f"{hh:02}:{mm:02}:{ss:02}.{ms:03}"

    def transcribe(
        self,
        input_path: str,
        language: str = "",
        output_root: str = "",
        output_name: str = "",
    ):
        """
        input_path: path to source media (video/audio)
        """

        print(f"Transcribing: {input_path}")

        transcribe_kwargs = {}
        if language:
            transcribe_kwargs["language"] = language

        segments, info = self.model.transcribe(input_path, **transcribe_kwargs)

        results = []
        for segment in segments:
            start = float(segment.start)
            end = float(segment.end)
            results.append({
                "start": self._seconds_to_timestamp(start),
                "end": self._seconds_to_timestamp(end),
                "text": segment.text.strip()
            })

        if any(results[i]["start"] > results[i + 1]["start"] for i in range(len(results) - 1)):
            results.sort(key=lambda item: item["start"])

        final_output = results

        # ======= TẠO FOLDER THEO TÊN VIDEO =======

        video_name = output_name if output_name else Path(input_path).stem
        if not output_root:
            output_root_path = Path("Data/processed")
        else:
            output_root_path = Path(output_root)

        output_dir = output_root_path / video_name / "extraction"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / "audio_transcripts.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_output, f, ensure_ascii=False, indent=2)

        print(f"Saved transcript to {output_path}")

        return final_output
