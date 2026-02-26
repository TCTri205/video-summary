from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

TIMESTAMP_RE = re.compile(r"^\d{2}:[0-5]\d:[0-5]\d\.\d{3}$")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in {"1", "true", "yes", "y", "on"}:
            return True
        if raw in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def _load_json_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise RuntimeError(f"CONFIG_FILE_NOT_FOUND: {cfg_path}")
    with cfg_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError("CONFIG_FILE_INVALID: root must be a JSON object")
    return payload


def _resolve_value(cli_value: Any, env_name: str, config: dict[str, Any], config_key: str, default: Any) -> Any:
    if cli_value is not None:
        return cli_value
    env_value = os.getenv(env_name)
    if env_value is not None:
        return env_value
    if config_key in config:
        return config[config_key]
    return default


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run full Video Summary system (Module 1 -> 2 -> 3) in one command"
    )
    parser.add_argument("--config", default=None, help="Optional JSON config file")
    parser.add_argument("--video-path", default=None, help="Input video path")
    parser.add_argument("--output-root", default=None, help="Processed data root for module 1/2")
    parser.add_argument("--artifacts-root", default=None, help="Artifacts root for module 3")
    parser.add_argument("--deliverables-root", default=None, help="Final deliverables root for module 3")
    parser.add_argument("--run-id", default=None, help="Run id for module 3")
    parser.add_argument("--stage", choices=["g3", "g5", "g8"], default=None, help="Reasoning target stage")

    parser.add_argument("--scene-threshold", type=float, default=None, help="SceneDetect threshold")
    parser.add_argument("--keyframe-resize", type=int, choices=[336, 448], default=None)
    parser.add_argument("--asr-model-size", default=None, help="faster-whisper model size")
    parser.add_argument("--asr-device", default=None, choices=["cpu", "cuda"], help="ASR compute device")
    parser.add_argument("--asr-compute-type", default=None, help="ASR compute type (ex: int8, float16)")
    parser.add_argument("--asr-language", default=None, help="ASR language code")
    parser.add_argument("--caption-model", default=None, help="Caption model id")
    parser.add_argument("--caption-batch-size", type=int, default=None)

    parser.add_argument("--input-profile", default=None, choices=["strict_contract_v1", "legacy_member1"])
    parser.add_argument("--source-duration-ms", type=int, default=None)
    parser.add_argument("--summarize-backend", choices=["api", "local", "heuristic"], default=None)
    parser.add_argument("--summarize-fallback-backend", choices=["api", "local", "heuristic"], default=None)
    parser.add_argument("--summarize-timeout-ms", type=int, default=None)
    parser.add_argument("--summarize-max-retries", type=int, default=None)
    parser.add_argument("--summarize-max-new-tokens", type=int, default=None)
    parser.add_argument("--summarize-prompt-max-chars", type=int, default=None)

    parser.add_argument("--qc-enforce-thresholds", action="store_true", default=None)
    parser.add_argument("--replay", action="store_true", default=None)
    parser.add_argument("--strict-replay-hash", action="store_true", default=None)
    return parser.parse_args()


def _to_ms(ts: str) -> int:
    parts = ts.replace(".", ":").split(":")
    hh = int(parts[0])
    mm = int(parts[1])
    ss = int(parts[2])
    ms = int(parts[3])
    return (((hh * 60) + mm) * 60 + ss) * 1000 + ms


def _preflight(video_path: Path) -> None:
    if not video_path.exists():
        raise RuntimeError(f"INPUT_VIDEO_NOT_FOUND: {video_path}")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("DEPENDENCY_MISSING: ffmpeg is not available in PATH")
    if shutil.which("ffprobe") is None:
        raise RuntimeError("DEPENDENCY_MISSING: ffprobe is not available in PATH")


def run_video_pipeline(video_path: str, output_root: str, scene_threshold: float, keyframe_resize: int):
    from extraction_perception.extraction.extraction import VideoPreprocessor

    video_path_obj = Path(video_path)
    output_root_obj = Path(output_root)

    processor = VideoPreprocessor(
        video_path=str(video_path_obj),
        output_root=str(output_root_obj),
        resize=keyframe_resize,
    )

    print("(Detecting scenes)")
    timestamps = processor.detect_scenes(threshold=scene_threshold)
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


def extract_transcripts_from_video(
    video_path: str,
    output_root: str,
    output_name: str,
    model_size: str,
    device: str,
    compute_type: str,
    language: str,
):
    from extraction_perception.extraction.whisper_module import WhisperExtractor

    extractor = WhisperExtractor(model_size=model_size, device=device, compute_type=compute_type)
    return extractor.transcribe(
        input_path=video_path,
        language=language,
        output_root=output_root,
        output_name=output_name,
    )


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


def run_caption(metadata_path: str, output_path: str, model_name: str, batch_size: int | None):
    from extraction_perception.perception.caption import VisualCaptioner

    captioner = VisualCaptioner(model_name=model_name)
    return captioner.caption_from_metadata(metadata_path=str(metadata_path), output_path=str(output_path), batch_size=batch_size)


def _run_reasoning_stage(config: Any, stage: str) -> dict[str, Any]:
    from reasoning_nlp.pipeline_runner import run_pipeline_g1_g3, run_pipeline_g1_g5, run_pipeline_g1_g8

    if stage == "g3":
        return run_pipeline_g1_g3(config)
    if stage == "g5":
        return run_pipeline_g1_g5(config)
    return run_pipeline_g1_g8(config)


def main() -> int:
    args = parse_args()
    file_config = _load_json_config(args.config)

    video_path = Path(_resolve_value(args.video_path, "VIDEO_SUMMARY_VIDEO_PATH", file_config, "video_path", "Data/raw/video1.mp4"))
    output_root = Path(_resolve_value(args.output_root, "VIDEO_SUMMARY_OUTPUT_ROOT", file_config, "output_root", "Data/processed"))
    artifacts_root = str(_resolve_value(args.artifacts_root, "VIDEO_SUMMARY_ARTIFACTS_ROOT", file_config, "artifacts_root", "artifacts"))
    deliverables_root = str(
        _resolve_value(args.deliverables_root, "VIDEO_SUMMARY_DELIVERABLES_ROOT", file_config, "deliverables_root", "deliverables")
    )
    stage = str(_resolve_value(args.stage, "VIDEO_SUMMARY_STAGE", file_config, "stage", "g8"))

    scene_threshold = float(_resolve_value(args.scene_threshold, "VIDEO_SUMMARY_SCENE_THRESHOLD", file_config, "scene_threshold", 27.0))
    keyframe_resize = int(_resolve_value(args.keyframe_resize, "VIDEO_SUMMARY_KEYFRAME_RESIZE", file_config, "keyframe_resize", 448))
    asr_model_size = str(_resolve_value(args.asr_model_size, "VIDEO_SUMMARY_ASR_MODEL_SIZE", file_config, "asr_model_size", "base"))
    asr_device = str(_resolve_value(args.asr_device, "VIDEO_SUMMARY_ASR_DEVICE", file_config, "asr_device", "cpu"))
    asr_compute_type = str(_resolve_value(args.asr_compute_type, "VIDEO_SUMMARY_ASR_COMPUTE_TYPE", file_config, "asr_compute_type", "int8"))
    asr_language = str(_resolve_value(args.asr_language, "VIDEO_SUMMARY_ASR_LANGUAGE", file_config, "asr_language", "vi"))
    caption_model = str(
        _resolve_value(
            args.caption_model,
            "VIDEO_SUMMARY_CAPTION_MODEL",
            file_config,
            "caption_model",
            "Salesforce/blip-image-captioning-base",
        )
    )
    caption_batch_size_raw = _resolve_value(
        args.caption_batch_size,
        "VIDEO_SUMMARY_CAPTION_BATCH_SIZE",
        file_config,
        "caption_batch_size",
        None,
    )
    caption_batch_size = int(caption_batch_size_raw) if caption_batch_size_raw is not None else None

    input_profile = str(
        _resolve_value(
            args.input_profile,
            "VIDEO_SUMMARY_INPUT_PROFILE",
            file_config,
            "input_profile",
            "strict_contract_v1",
        )
    )
    source_duration_ms_raw = _resolve_value(
        args.source_duration_ms,
        "VIDEO_SUMMARY_SOURCE_DURATION_MS",
        file_config,
        "source_duration_ms",
        None,
    )
    source_duration_ms = int(source_duration_ms_raw) if source_duration_ms_raw is not None else None

    summarize_backend = str(
        _resolve_value(
            args.summarize_backend,
            "VIDEO_SUMMARY_SUMMARIZE_BACKEND",
            file_config,
            "summarize_backend",
            "local",
        )
    )
    summarize_fallback_backend = str(
        _resolve_value(
            args.summarize_fallback_backend,
            "VIDEO_SUMMARY_SUMMARIZE_FALLBACK_BACKEND",
            file_config,
            "summarize_fallback_backend",
            "local",
        )
    )
    summarize_timeout_ms = int(
        _resolve_value(
            args.summarize_timeout_ms,
            "VIDEO_SUMMARY_SUMMARIZE_TIMEOUT_MS",
            file_config,
            "summarize_timeout_ms",
            30000,
        )
    )
    summarize_max_retries = int(
        _resolve_value(
            args.summarize_max_retries,
            "VIDEO_SUMMARY_SUMMARIZE_MAX_RETRIES",
            file_config,
            "summarize_max_retries",
            2,
        )
    )
    summarize_max_new_tokens = int(
        _resolve_value(
            args.summarize_max_new_tokens,
            "VIDEO_SUMMARY_SUMMARIZE_MAX_NEW_TOKENS",
            file_config,
            "summarize_max_new_tokens",
            512,
        )
    )
    summarize_prompt_max_chars_raw = _resolve_value(
        args.summarize_prompt_max_chars,
        "VIDEO_SUMMARY_SUMMARIZE_PROMPT_MAX_CHARS",
        file_config,
        "summarize_prompt_max_chars",
        12000,
    )
    summarize_prompt_max_chars = int(summarize_prompt_max_chars_raw) if summarize_prompt_max_chars_raw is not None else None

    run_id = str(
        _resolve_value(
            args.run_id,
            "VIDEO_SUMMARY_RUN_ID",
            file_config,
            "run_id",
            f"run_{uuid.uuid4().hex[:8]}",
        )
    )

    qc_enforce_thresholds = _coerce_bool(
        _resolve_value(
            args.qc_enforce_thresholds,
            "VIDEO_SUMMARY_QC_ENFORCE_THRESHOLDS",
            file_config,
            "qc_enforce_thresholds",
            False,
        )
    )
    replay = _coerce_bool(_resolve_value(args.replay, "VIDEO_SUMMARY_REPLAY", file_config, "replay", False))
    strict_replay_hash = _coerce_bool(
        _resolve_value(
            args.strict_replay_hash,
            "VIDEO_SUMMARY_STRICT_REPLAY_HASH",
            file_config,
            "strict_replay_hash",
            False,
        )
    )

    if "VIDEO_SUMMARY_QC_ENFORCE_THRESHOLDS" in os.environ:
        qc_enforce_thresholds = _env_bool("VIDEO_SUMMARY_QC_ENFORCE_THRESHOLDS", qc_enforce_thresholds)
    if "VIDEO_SUMMARY_REPLAY" in os.environ:
        replay = _env_bool("VIDEO_SUMMARY_REPLAY", replay)
    if "VIDEO_SUMMARY_STRICT_REPLAY_HASH" in os.environ:
        strict_replay_hash = _env_bool("VIDEO_SUMMARY_STRICT_REPLAY_HASH", strict_replay_hash)

    if stage not in {"g3", "g5", "g8"}:
        raise RuntimeError(f"INVALID_STAGE: {stage}. Use g3, g5, or g8")

    try:
        _preflight(video_path)
        output_root.mkdir(parents=True, exist_ok=True)

        print("=== Module 1: Extraction ===")
        extraction_result = run_video_pipeline(
            video_path=str(video_path),
            output_root=str(output_root),
            scene_threshold=scene_threshold,
            keyframe_resize=keyframe_resize,
        )
        audio_path = extraction_result["audio_path"]
        video_name = video_path.stem

        print("=== Module 2: Perception ===")
        extract_transcripts_from_video(
            video_path=str(audio_path),
            output_root=str(output_root),
            output_name=video_name,
            model_size=asr_model_size,
            device=asr_device,
            compute_type=asr_compute_type,
            language=asr_language,
        )

        metadata_path = output_root / video_name / "extraction" / "scene_metadata.json"
        captions_path = output_root / video_name / "extraction" / "visual_captions.json"
        transcripts_path = output_root / video_name / "extraction" / "audio_transcripts.json"

        run_caption(
            metadata_path=str(metadata_path),
            output_path=str(captions_path),
            model_name=caption_model,
            batch_size=caption_batch_size,
        )
        validate_handoff_outputs(str(transcripts_path), str(captions_path))
        print("(Handoff validation passed)")

        print(f"=== Module 3: Reasoning ({stage}) ===")
        from reasoning_nlp.common.errors import PipelineError
        from reasoning_nlp.pipeline_runner import PipelineConfig

        pipeline_cfg = PipelineConfig(
            audio_transcripts_path=str(transcripts_path),
            visual_captions_path=str(captions_path),
            raw_video_path=str(video_path),
            run_id=run_id,
            artifacts_root=artifacts_root,
            deliverables_root=deliverables_root,
            input_profile=input_profile,
            source_duration_ms=source_duration_ms,
            summarize_backend=summarize_backend,
            summarize_fallback_backend=summarize_fallback_backend,
            summarize_timeout_ms=summarize_timeout_ms,
            summarize_max_retries=summarize_max_retries,
            summarize_max_new_tokens=summarize_max_new_tokens,
            summarize_prompt_max_chars=summarize_prompt_max_chars,
            qc_enforce_thresholds=qc_enforce_thresholds,
            strict_replay_hash=strict_replay_hash,
            replay_mode=replay,
        )

        result = _run_reasoning_stage(pipeline_cfg, stage)
        print("=== Pipeline completed ===")
        print(json.dumps({"run_id": result["run_id"], "stage_results": result["stage_results"]}, ensure_ascii=False, indent=2))

        if stage == "g8":
            base = Path(artifacts_root) / run_id
            final_dir = Path(deliverables_root) / run_id
            print("Final deliverables:")
            print(f"- {final_dir / 'summary_video.mp4'}")
            print(f"- {final_dir / 'summary_text.txt'}")
            print("Debug artifacts:")
            print(f"- {base / 'g5_segment' / 'summary_script.json'}")
            print(f"- {base / 'g5_segment' / 'summary_video_manifest.json'}")
            print(f"- {base / 'g8_qc' / 'quality_report.json'}")

        return 0
    except Exception as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
