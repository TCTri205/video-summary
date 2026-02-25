from __future__ import annotations

import json
import hashlib
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from reasoning_nlp.aligner.confidence import compute_confidence
from reasoning_nlp.aligner.context_builder import build_context_blocks
from reasoning_nlp.aligner.matcher import compute_adaptive_delta_ms, match_captions
from reasoning_nlp.aligner.normalize import normalize_for_alignment
from reasoning_nlp.assembler.audio_policy import ensure_keep_original_audio
from reasoning_nlp.assembler.ffmpeg_runner import render_summary_video
from reasoning_nlp.assembler.manifest_builder import validate_manifest_stage
from reasoning_nlp.assembler.video_probe import probe_source_duration_ms
from reasoning_nlp.common.errors import PipelineError, fail
from reasoning_nlp.common.io_json import read_json, write_json
from reasoning_nlp.common.logging import get_logger
from reasoning_nlp.common.types import AlignmentBlock, CanonicalCaption, CanonicalTranscript
from reasoning_nlp.config.defaults import DEFAULT_ALIGNMENT, DEFAULT_QC, DEFAULT_RUNTIME, DEFAULT_SEGMENT_BUDGET, DEFAULT_SUMMARIZATION
from reasoning_nlp.qc.metrics import (
    compute_alignment_metrics,
    compute_black_frame_ratio,
    compute_compression_ratio,
    compute_grounding_score,
    compute_parse_validity_rate,
    compute_timeline_consistency,
)
from reasoning_nlp.qc.report_builder import build_quality_report
from reasoning_nlp.segment_planner.budget_policy import BudgetConfig
from reasoning_nlp.segment_planner.planner import plan_segments_from_context
from reasoning_nlp.summarizer.grounding_checks import check_grounding
from reasoning_nlp.summarizer.llm_client import generate_internal_summary
from reasoning_nlp.summarizer.parse_repair import repair_internal_summary
from reasoning_nlp.validators.artifact_validator import (
    validate_alignment_artifact,
    validate_deliverable_artifacts,
    validate_quality_report_artifact,
    validate_summary_internal_artifact,
)
from reasoning_nlp.validators.input_validator import validate_and_normalize_inputs


STAGE_ORDER = ["validate", "align", "context_build", "summarize", "segment_plan", "manifest", "assemble", "qc"]


@dataclass(frozen=True)
class PipelineConfig:
    audio_transcripts_path: str
    visual_captions_path: str
    raw_video_path: str
    run_id: str | None = None
    artifacts_root: str = DEFAULT_RUNTIME["artifacts_root"]
    input_profile: str = DEFAULT_RUNTIME["input_profile"]
    align_k: float = float(DEFAULT_ALIGNMENT["k"])
    align_min_delta_ms: int = int(DEFAULT_ALIGNMENT["min_delta_ms"])
    align_max_delta_ms: int = int(DEFAULT_ALIGNMENT["max_delta_ms"])
    summarize_seed: int = int(DEFAULT_SUMMARIZATION["seed"])
    summarize_temperature: float = float(DEFAULT_SUMMARIZATION["temperature"])
    model_version: str = str(DEFAULT_SUMMARIZATION["model_version"])
    tokenizer_version: str = str(DEFAULT_SUMMARIZATION["tokenizer_version"])
    summarize_backend: str = str(DEFAULT_SUMMARIZATION["backend"])
    summarize_fallback_backend: str = str(DEFAULT_SUMMARIZATION["fallback_backend"])
    summarize_timeout_ms: int = int(DEFAULT_SUMMARIZATION["timeout_ms"])
    summarize_max_retries: int = int(DEFAULT_SUMMARIZATION["max_retries"])
    summarize_max_new_tokens: int = int(DEFAULT_SUMMARIZATION["max_new_tokens"])
    summarize_do_sample: bool = bool(DEFAULT_SUMMARIZATION["do_sample"])
    source_duration_ms: int | None = None
    min_segment_duration_ms: int = int(DEFAULT_SEGMENT_BUDGET["min_segment_duration_ms"])
    max_segment_duration_ms: int = int(DEFAULT_SEGMENT_BUDGET["max_segment_duration_ms"])
    min_total_duration_ms: int | None = int(DEFAULT_SEGMENT_BUDGET["min_total_duration_ms"])
    max_total_duration_ms: int | None = int(DEFAULT_SEGMENT_BUDGET["max_total_duration_ms"])
    target_ratio: float | None = DEFAULT_SEGMENT_BUDGET["target_ratio"]
    target_ratio_tolerance: float = float(DEFAULT_SEGMENT_BUDGET["target_ratio_tolerance"])
    qc_enforce_thresholds: bool = bool(DEFAULT_QC["enforce_thresholds"])
    qc_min_parse_validity_rate: float = float(DEFAULT_QC["min_parse_validity_rate"])
    qc_min_timeline_consistency_score: float = float(DEFAULT_QC["min_timeline_consistency_score"])
    qc_min_grounding_score: float = float(DEFAULT_QC["min_grounding_score"])
    qc_max_black_frame_ratio: float = float(DEFAULT_QC["max_black_frame_ratio"])
    qc_max_no_match_rate: float = float(DEFAULT_QC["max_no_match_rate"])
    qc_min_median_confidence: float = float(DEFAULT_QC["min_median_confidence"])
    qc_min_high_confidence_ratio: float = float(DEFAULT_QC["min_high_confidence_ratio"])
    emit_internal_artifacts: bool = bool(DEFAULT_RUNTIME["emit_internal_artifacts"])
    replay_mode: bool = False


def run_pipeline_g1_g3(config: PipelineConfig) -> dict[str, Any]:
    logger = get_logger()
    run_id = config.run_id or _new_run_id()
    base = Path(config.artifacts_root) / run_id
    stage_results: list[dict[str, Any]] = []

    try:
        validated, _ = _run_g1_validate(config, base, stage_results, logger)
        alignment_payload, alignment_blocks = _run_g2_align(config, validated, base, stage_results, logger)
        context_payload = _run_g3_context(alignment_blocks, base, stage_results, logger)
    except PipelineError:
        raise
    except Exception as exc:
        raise fail("pipeline", "PIPELINE_UNEXPECTED", str(exc)) from exc

    return {
        "run_id": run_id,
        "stage_results": stage_results,
        "artifacts": {
            "alignment_result": str(base / "g2_align" / "alignment_result.json"),
            "context_blocks": str(base / "g3_context" / "context_blocks.json"),
        },
        "alignment_result": alignment_payload,
        "context_blocks": context_payload,
    }


def run_pipeline_g1_g5(config: PipelineConfig) -> dict[str, Any]:
    logger = get_logger()
    run_id = config.run_id or _new_run_id()
    base = Path(config.artifacts_root) / run_id
    stage_results: list[dict[str, Any]] = []

    try:
        validated, source_duration_ms = _run_g1_validate(config, base, stage_results, logger)
        alignment_payload, alignment_blocks = _run_g2_align(config, validated, base, stage_results, logger)
        context_payload = _run_g3_context(alignment_blocks, base, stage_results, logger)
        summary_internal_payload = _run_g4_summarize(
            config,
            context_payload,
            source_duration_ms,
            base,
            stage_results,
            logger,
        )
        script_payload, manifest_payload = _run_g5_segment_plan(config, context_payload, summary_internal_payload, base, stage_results, logger)
    except PipelineError:
        raise
    except Exception as exc:
        raise fail("pipeline", "PIPELINE_UNEXPECTED", str(exc)) from exc

    return {
        "run_id": run_id,
        "stage_results": stage_results,
        "artifacts": {
            "alignment_result": str(base / "g2_align" / "alignment_result.json"),
            "context_blocks": str(base / "g3_context" / "context_blocks.json"),
            "summary_script_internal": str(base / "g4_summarize" / "summary_script.internal.json"),
            "summary_script": str(base / "g5_segment" / "summary_script.json"),
            "summary_video_manifest": str(base / "g5_segment" / "summary_video_manifest.json"),
        },
        "alignment_result": alignment_payload,
        "context_blocks": context_payload,
        "summary_script_internal": summary_internal_payload,
        "summary_script": script_payload,
        "summary_video_manifest": manifest_payload,
    }


def run_pipeline_g1_g8(config: PipelineConfig) -> dict[str, Any]:
    logger = get_logger()
    run_id = config.run_id or _new_run_id()
    base = Path(config.artifacts_root) / run_id
    stage_results: list[dict[str, Any]] = []
    replay_enabled = bool(config.replay_mode)
    run_meta = _build_run_meta(config)
    stage_hashes = cast(dict[str, str], run_meta.get("stage_hashes", {}))

    try:
        validated, source_duration_ms = _replay_or_run_g1(
            config,
            base,
            stage_results,
            logger,
            replay_enabled,
            stage_hashes,
        )
        alignment_payload, alignment_blocks = _replay_or_run_g2(
            config,
            validated,
            base,
            stage_results,
            logger,
            replay_enabled,
            stage_hashes,
        )
        context_payload = _replay_or_run_g3(base, stage_results, logger, replay_enabled, alignment_blocks, stage_hashes)
        summary_internal_payload = _replay_or_run_g4(
            config,
            context_payload,
            source_duration_ms,
            base,
            stage_results,
            logger,
            replay_enabled,
            stage_hashes,
        )
        script_payload, manifest_payload = _replay_or_run_g5(
            config,
            context_payload,
            summary_internal_payload,
            base,
            stage_results,
            logger,
            replay_enabled,
            stage_hashes,
        )
        _replay_or_run_g6(
            config,
            script_payload,
            manifest_payload,
            source_duration_ms,
            base,
            stage_results,
            logger,
            replay_enabled,
            stage_hashes,
        )
        assemble_payload = _replay_or_run_g7(
            config,
            manifest_payload,
            base,
            stage_results,
            logger,
            replay_enabled,
            stage_hashes,
        )
        quality_report = _run_g8_qc(
            config,
            run_id,
            alignment_payload,
            context_payload,
            summary_internal_payload,
            script_payload,
            manifest_payload,
            assemble_payload,
            source_duration_ms,
            base,
            stage_results,
            logger,
        )
        _write_run_meta(base, run_meta)
    except PipelineError:
        raise
    except Exception as exc:
        raise fail("pipeline", "PIPELINE_UNEXPECTED", str(exc)) from exc

    return {
        "run_id": run_id,
        "stage_results": stage_results,
        "artifacts": {
            "alignment_result": str(base / "g2_align" / "alignment_result.json"),
            "context_blocks": str(base / "g3_context" / "context_blocks.json"),
            "summary_script_internal": str(base / "g4_summarize" / "summary_script.internal.json"),
            "summary_script": str(base / "g5_segment" / "summary_script.json"),
            "summary_video_manifest": str(base / "g5_segment" / "summary_video_manifest.json"),
            "summary_video": str(base / "g7_assemble" / "summary_video.mp4"),
            "quality_report": str(base / "g8_qc" / "quality_report.json"),
        },
        "summary_script": script_payload,
        "summary_video_manifest": manifest_payload,
        "assemble": assemble_payload,
        "quality_report": quality_report,
    }


def _run_g1_validate(
    config: PipelineConfig,
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
):
    started = time.perf_counter()
    stage = "validate"
    try:
        validated = validate_and_normalize_inputs(
            audio_transcripts_path=Path(config.audio_transcripts_path),
            visual_captions_path=Path(config.visual_captions_path),
            raw_video_path=Path(config.raw_video_path),
            profile=config.input_profile,
        )
        source_duration_ms = int(config.source_duration_ms) if config.source_duration_ms is not None else probe_source_duration_ms(
            validated.raw_video_path
        )
        if config.emit_internal_artifacts:
            out_path = base / "g1_validate" / "normalized_input.json"
            write_json(
                out_path,
                {
                    "input_profile": validated.input_profile,
                    "transcripts": [asdict(x) for x in validated.transcripts],
                    "captions": [asdict(x) for x in validated.captions],
                    "raw_video_path": validated.raw_video_path,
                    "source_duration_ms": source_duration_ms,
                },
            )
        _append_stage_result(stage_results, stage, "pass", started)
        logger.info("run stage=%s status=pass", stage)
        return validated, source_duration_ms
    except PipelineError as err:
        _append_stage_result(stage_results, stage, "fail", started, error_code=err.code)
        logger.error("run stage=%s status=fail error_code=%s", stage, err.code)
        raise


def _run_g2_align(
    config: PipelineConfig,
    validated,
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
) -> tuple[dict[str, Any], list[AlignmentBlock]]:
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
        match_results = match_captions(transcripts=transcripts, captions=captions, delta_ms=delta_ms)

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

        _append_stage_result(stage_results, stage, "pass", started)
        logger.info("run stage=%s status=pass", stage)
        return alignment_payload, blocks
    except PipelineError as err:
        _append_stage_result(stage_results, stage, "fail", started, error_code=err.code)
        logger.error("run stage=%s status=fail error_code=%s", stage, err.code)
        raise


def _run_g3_context(
    blocks: list[AlignmentBlock],
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
) -> list[dict[str, Any]]:
    started = time.perf_counter()
    stage = "context_build"
    try:
        context_payload = build_context_blocks(blocks)
        out_path = base / "g3_context" / "context_blocks.json"
        write_json(out_path, context_payload)
        _append_stage_result(stage_results, stage, "pass", started)
        logger.info("run stage=%s status=pass", stage)
        return context_payload
    except PipelineError as err:
        _append_stage_result(stage_results, stage, "fail", started, error_code=err.code)
        logger.error("run stage=%s status=fail error_code=%s", stage, err.code)
        raise


def _run_g4_summarize(
    config: PipelineConfig,
    context_payload: list[dict[str, Any]],
    source_duration_ms: int | None,
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
) -> dict[str, Any]:
    started = time.perf_counter()
    stage = "summarize"
    try:
        raw = generate_internal_summary(
            context_blocks=context_payload,
            run_seed=config.summarize_seed,
            model_version=config.model_version,
            tokenizer_version=config.tokenizer_version,
            temperature=config.summarize_temperature,
            backend=config.summarize_backend,
            fallback_backend=config.summarize_fallback_backend,
            timeout_ms=config.summarize_timeout_ms,
            max_retries=config.summarize_max_retries,
            max_new_tokens=config.summarize_max_new_tokens,
            do_sample=config.summarize_do_sample,
        )
        repaired = repair_internal_summary(raw)
        repaired.setdefault("quality_flags", [])
        repaired["quality_flags"] = list(repaired["quality_flags"])
        repaired["quality_flags"].append(f"model_version={config.model_version}")
        repaired["quality_flags"].append(f"tokenizer_version={config.tokenizer_version}")
        grounding_errors = check_grounding(repaired, context_payload)
        if grounding_errors:
            repaired["quality_flags"] = list(sorted(set(list(repaired["quality_flags"]) + grounding_errors)))
        else:
            repaired["quality_flags"] = list(sorted(set(repaired["quality_flags"])))

        budget = BudgetConfig(
            min_segment_duration_ms=config.min_segment_duration_ms,
            max_segment_duration_ms=config.max_segment_duration_ms,
            min_total_duration_ms=config.min_total_duration_ms,
            max_total_duration_ms=config.max_total_duration_ms,
            target_ratio=config.target_ratio,
            target_ratio_tolerance=config.target_ratio_tolerance,
        )
        planned = plan_segments_from_context(
            context_blocks=context_payload,
            summary_plot=str(repaired.get("plot_summary", "")),
            budget=budget,
            source_duration_ms=source_duration_ms,
        )
        repaired["segments"] = [asdict(s) for s in planned]

        schema_path = Path("docs/Reasoning-NLP/schema/summary_script.internal.schema.json")
        validate_summary_internal_artifact(repaired, schema_path=schema_path)

        out_path = base / "g4_summarize" / "summary_script.internal.json"
        write_json(out_path, repaired)

        _append_stage_result(stage_results, stage, "pass", started)
        logger.info("run stage=%s status=pass", stage)
        return repaired
    except PipelineError as err:
        _append_stage_result(stage_results, stage, "fail", started, error_code=err.code)
        logger.error("run stage=%s status=fail error_code=%s", stage, err.code)
        raise


def _run_g5_segment_plan(
    config: PipelineConfig,
    context_payload: list[dict[str, Any]],
    summary_internal_payload: dict[str, Any],
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
) -> tuple[dict[str, Any], dict[str, Any]]:
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

        _append_stage_result(stage_results, stage, "pass", started)
        logger.info("run stage=%s status=pass", stage)
        return script_payload, manifest_payload
    except PipelineError as err:
        _append_stage_result(stage_results, stage, "fail", started, error_code=err.code)
        logger.error("run stage=%s status=fail error_code=%s", stage, err.code)
        raise


def _run_g6_manifest(
    config: PipelineConfig,
    script_payload: dict[str, Any],
    manifest_payload: dict[str, Any],
    source_duration_ms: int | None,
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
) -> None:
    started = time.perf_counter()
    stage = "manifest"
    try:
        validate_manifest_stage(
            script_payload=script_payload,
            manifest_payload=manifest_payload,
            source_duration_ms=source_duration_ms,
        )
        out_path = base / "g6_manifest" / "manifest_validation.json"
        write_json(out_path, {"status": "pass", "stage": stage})
        _append_stage_result(stage_results, stage, "pass", started)
        logger.info("run stage=%s status=pass", stage)
    except PipelineError as err:
        _append_stage_result(stage_results, stage, "fail", started, error_code=err.code)
        logger.error("run stage=%s status=fail error_code=%s", stage, err.code)
        raise


def _run_g7_assemble(
    config: PipelineConfig,
    manifest_payload: dict[str, Any],
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
) -> dict[str, Any]:
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
        _append_stage_result(stage_results, stage, "pass", started)
        logger.info("run stage=%s status=pass", stage)
        return render_payload
    except PipelineError as err:
        _append_stage_result(stage_results, stage, "fail", started, error_code=err.code)
        logger.error("run stage=%s status=fail error_code=%s", stage, err.code)
        raise


def _run_g8_qc(
    config: PipelineConfig,
    run_id: str,
    alignment_payload: dict[str, Any],
    context_payload: list[dict[str, Any]],
    summary_internal_payload: dict[str, Any],
    script_payload: dict[str, Any],
    manifest_payload: dict[str, Any],
    assemble_payload: dict[str, Any],
    source_duration_ms: int | None,
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
) -> dict[str, Any]:
    started = time.perf_counter()
    stage = "qc"
    try:
        alignment_metrics = compute_alignment_metrics(alignment_payload)
        timeline_consistency_score = compute_timeline_consistency(script_payload, manifest_payload)
        compression_ratio = compute_compression_ratio(script_payload, source_duration_ms)
        grounding_score = compute_grounding_score(summary_internal_payload, context_payload)
        parse_validity_rate = compute_parse_validity_rate(summary_internal_payload)
        output_video_path = str(base / "g7_assemble" / "summary_video.mp4")
        black_frame_ratio = compute_black_frame_ratio(
            output_video_path, duration_ms=int(assemble_payload.get("duration_ms", 0))
        )
        metrics = {
            "parse_validity_rate": parse_validity_rate,
            "timeline_consistency_score": timeline_consistency_score,
            "grounding_score": grounding_score,
            "compression_ratio": compression_ratio,
            "manifest_consistency_pass": True,
            "render_success": bool(assemble_payload.get("render_success", False)),
            "audio_present": bool(assemble_payload.get("audio_present", False)),
            "duration_match_score": float(assemble_payload.get("duration_match_score", 0.0)),
            "black_frame_ratio": black_frame_ratio,
            "decode_error_count": int(assemble_payload.get("decode_error_count", 0)),
            "no_match_rate": alignment_metrics["no_match_rate"],
            "median_confidence": alignment_metrics["median_confidence"],
            "high_confidence_ratio": alignment_metrics["high_confidence_ratio"],
        }

        warnings: list[str] = []
        if metrics["no_match_rate"] > 0.30:
            warnings.append("ALIGN_LOW_MATCH_COVERAGE")
        if metrics["median_confidence"] < 0.60:
            warnings.append("ALIGN_LOW_CONFIDENCE")
        if metrics["high_confidence_ratio"] < 0.50:
            warnings.append("ALIGN_WEAK_GROUNDING_SIGNAL")

        threshold_errors: list[dict[str, str]] = []
        if bool(config.qc_enforce_thresholds):
            checks = [
                ("QC_PARSE_VALIDITY_LOW", metrics["parse_validity_rate"] >= config.qc_min_parse_validity_rate, f"parse_validity_rate < {config.qc_min_parse_validity_rate}"),
                (
                    "QC_TIMELINE_CONSISTENCY_LOW",
                    metrics["timeline_consistency_score"] >= config.qc_min_timeline_consistency_score,
                    f"timeline_consistency_score < {config.qc_min_timeline_consistency_score}",
                ),
                ("QC_GROUNDING_LOW", metrics["grounding_score"] >= config.qc_min_grounding_score, f"grounding_score < {config.qc_min_grounding_score}"),
                (
                    "QC_BLACK_FRAME_HIGH",
                    metrics["black_frame_ratio"] <= config.qc_max_black_frame_ratio,
                    f"black_frame_ratio > {config.qc_max_black_frame_ratio}",
                ),
                ("QC_NO_MATCH_HIGH", metrics["no_match_rate"] <= config.qc_max_no_match_rate, f"no_match_rate > {config.qc_max_no_match_rate}"),
                (
                    "QC_MEDIAN_CONFIDENCE_LOW",
                    metrics["median_confidence"] >= config.qc_min_median_confidence,
                    f"median_confidence < {config.qc_min_median_confidence}",
                ),
                (
                    "QC_HIGH_CONFIDENCE_RATIO_LOW",
                    metrics["high_confidence_ratio"] >= config.qc_min_high_confidence_ratio,
                    f"high_confidence_ratio < {config.qc_min_high_confidence_ratio}",
                ),
                ("QC_RENDER_FAILED", metrics["render_success"] is True, "render_success != true"),
                ("QC_AUDIO_MISSING", metrics["audio_present"] is True, "audio_present != true"),
            ]
            for code, ok, message in checks:
                if not ok:
                    threshold_errors.append({"stage": "qc", "error_code": code, "message": message})

        report = build_quality_report(
            run_id=run_id,
            input_profile=config.input_profile,
            stage_results=stage_results,
            metrics=metrics,
            warnings=warnings,
            errors=threshold_errors,
        )
        if threshold_errors:
            report["overall_status"] = "fail"
        report["stage_results"] = report["stage_results"] + [
            {
                "stage": "qc",
                "status": "fail" if threshold_errors else "pass",
                "duration_ms": 0,
            }
        ]
        schema_path = Path("docs/Reasoning-NLP/schema/quality_report.schema.json")
        validate_quality_report_artifact(report, schema_path=schema_path)

        out_path = base / "g8_qc" / "quality_report.json"
        write_json(out_path, report)

        qc_status = "fail" if threshold_errors else "pass"
        _append_stage_result(stage_results, stage, qc_status, started)
        logger.info("run stage=%s status=%s", stage, qc_status)
        return report
    except PipelineError as err:
        _append_stage_result(stage_results, stage, "fail", started, error_code=err.code)
        logger.error("run stage=%s status=fail error_code=%s", stage, err.code)
        raise


def _append_stage_result(
    stage_results: list[dict[str, Any]],
    stage: str,
    status: str,
    started: float,
    error_code: str | None = None,
) -> None:
    duration_ms = int((time.perf_counter() - started) * 1000)
    payload: dict[str, Any] = {
        "stage": stage,
        "status": status,
        "duration_ms": max(0, duration_ms),
    }
    if error_code:
        payload["error_code"] = error_code
    stage_results.append(payload)


def _new_run_id() -> str:
    return f"run_{uuid.uuid4().hex[:12]}"


def _append_stage_skipped(stage_results: list[dict[str, Any]], stage: str) -> None:
    stage_results.append({"stage": stage, "status": "skipped", "duration_ms": 0})


def _replay_or_run_g1(
    config: PipelineConfig,
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
    replay_enabled: bool,
    stage_hashes: dict[str, str],
):
    if replay_enabled and _is_stage_replayable(base, "validate", stage_hashes):
        payload = _load_json_if_exists(base / "g1_validate" / "normalized_input.json")
        if isinstance(payload, dict):
            try:
                validated, source_duration_ms = _validated_input_from_payload(cast(dict[str, Any], payload))
                _append_stage_skipped(stage_results, "validate")
                logger.info("run stage=validate status=skipped")
                return validated, source_duration_ms
            except Exception:
                pass
    return _run_g1_validate(config, base, stage_results, logger)


def _replay_or_run_g2(
    config: PipelineConfig,
    validated,
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
    replay_enabled: bool,
    stage_hashes: dict[str, str],
) -> tuple[dict[str, Any], list[AlignmentBlock]]:
    if replay_enabled and _is_stage_replayable(base, "align", stage_hashes):
        payload = _load_json_if_exists(base / "g2_align" / "alignment_result.json")
        if isinstance(payload, dict):
            try:
                validate_alignment_artifact(payload, Path("docs/Reasoning-NLP/schema/alignment_result.schema.json"))
                blocks = [AlignmentBlock(**b) for b in payload.get("blocks", [])]
                _append_stage_skipped(stage_results, "align")
                logger.info("run stage=align status=skipped")
                return payload, blocks
            except Exception:
                pass
    return _run_g2_align(config, validated, base, stage_results, logger)


def _replay_or_run_g3(
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
    replay_enabled: bool,
    alignment_blocks: list[AlignmentBlock],
    stage_hashes: dict[str, str],
) -> list[dict[str, Any]]:
    if replay_enabled and _is_stage_replayable(base, "context_build", stage_hashes):
        payload = _load_json_if_exists(base / "g3_context" / "context_blocks.json")
        if isinstance(payload, list) and payload:
            _append_stage_skipped(stage_results, "context_build")
            logger.info("run stage=context_build status=skipped")
            return payload
    return _run_g3_context(alignment_blocks, base, stage_results, logger)


def _replay_or_run_g4(
    config: PipelineConfig,
    context_payload: list[dict[str, Any]],
    source_duration_ms: int | None,
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
    replay_enabled: bool,
    stage_hashes: dict[str, str],
) -> dict[str, Any]:
    if replay_enabled and _is_stage_replayable(base, "summarize", stage_hashes):
        payload = _load_json_if_exists(base / "g4_summarize" / "summary_script.internal.json")
        if isinstance(payload, dict):
            try:
                validate_summary_internal_artifact(payload, Path("docs/Reasoning-NLP/schema/summary_script.internal.schema.json"))
                _append_stage_skipped(stage_results, "summarize")
                logger.info("run stage=summarize status=skipped")
                return payload
            except Exception:
                pass
    return _run_g4_summarize(config, context_payload, source_duration_ms, base, stage_results, logger)


def _replay_or_run_g5(
    config: PipelineConfig,
    context_payload: list[dict[str, Any]],
    summary_internal_payload: dict[str, Any],
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
    replay_enabled: bool,
    stage_hashes: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if replay_enabled and _is_stage_replayable(base, "segment_plan", stage_hashes):
        script_payload = _load_json_if_exists(base / "g5_segment" / "summary_script.json")
        manifest_payload = _load_json_if_exists(base / "g5_segment" / "summary_video_manifest.json")
        if isinstance(script_payload, dict) and isinstance(manifest_payload, dict):
            try:
                validate_deliverable_artifacts(
                    script_payload=script_payload,
                    manifest_payload=manifest_payload,
                    script_schema_path=Path("contracts/v1/template/summary_script.schema.json"),
                    manifest_schema_path=Path("contracts/v1/template/summary_video_manifest.schema.json"),
                )
                _append_stage_skipped(stage_results, "segment_plan")
                logger.info("run stage=segment_plan status=skipped")
                return script_payload, manifest_payload
            except Exception:
                pass
    return _run_g5_segment_plan(config, context_payload, summary_internal_payload, base, stage_results, logger)


def _replay_or_run_g6(
    config: PipelineConfig,
    script_payload: dict[str, Any],
    manifest_payload: dict[str, Any],
    source_duration_ms: int | None,
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
    replay_enabled: bool,
    stage_hashes: dict[str, str],
) -> None:
    if replay_enabled and _is_stage_replayable(base, "manifest", stage_hashes):
        payload = _load_json_if_exists(base / "g6_manifest" / "manifest_validation.json")
        if isinstance(payload, dict) and payload.get("status") == "pass":
            _append_stage_skipped(stage_results, "manifest")
            logger.info("run stage=manifest status=skipped")
            return
    _run_g6_manifest(config, script_payload, manifest_payload, source_duration_ms, base, stage_results, logger)


def _replay_or_run_g7(
    config: PipelineConfig,
    manifest_payload: dict[str, Any],
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
    replay_enabled: bool,
    stage_hashes: dict[str, str],
) -> dict[str, Any]:
    if replay_enabled and _is_stage_replayable(base, "assemble", stage_hashes):
        render_meta = _load_json_if_exists(base / "g7_assemble" / "render_meta.json")
        video_path = base / "g7_assemble" / "summary_video.mp4"
        if isinstance(render_meta, dict) and video_path.exists() and video_path.stat().st_size > 0:
            _append_stage_skipped(stage_results, "assemble")
            logger.info("run stage=assemble status=skipped")
            return render_meta
    return _run_g7_assemble(config, manifest_payload, base, stage_results, logger)


def _validated_input_from_payload(payload: dict[str, Any]):
    from reasoning_nlp.validators.input_validator import ValidatedInput

    transcripts = [CanonicalTranscript(**x) for x in payload.get("transcripts", [])]
    captions = [CanonicalCaption(**x) for x in payload.get("captions", [])]
    validated = ValidatedInput(
        input_profile=str(payload.get("input_profile", "strict_contract_v1")),
        transcripts=transcripts,
        captions=captions,
        raw_video_path=str(payload.get("raw_video_path", "")),
    )
    source_duration_ms = payload.get("source_duration_ms")
    if not isinstance(source_duration_ms, int) or source_duration_ms <= 0:
        source_duration_ms = probe_source_duration_ms(validated.raw_video_path)
    return validated, source_duration_ms


def _load_json_if_exists(path: Path) -> dict[str, Any] | list[dict[str, Any]] | None:
    if not path.exists():
        return None
    try:
        return read_json(path)
    except Exception:
        return None


def _build_run_meta(config: PipelineConfig) -> dict[str, Any]:
    input_checksums = {
        "audio_transcripts_sha256": _file_sha256(Path(config.audio_transcripts_path)),
        "visual_captions_sha256": _file_sha256(Path(config.visual_captions_path)),
        "raw_video_sha256": _file_sha256(Path(config.raw_video_path)),
    }
    tracked = {
        "input_profile": config.input_profile,
        "align_k": config.align_k,
        "align_min_delta_ms": config.align_min_delta_ms,
        "align_max_delta_ms": config.align_max_delta_ms,
        "summarize_seed": config.summarize_seed,
        "summarize_temperature": config.summarize_temperature,
        "model_version": config.model_version,
        "tokenizer_version": config.tokenizer_version,
        "source_duration_ms": config.source_duration_ms,
        "summarize_backend": config.summarize_backend,
        "summarize_fallback_backend": config.summarize_fallback_backend,
        "summarize_timeout_ms": config.summarize_timeout_ms,
        "summarize_max_retries": config.summarize_max_retries,
        "summarize_max_new_tokens": config.summarize_max_new_tokens,
        "summarize_do_sample": config.summarize_do_sample,
        "min_segment_duration_ms": config.min_segment_duration_ms,
        "max_segment_duration_ms": config.max_segment_duration_ms,
        "min_total_duration_ms": config.min_total_duration_ms,
        "max_total_duration_ms": config.max_total_duration_ms,
        "target_ratio": config.target_ratio,
        "target_ratio_tolerance": config.target_ratio_tolerance,
        "qc_enforce_thresholds": config.qc_enforce_thresholds,
        "qc_min_parse_validity_rate": config.qc_min_parse_validity_rate,
        "qc_min_timeline_consistency_score": config.qc_min_timeline_consistency_score,
        "qc_min_grounding_score": config.qc_min_grounding_score,
        "qc_max_black_frame_ratio": config.qc_max_black_frame_ratio,
        "qc_max_no_match_rate": config.qc_max_no_match_rate,
        "qc_min_median_confidence": config.qc_min_median_confidence,
        "qc_min_high_confidence_ratio": config.qc_min_high_confidence_ratio,
        **input_checksums,
    }

    stage_inputs = {
        "validate": {
            "input_profile": config.input_profile,
            "audio_transcripts_sha256": input_checksums["audio_transcripts_sha256"],
            "visual_captions_sha256": input_checksums["visual_captions_sha256"],
            "raw_video_sha256": input_checksums["raw_video_sha256"],
            "source_duration_ms": config.source_duration_ms,
        },
        "align": {
            "align_k": config.align_k,
            "align_min_delta_ms": config.align_min_delta_ms,
            "align_max_delta_ms": config.align_max_delta_ms,
        },
        "context_build": {},
        "summarize": {
            "summarize_seed": config.summarize_seed,
            "summarize_temperature": config.summarize_temperature,
            "model_version": config.model_version,
            "tokenizer_version": config.tokenizer_version,
            "summarize_backend": config.summarize_backend,
            "summarize_fallback_backend": config.summarize_fallback_backend,
            "summarize_timeout_ms": config.summarize_timeout_ms,
            "summarize_max_retries": config.summarize_max_retries,
            "summarize_max_new_tokens": config.summarize_max_new_tokens,
            "summarize_do_sample": config.summarize_do_sample,
        },
        "segment_plan": {
            "min_segment_duration_ms": config.min_segment_duration_ms,
            "max_segment_duration_ms": config.max_segment_duration_ms,
            "min_total_duration_ms": config.min_total_duration_ms,
            "max_total_duration_ms": config.max_total_duration_ms,
            "target_ratio": config.target_ratio,
            "target_ratio_tolerance": config.target_ratio_tolerance,
        },
        "manifest": {},
        "assemble": {},
        "qc": {
            "input_profile": config.input_profile,
            "qc_enforce_thresholds": config.qc_enforce_thresholds,
            "qc_min_parse_validity_rate": config.qc_min_parse_validity_rate,
            "qc_min_timeline_consistency_score": config.qc_min_timeline_consistency_score,
            "qc_min_grounding_score": config.qc_min_grounding_score,
            "qc_max_black_frame_ratio": config.qc_max_black_frame_ratio,
            "qc_max_no_match_rate": config.qc_max_no_match_rate,
            "qc_min_median_confidence": config.qc_min_median_confidence,
            "qc_min_high_confidence_ratio": config.qc_min_high_confidence_ratio,
        },
    }

    stage_hashes = _build_stage_hashes(stage_inputs)
    material = json.dumps(tracked, ensure_ascii=True, sort_keys=True)
    return {
        "version": 1,
        "config_hash": hashlib.sha256(material.encode("utf-8")).hexdigest(),
        "tracked": tracked,
        "stage_hashes": stage_hashes,
    }


def _write_run_meta(base: Path, run_meta: dict[str, Any]) -> None:
    write_json(base / "run_meta.json", run_meta)


def _build_stage_hashes(stage_inputs: dict[str, dict[str, Any]]) -> dict[str, str]:
    stage_hashes: dict[str, str] = {}
    for stage in STAGE_ORDER:
        deps = {k: stage_hashes[k] for k in STAGE_ORDER[: STAGE_ORDER.index(stage)]}
        material = {
            "stage": stage,
            "inputs": stage_inputs.get(stage, {}),
            "deps": deps,
        }
        text = json.dumps(material, ensure_ascii=True, sort_keys=True)
        stage_hashes[stage] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return stage_hashes


def _is_stage_replayable(base: Path, stage: str, current_stage_hashes: dict[str, str]) -> bool:
    payload = _load_json_if_exists(base / "run_meta.json")
    if not isinstance(payload, dict):
        return False
    saved = payload.get("stage_hashes")
    if not isinstance(saved, dict):
        return False

    stage_idx = STAGE_ORDER.index(stage)
    for dep in STAGE_ORDER[: stage_idx + 1]:
        if saved.get(dep) != current_stage_hashes.get(dep):
            return False
    return True


def _file_sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    from reasoning_nlp.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
