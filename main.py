from pathlib import Path
from extraction_perception.extraction.extraction import VideoPreprocessor
from extraction_perception.extraction.whisper_module import WhisperExtractor
from extraction_perception.perception.caption import VisualCaptioner

def run_video_pipeline(video_path: str, output_root: str):
    video_path = Path(video_path)
    output_root = Path(output_root)

    if not video_path.exists():
        print("❌ Video không tồn tại")
        return None

    processor = VideoPreprocessor(
        video_path=str(video_path),
        output_root=str(output_root)
    )

    print("🎬 Detecting scenes...")
    timestamps = processor.detect_scenes()
    print(f"✅ Found {len(timestamps)} scenes")

    print("🎧 Extracting audio...")
    audio_path = processor.extract_audio()
    print(f"✅ Audio saved at: {audio_path}")

    print("🖼 Extracting keyframes...")
    metadata = processor.extract_keyframes_and_metadata(timestamps)

    print("🎉 Extraction DONE")
    return metadata

def extract_transcripts_from_video(video_path: str):
    extractor = WhisperExtractor(
        model_size="base",
        device="cpu",
        compute_type="int8"
    )

    result = extractor.transcribe(
        input_path=video_path,
        language="vi"
    )

    return result

def run_caption(metadata_path: str, output_path: str):
    captioner = VisualCaptioner()

    captioner.caption_from_metadata(
        metadata_path=str(metadata_path),
        output_path=str(output_path)
    )

def main():
    video_path = Path(
        r"C:\ZtranCongDuc8125\TOHC\S-GROUP\AI\PROJECT\VIDEO_SUMARIZE\video-summary\Data\raw\video1.mp4"
    )

    output_root = Path(
        r"C:\ZtranCongDuc8125\TOHC\S-GROUP\AI\PROJECT\VIDEO_SUMARIZE\video-summary\Data\processed"
    )

    # 1️⃣ Extraction
    metadata = run_video_pipeline(video_path, output_root)

    if metadata is None:
        return

    # 2️⃣ ASR
    extract_transcripts_from_video(video_path=str(video_path))

    # 3️⃣ Caption
    video_name = video_path.stem
    metadata_path = output_root / video_name / "extraction" / "scene_metadata.json"
    output_path = output_root / video_name / "extraction" / "visual_captions.json"

    run_caption(
        metadata_path=str(metadata_path),
        output_path=str(output_path)
    )

if __name__ == "__main__":
    main()
