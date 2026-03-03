from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from reasoning_nlp.aligner.confidence import compute_confidence
from reasoning_nlp.aligner.matcher import compute_adaptive_delta_ms, match_captions
from reasoning_nlp.aligner.normalize import normalize_for_alignment
from reasoning_nlp.common.errors import PipelineError
from reasoning_nlp.common.io_json import write_json
from reasoning_nlp.common.types import AlignmentBlock
from reasoning_nlp.pipeline.stages.stage_utils import append_stage_result
from reasoning_nlp.validators.artifact_validator import validate_alignment_artifact


def run_g2_align(
    config,
    validated,
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
) -> tuple[dict[str, Any], list[AlignmentBlock]]:
    import time

    started = time.perf_counter()
    stage = "align"
    try:
        transcripts, captions = normalize_for_alignment(validated.transcripts, validated.captions)
        delta_ms = compute_adaptive_delta_ms(
            transcripts=transcripts,
            k=config.align_k,
            min_delta_ms=config.align_min_delta_ms,
            max_delta_ms=config.align_max_delta_ms,
        )
        match_results = match_captions(
            transcripts=transcripts,
            captions=captions,
            delta_ms=delta_ms,
            assume_sorted=True,
        )

        blocks: list[AlignmentBlock] = []
        for caption, matched in zip(captions, match_results):
            confidence = compute_confidence(matched.fallback_type, matched.distance_ms, delta_ms)
            block = AlignmentBlock(
                caption_id=caption.caption_id,
                timestamp=caption.timestamp,
                image_text=caption.caption,
                dialogue_text=matched.dialogue_text,
                matched_transcript_ids=matched.transcript_ids,
                fallback_type=matched.fallback_type,
                confidence=confidence,
            )
            blocks.append(block)

        alignment_payload: dict[str, Any] = {
            "schema_version": "1.1",
            "delta_ms": delta_ms,
            "blocks": [asdict(b) for b in blocks],
        }

        schema_path = Path("docs/Reasoning-NLP/schema/alignment_result.schema.json")
        validate_alignment_artifact(alignment_payload, schema_path=schema_path)

        out_path = base / "g2_align" / "alignment_result.json"
        write_json(out_path, alignment_payload)

        append_stage_result(stage_results, stage, "pass", started)
        logger.info("run stage=%s status=pass", stage)
        return alignment_payload, blocks
    except PipelineError as err:
        append_stage_result(stage_results, stage, "fail", started, error_code=err.code)
        logger.error("run stage=%s status=fail error_code=%s", stage, err.code)
        raise
