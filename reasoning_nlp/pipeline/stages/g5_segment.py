from __future__ import annotations

from pathlib import Path
from typing import Any

from reasoning_nlp.common.errors import PipelineError, fail
from reasoning_nlp.common.io_json import write_json
from reasoning_nlp.pipeline.stages.stage_utils import append_stage_result
from reasoning_nlp.validators.artifact_validator import validate_deliverable_artifacts


def run_g5_segment_plan(
    config,
    context_payload: list[dict[str, Any]],
    summary_internal_payload: dict[str, Any],
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
) -> tuple[dict[str, Any], dict[str, Any]]:
    del context_payload
    import time

    started = time.perf_counter()
    stage = "segment_plan"
    try:
        internal_segments = summary_internal_payload.get("segments", [])
        if not isinstance(internal_segments, list) or not internal_segments:
            raise fail(stage, "BUDGET_SEGMENTS_EMPTY", "No internal segments generated")

        script_payload = {
            "title": str(summary_internal_payload.get("title", "Video Summary")).strip() or "Video Summary",
            "plot_summary": str(summary_internal_payload.get("plot_summary", "")).strip(),
            "moral_lesson": str(summary_internal_payload.get("moral_lesson", "")).strip(),
            "segments": [
                {
                    "segment_id": int(seg["segment_id"]),
                    "source_start": str(seg["source_start"]),
                    "source_end": str(seg["source_end"]),
                    "script_text": str(seg["script_text"]),
                }
                for seg in internal_segments
            ],
        }

        manifest_payload = {
            "source_video_path": str(config.raw_video_path),
            "output_video_path": "summary_video.mp4",
            "keep_original_audio": True,
            "segments": [
                {
                    "segment_id": int(seg["segment_id"]),
                    "source_start": str(seg["source_start"]),
                    "source_end": str(seg["source_end"]),
                    "script_ref": int(seg["segment_id"]),
                    "transition": "cut",
                }
                for seg in internal_segments
            ],
        }

        validate_deliverable_artifacts(
            script_payload=script_payload,
            manifest_payload=manifest_payload,
            script_schema_path=Path("contracts/v1/template/summary_script.schema.json"),
            manifest_schema_path=Path("contracts/v1/template/summary_video_manifest.schema.json"),
        )

        out_dir = base / "g5_segment"
        write_json(out_dir / "summary_script.json", script_payload)
        write_json(out_dir / "summary_video_manifest.json", manifest_payload)

        append_stage_result(stage_results, stage, "pass", started)
        logger.info("run stage=%s status=pass", stage)
        return script_payload, manifest_payload
    except PipelineError as err:
        append_stage_result(stage_results, stage, "fail", started, error_code=err.code)
        logger.error("run stage=%s status=fail error_code=%s", stage, err.code)
        raise
