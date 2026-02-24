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

    def transcribe(self, input_path: str, language: str = None):
        """
        input_path: Data/raw/video.mp4
        """

        print(f"Transcribing: {input_path}")

        segments, info = self.model.transcribe(
            input_path,
            language=language
        )

        results = []
        for segment in segments:
            results.append({
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip()
            })

        final_output = {
            "language": info.language,
            "duration": round(info.duration, 2),
            "segments": results
        }

        # ======= TẠO FOLDER THEO TÊN VIDEO =======

        video_name = Path(input_path).stem
        output_dir = Path("Data/processed") / video_name / "extraction"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / "audio_transcripts.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_output, f, ensure_ascii=False, indent=2)

        print(f"Saved transcript to {output_path}")

        return final_output
