from __future__ import annotations

from pathlib import Path
from typing import Any

from reasoning_nlp.assembler.audio_policy import ensure_keep_original_audio
from reasoning_nlp.assembler.ffmpeg_runner import render_summary_video
from reasoning_nlp.common.errors import PipelineError, fail
from reasoning_nlp.common.io_json import write_json
from reasoning_nlp.pipeline.stages.stage_utils import append_stage_result


def run_g7_assemble(
    config,
    manifest_payload: dict[str, Any],
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
) -> dict[str, Any]:
    import time

    started = time.perf_counter()
    stage = "assemble"
    try:
        ensure_keep_original_audio(manifest_payload)
        output_path = str(base / "g7_assemble" / "summary_video.mp4")
        segments = manifest_payload.get("segments", [])
        if not isinstance(segments, list) or not segments:
            raise fail(stage, "RENDER_SEGMENTS_EMPTY", "Manifest must contain at least one segment")
        render_payload = render_summary_video(
            source_video_path=str(config.raw_video_path),
            output_video_path=output_path,
            segments=segments,
        )
        write_json(base / "g7_assemble" / "render_meta.json", render_payload)
        append_stage_result(stage_results, stage, "pass", started)
        logger.info("run stage=%s status=pass", stage)
        return render_payload
    except PipelineError as err:
        append_stage_result(stage_results, stage, "fail", started, error_code=err.code)
        logger.error("run stage=%s status=fail error_code=%s", stage, err.code)
        raise
