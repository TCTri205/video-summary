from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from reasoning_nlp.assembler.video_probe import probe_source_duration_ms
from reasoning_nlp.common.errors import PipelineError
from reasoning_nlp.common.io_json import write_json
from reasoning_nlp.pipeline.stages.stage_utils import append_stage_result, is_simple_runtime
from reasoning_nlp.validators.input_validator import validate_and_normalize_inputs


def run_g1_validate(
    config,
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
):
    import time

    started = time.perf_counter()
    stage = "validate"
    try:
        validated = validate_and_normalize_inputs(
            audio_transcripts_path=Path(config.audio_transcripts_path),
            visual_captions_path=Path(config.visual_captions_path),
            scene_metadata_path=Path(config.scene_metadata_path),
            raw_video_path=Path(config.raw_video_path),
            profile=config.input_profile,
        )
        actual_duration_ms = probe_source_duration_ms(validated.raw_video_path)
        if config.source_duration_ms is not None:
            source_duration_ms = int(config.source_duration_ms)
            if abs(source_duration_ms - actual_duration_ms) > 1000:
                raise PipelineError(
                    stage=stage,
                    code="TIME_SOURCE_DURATION_OVERRIDE_MISMATCH",
                    message=(
                        f"Configured source_duration_ms={source_duration_ms} does not match probed video duration "
                        f"{actual_duration_ms}"
                    ),
                )
        else:
            source_duration_ms = actual_duration_ms
        if config.emit_internal_artifacts and not is_simple_runtime(config):
            out_path = base / "g1_validate" / "normalized_input.json"
            write_json(
                out_path,
                {
                    "input_profile": validated.input_profile,
                    "transcripts": [asdict(x) for x in validated.transcripts],
                    "captions": [asdict(x) for x in validated.captions],
                    "scene_timestamps_ms": list(validated.scene_timestamps_ms),
                    "raw_video_path": validated.raw_video_path,
                    "source_duration_ms": source_duration_ms,
                },
            )
        append_stage_result(stage_results, stage, "pass", started)
        logger.info("run stage=%s status=pass", stage)
        return validated, source_duration_ms
    except PipelineError as err:
        append_stage_result(stage_results, stage, "fail", started, error_code=err.code)
        logger.error("run stage=%s status=fail error_code=%s", stage, err.code)
        raise
