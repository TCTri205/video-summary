from pathlib import Path
import json
import re
from extraction_perception.extraction.extraction import VideoPreprocessor
from extraction_perception.extraction.whisper_module import WhisperExtractor
from extraction_perception.perception.caption import VisualCaptioner


TIMESTAMP_RE = re.compile(r"^\d{2}:[0-5]\d:[0-5]\d\.\d{3}$")

def run_video_pipeline(video_path: str, output_root: str):
    video_path_obj = Path(video_path)
    output_root_obj = Path(output_root)

    if not video_path_obj.exists():
        print("❌ Video không tồn tại")
        return None

    processor = VideoPreprocessor(
        video_path=str(video_path_obj),
        output_root=str(output_root_obj)
    )

    print("(Detecting scenes)")
    timestamps = processor.detect_scenes()
    print(f"(Found {len(timestamps)} scenes)")

    print("(Extracting audio)")
    audio_path = processor.extract_audio()
    print(f"(Audio saved at: {audio_path})")

    print("(Extracting keyframes)")
    metadata = processor.extract_keyframes_and_metadata(timestamps)

    print("(Extraction DONE)")
    return {
        "metadata": metadata,
        "audio_path": audio_path,
    }

def extract_transcripts_from_video(video_path: str, output_root: str, output_name: str):
    extractor = WhisperExtractor(
        model_size="base",
        device="cpu",
        compute_type="int8"
    )

    result = extractor.transcribe(
        input_path=video_path,
        language="vi",
        output_root=output_root,
        output_name=output_name,
    )

    return result


def _to_ms(ts: str) -> int:
    parts = ts.replace('.', ':').split(':')
    hh = int(parts[0])
    mm = int(parts[1])
    ss = int(parts[2])
    ms = int(parts[3])
    return (((hh * 60) + mm) * 60 + ss) * 1000 + ms


def validate_handoff_outputs(transcript_path: str, captions_path: str):
    transcript_file = Path(transcript_path)
    captions_file = Path(captions_path)

    if not transcript_file.exists():
        raise RuntimeError(f"SCHEMA_INPUT_MISSING_FILE: {transcript_file}")
    if not captions_file.exists():
        raise RuntimeError(f"SCHEMA_INPUT_MISSING_FILE: {captions_file}")

    with transcript_file.open("r", encoding="utf-8") as f:
        transcripts = json.load(f)
    with captions_file.open("r", encoding="utf-8") as f:
        captions = json.load(f)

    if not isinstance(transcripts, list):
        raise RuntimeError("SCHEMA_INPUT_TRANSCRIPT_TYPE: audio_transcripts.json must be an array")
    if not isinstance(captions, list):
        raise RuntimeError("SCHEMA_INPUT_CAPTION_TYPE: visual_captions.json must be an array")

    prev_start = -1
    for idx, item in enumerate(transcripts, start=1):
        start = item.get("start", "")
        end = item.get("end", "")
        text = str(item.get("text", "")).strip()
        if not isinstance(start, str) or not isinstance(end, str):
            raise RuntimeError(f"SCHEMA_INPUT_TRANSCRIPT_FIELD_TYPE: item {idx} has non-string start/end")
        if not TIMESTAMP_RE.match(start) or not TIMESTAMP_RE.match(end):
            raise RuntimeError(f"TIME_PARSE_TRANSCRIPT_TIMESTAMP: item {idx} has invalid timestamp")
        s_ms = _to_ms(start)
        e_ms = _to_ms(end)
        if e_ms <= s_ms:
            raise RuntimeError(f"TIME_ORDER_TRANSCRIPT: item {idx} must satisfy start < end")
        if s_ms < prev_start:
            raise RuntimeError(f"TIME_SORT_TRANSCRIPT: item {idx} is out of order")
        if not text:
            raise RuntimeError(f"SCHEMA_INPUT_TRANSCRIPT_EMPTY_TEXT: item {idx} has empty text")
        prev_start = s_ms

    prev_ts = -1
    for idx, item in enumerate(captions, start=1):
        ts = item.get("timestamp", "")
        caption = str(item.get("caption", "")).strip()
        if not isinstance(ts, str):
            raise RuntimeError(f"SCHEMA_INPUT_CAPTION_FIELD_TYPE: item {idx} has non-string timestamp")
        if not TIMESTAMP_RE.match(ts):
            raise RuntimeError(f"TIME_PARSE_CAPTION_TIMESTAMP: item {idx} has invalid timestamp")
        ts_ms = _to_ms(ts)
        if ts_ms < prev_ts:
            raise RuntimeError(f"TIME_SORT_CAPTION: item {idx} is out of order")
        if not caption:
            raise RuntimeError(f"SCHEMA_INPUT_CAPTION_EMPTY_TEXT: item {idx} has empty caption")
        prev_ts = ts_ms

def run_caption(metadata_path: str, output_path: str):
    captioner = VisualCaptioner()

    captioner.caption_from_metadata(
        metadata_path=str(metadata_path),
        output_path=str(output_path)
    )

def main():
    video_path = Path("Data/raw/video1.mp4")

    output_root = Path("Data/processed")

    # 1️⃣ Extraction
    extraction_result = run_video_pipeline(str(video_path), str(output_root))

    if extraction_result is None:
        return

    audio_path = extraction_result["audio_path"]
    video_name = Path(video_path).stem

    # 2️⃣ ASR
    extract_transcripts_from_video(
        video_path=str(audio_path),
        output_root=str(output_root),
        output_name=video_name,
    )

    # 3️⃣ Caption
    metadata_path = output_root / video_name / "extraction" / "scene_metadata.json"
    output_path = output_root / video_name / "extraction" / "visual_captions.json"

    run_caption(
        metadata_path=str(metadata_path),
        output_path=str(output_path)
    )

    transcript_path = output_root / video_name / "extraction" / "audio_transcripts.json"
    validate_handoff_outputs(str(transcript_path), str(output_path))
    print("(Handoff validation passed)")

if __name__ == "__main__":
    main()
