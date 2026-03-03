from __future__ import annotations

from pathlib import Path
from typing import Any

from reasoning_nlp.aligner.context_builder import build_context_blocks
from reasoning_nlp.common.errors import PipelineError
from reasoning_nlp.common.io_json import write_json
from reasoning_nlp.pipeline.stages.stage_utils import append_stage_result


def run_g3_context(
    blocks,
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
) -> list[dict[str, Any]]:
    import time

    started = time.perf_counter()
    stage = "context_build"
    try:
        context_payload = build_context_blocks(blocks)
        out_path = base / "g3_context" / "context_blocks.json"
        write_json(out_path, context_payload)
        append_stage_result(stage_results, stage, "pass", started)
        logger.info("run stage=%s status=pass", stage)
        return context_payload
    except PipelineError as err:
        append_stage_result(stage_results, stage, "fail", started, error_code=err.code)
        logger.error("run stage=%s status=fail error_code=%s", stage, err.code)
        raise
