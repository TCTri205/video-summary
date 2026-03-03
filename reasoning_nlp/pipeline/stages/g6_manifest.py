from __future__ import annotations

from pathlib import Path
from typing import Any

from reasoning_nlp.assembler.manifest_builder import validate_manifest_stage
from reasoning_nlp.common.errors import PipelineError
from reasoning_nlp.common.io_json import write_json
from reasoning_nlp.pipeline.stages.stage_utils import append_stage_result


def run_g6_manifest(
    config,
    script_payload: dict[str, Any],
    manifest_payload: dict[str, Any],
    source_duration_ms: int | None,
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
) -> None:
    import time

    started = time.perf_counter()
    stage = "manifest"
    try:
        validate_manifest_stage(
            script_payload=script_payload,
            manifest_payload=manifest_payload,
            source_duration_ms=source_duration_ms,
        )
        if bool(config.emit_internal_artifacts):
            out_path = base / "g6_manifest" / "manifest_validation.json"
            write_json(out_path, {"status": "pass", "stage": stage})
        append_stage_result(stage_results, stage, "pass", started)
        logger.info("run stage=%s status=pass", stage)
    except PipelineError as err:
        append_stage_result(stage_results, stage, "fail", started, error_code=err.code)
        logger.error("run stage=%s status=fail error_code=%s", stage, err.code)
        raise
