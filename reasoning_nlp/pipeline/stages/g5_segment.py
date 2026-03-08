from __future__ import annotations

from pathlib import Path
from typing import Any

from reasoning_nlp.common.errors import PipelineError, fail
from reasoning_nlp.common.io_json import write_json
from reasoning_nlp.pipeline.stages.stage_utils import append_stage_result
from reasoning_nlp.segment_planner.extraction_selector import select_segments_from_extraction_boundaries
from reasoning_nlp.validators.artifact_validator import validate_deliverable_artifacts


def run_g5_segment_plan(
    config,
    context_payload: list[dict[str, Any]],
    summary_internal_payload: dict[str, Any],
    scene_timestamps_ms: list[int],
    source_duration_ms: int,
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
) -> tuple[dict[str, Any], dict[str, Any]]:
    import time

    started = time.perf_counter()
    stage = "segment_plan"
    try:
        selected_segments = select_segments_from_extraction_boundaries(
            context_blocks=context_payload,
            scene_timestamps_ms=scene_timestamps_ms,
            source_duration_ms=source_duration_ms,
            summary_plot=str(summary_internal_payload.get("plot_summary", "")),
            min_candidate_segment_ms=int(config.min_candidate_segment_ms),
            max_selected_segments=int(config.max_selected_segments),
            min_total_duration_ms=config.min_total_duration_ms,
            max_total_duration_ms=config.max_total_duration_ms,
        )
        if not selected_segments:
            raise fail(stage, "BUDGET_SEGMENTS_EMPTY", "No extraction-based segments selected")

        internal_segments = [
            {
                "segment_id": int(seg.segment_id),
                "source_start": str(seg.source_start),
                "source_end": str(seg.source_end),
                "script_text": str(seg.script_text),
                "confidence": float(seg.confidence),
                "role": str(seg.role),
            }
            for seg in selected_segments
        ]
        summary_internal_payload["segments"] = internal_segments

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
