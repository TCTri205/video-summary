from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import subprocess
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
    compute_black_frame_ratio_with_status,
    compute_compression_ratio,
    compute_grounding_score,
    compute_parse_validity_rate,
    compute_timeline_consistency,
)
from reasoning_nlp.qc.report_builder import build_quality_report
from reasoning_nlp.segment_planner.budget_policy import BudgetConfig
from reasoning_nlp.segment_planner.planner import plan_segments_from_context
from reasoning_nlp.summarizer.grounding_checks import check_grounding
from reasoning_nlp.summarizer.leakage_guard import contains_hard_prompt_leakage, contains_soft_prompt_leakage
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
    deliverables_root: str = DEFAULT_RUNTIME["deliverables_root"]
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
    summarize_prompt_max_chars: int | None = int(DEFAULT_SUMMARIZATION["prompt_max_chars"])
    summarize_production_strict: bool = bool(DEFAULT_SUMMARIZATION["production_strict"])
    allow_heuristic_for_tests: bool = False
    source_duration_ms: int | None = None
    min_segment_duration_ms: int = int(DEFAULT_SEGMENT_BUDGET["min_segment_duration_ms"])
    max_segment_duration_ms: int = int(DEFAULT_SEGMENT_BUDGET["max_segment_duration_ms"])
    min_total_duration_ms: int | None = int(DEFAULT_SEGMENT_BUDGET["min_total_duration_ms"])
    max_total_duration_ms: int | None = int(DEFAULT_SEGMENT_BUDGET["max_total_duration_ms"])
    target_ratio: float | None = DEFAULT_SEGMENT_BUDGET["target_ratio"]
    target_ratio_tolerance: float = float(DEFAULT_SEGMENT_BUDGET["target_ratio_tolerance"])
    qc_enforce_thresholds: bool = bool(DEFAULT_QC["enforce_thresholds"])
    qc_blackdetect_mode: str = str(DEFAULT_QC["blackdetect_mode"])
    qc_min_parse_validity_rate: float = float(DEFAULT_QC["min_parse_validity_rate"])
    qc_min_timeline_consistency_score: float = float(DEFAULT_QC["min_timeline_consistency_score"])
    qc_min_grounding_score: float = float(DEFAULT_QC["min_grounding_score"])
    qc_max_black_frame_ratio: float = float(DEFAULT_QC["max_black_frame_ratio"])
    qc_max_no_match_rate: float = float(DEFAULT_QC["max_no_match_rate"])
    qc_min_median_confidence: float = float(DEFAULT_QC["min_median_confidence"])
    qc_min_high_confidence_ratio: float = float(DEFAULT_QC["min_high_confidence_ratio"])
    emit_internal_artifacts: bool = bool(DEFAULT_RUNTIME["emit_internal_artifacts"])
    strict_replay_hash: bool = bool(DEFAULT_RUNTIME["strict_replay_hash"])
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
        if bool(config.summarize_production_strict) and _quality_report_has_error(quality_report, "QC_LLM_NEUTRAL_FALLBACK"):
            raise fail("qc", "QC_LLM_NEUTRAL_FALLBACK", "LLM_NEUTRAL_FALLBACK detected")
        deliverables = _publish_final_deliverables(
            config=config,
            run_id=run_id,
            base=base,
            summary_internal_payload=summary_internal_payload,
            script_payload=script_payload,
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
            "final_summary_video": str(deliverables["summary_video"]),
            "final_summary_text": str(deliverables["summary_text"]),
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
            prompt_max_chars=config.summarize_prompt_max_chars,
            production_strict=config.summarize_production_strict,
            allow_heuristic_for_tests=config.allow_heuristic_for_tests,
        )
        raw_parse_validity_rate = compute_parse_validity_rate(raw)
        repaired = repair_internal_summary(raw)
        repaired_parse_validity_rate = compute_parse_validity_rate(repaired)
        write_json(
            base / "g4_summarize" / "parse_meta.json",
            {
                "raw_parse_validity_rate": max(0.0, min(1.0, float(raw_parse_validity_rate))),
                "repaired_parse_validity_rate": max(0.0, min(1.0, float(repaired_parse_validity_rate))),
            },
        )
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
    except Exception as exc:
        _append_stage_result(stage_results, stage, "fail", started, error_code="LLM_BACKEND_ALL_FAILED")
        logger.error("run stage=%s status=fail error_code=LLM_BACKEND_ALL_FAILED", stage)
        raise fail(stage, "LLM_BACKEND_ALL_FAILED", str(exc)) from exc


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
        parse_meta = _load_json_if_exists(base / "g4_summarize" / "parse_meta.json")
        parse_validity_rate = compute_parse_validity_rate(summary_internal_payload)
        repaired_parse_validity_rate = parse_validity_rate
        if isinstance(parse_meta, dict):
            raw_metric = parse_meta.get("raw_parse_validity_rate")
            if isinstance(raw_metric, (int, float)):
                parse_validity_rate = max(0.0, min(1.0, float(raw_metric)))
            repaired_metric = parse_meta.get("repaired_parse_validity_rate")
            if isinstance(repaired_metric, (int, float)):
                repaired_parse_validity_rate = max(0.0, min(1.0, float(repaired_metric)))
        output_video_path = str(base / "g7_assemble" / "summary_video.mp4")
        blackdetect_mode = str(config.qc_blackdetect_mode).strip().lower()
        if blackdetect_mode == "auto":
            blackdetect_mode = "full" if bool(config.qc_enforce_thresholds) else "sampled"
        blackdetect_result = compute_black_frame_ratio_with_status(
            output_video_path,
            duration_ms=int(assemble_payload.get("duration_ms", 0)),
            mode=blackdetect_mode,
        )
        black_frame_ratio = float(blackdetect_result["ratio"])
        metrics = {
            "parse_validity_rate": parse_validity_rate,
            "repaired_parse_validity_rate": repaired_parse_validity_rate,
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
        if str(blackdetect_result.get("status", "")) == "error":
            warnings.append("QC_BLACKDETECT_FALLBACK")

        threshold_errors: list[dict[str, str]] = []

        leakage_errors = _collect_prompt_leakage_errors(summary_internal_payload)
        threshold_errors.extend(leakage_errors)
        if leakage_errors or _has_soft_prompt_leakage(summary_internal_payload):
            warnings.append("QC_PROMPT_LEAKAGE_SUSPECTED")

        quality_flags = summary_internal_payload.get("quality_flags", [])
        if isinstance(quality_flags, list) and any(str(x) == "LLM_NEUTRAL_FALLBACK" for x in quality_flags):
            threshold_errors.append(
                {
                    "stage": "qc",
                    "error_code": "QC_LLM_NEUTRAL_FALLBACK",
                    "message": "LLM_NEUTRAL_FALLBACK detected",
                }
            )

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
                (
                    "QC_BLACKDETECT_FAILED",
                    str(blackdetect_result.get("status", "")) != "error",
                    str(blackdetect_result.get("error_code", "QC_BLACKDETECT_FAILED")),
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


_CTA_PATTERNS = [
    re.compile(r"\blike\b", re.IGNORECASE),
    re.compile(r"\bcomment\b", re.IGNORECASE),
    re.compile(r"\bsubscribe\b", re.IGNORECASE),
    re.compile(r"\bdang\s*ky\b", re.IGNORECASE),
    re.compile(r"\bdang\s*ki\b", re.IGNORECASE),
]


def _publish_final_deliverables(
    config: PipelineConfig,
    run_id: str,
    base: Path,
    summary_internal_payload: dict[str, Any],
    script_payload: dict[str, Any],
) -> dict[str, Path]:
    deliverable_dir = Path(config.deliverables_root) / run_id
    if deliverable_dir.exists():
        shutil.rmtree(deliverable_dir)
    deliverable_dir.mkdir(parents=True, exist_ok=True)

    src_video = base / "g7_assemble" / "summary_video.mp4"
    dst_video = deliverable_dir / "summary_video.mp4"
    if not src_video.exists() or src_video.stat().st_size <= 0:
        raise fail("qc", "QC_FINAL_VIDEO_MISSING", f"Missing rendered video: {src_video}")
    shutil.copy2(src_video, dst_video)

    text_output = _build_summary_text(summary_internal_payload, script_payload)
    dst_text = deliverable_dir / "summary_text.txt"
    dst_text.write_text(text_output, encoding="utf-8")

    if not dst_video.exists() or dst_video.stat().st_size <= 0:
        raise fail("qc", "QC_FINAL_VIDEO_INVALID", f"Invalid final video: {dst_video}")
    if not _probe_has_audio_stream(dst_video):
        raise fail("qc", "QC_FINAL_AUDIO_MISSING", "Final summary video does not contain audio stream")
    if not dst_text.exists():
        raise fail("qc", "QC_FINAL_TEXT_MISSING", f"Missing final summary text: {dst_text}")

    text_value = dst_text.read_text(encoding="utf-8").strip()
    if len(text_value) < 30:
        raise fail("qc", "QC_FINAL_TEXT_TOO_SHORT", "Final summary text is too short")
    if contains_hard_prompt_leakage(text_value):
        raise fail("qc", "QC_FINAL_TEXT_PROMPT_LEAKAGE", "Final summary text contains prompt leakage markers")
    if _looks_like_cta(text_value):
        raise fail("qc", "QC_FINAL_TEXT_CTA", "Final summary text contains CTA boilerplate")

    files = [x for x in deliverable_dir.iterdir() if x.is_file()]
    expected_names = {"summary_video.mp4", "summary_text.txt"}
    actual_names = {x.name for x in files}
    if actual_names != expected_names:
        raise fail("qc", "QC_FINAL_DELIVERABLE_SET", f"Expected deliverables {sorted(expected_names)}, got {sorted(actual_names)}")

    return {
        "summary_video": dst_video,
        "summary_text": dst_text,
    }


def _build_summary_text(summary_internal_payload: dict[str, Any], script_payload: dict[str, Any]) -> str:
    plot_summary = str(summary_internal_payload.get("plot_summary", script_payload.get("plot_summary", ""))).strip()
    moral_lesson = str(summary_internal_payload.get("moral_lesson", script_payload.get("moral_lesson", ""))).strip()

    sentences: list[str] = []
    if plot_summary:
        sentences.append(_as_sentence(plot_summary))
    if moral_lesson and moral_lesson.lower() != plot_summary.lower():
        sentences.append(_as_sentence(moral_lesson))

    if not sentences:
        sentences.append("Khong du du lieu de tao tom tat ngan cho video.")

    output = " ".join(sentences).strip()
    if contains_hard_prompt_leakage(output):
        raise fail("qc", "QC_FINAL_TEXT_PROMPT_LEAKAGE", "Summary text build detected prompt leakage markers")
    return output + "\n"


def _as_sentence(text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return ""
    if compact[-1] in {".", "!", "?"}:
        return compact
    return f"{compact}."


def _looks_like_cta(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return False
    return any(pattern.search(lowered) for pattern in _CTA_PATTERNS)


def _probe_has_audio_stream(video_path: Path) -> bool:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=codec_type",
        "-of",
        "csv=p=0",
        str(video_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return False
    out = (proc.stdout or "").strip().lower()
    return "audio" in out


def _quality_report_has_error(report: dict[str, Any], error_code: str) -> bool:
    errors = report.get("errors", [])
    if not isinstance(errors, list):
        return False
    for item in errors:
        if isinstance(item, dict) and str(item.get("error_code", "")) == error_code:
            return True
    return False


def _collect_prompt_leakage_errors(summary_internal_payload: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    text_fields = [
        ("title", str(summary_internal_payload.get("title", ""))),
        ("plot_summary", str(summary_internal_payload.get("plot_summary", ""))),
        ("moral_lesson", str(summary_internal_payload.get("moral_lesson", ""))),
    ]
    for field_name, value in text_fields:
        if contains_hard_prompt_leakage(value):
            errors.append(
                {
                    "stage": "qc",
                    "error_code": "QC_PROMPT_LEAKAGE_DETECTED",
                    "message": f"{field_name} contains hard prompt leakage markers",
                }
            )

    evidence = summary_internal_payload.get("evidence", [])
    if isinstance(evidence, list):
        for idx, item in enumerate(evidence):
            if not isinstance(item, dict):
                continue
            claim = str(item.get("claim", ""))
            if contains_hard_prompt_leakage(claim):
                errors.append(
                    {
                        "stage": "qc",
                        "error_code": "QC_PROMPT_LEAKAGE_DETECTED",
                        "message": f"evidence[{idx}].claim contains hard prompt leakage markers",
                    }
                )

    segments = summary_internal_payload.get("segments", [])
    if isinstance(segments, list):
        for idx, seg in enumerate(segments):
            if not isinstance(seg, dict):
                continue
            script_text = str(seg.get("script_text", ""))
            if contains_hard_prompt_leakage(script_text):
                errors.append(
                    {
                        "stage": "qc",
                        "error_code": "QC_PROMPT_LEAKAGE_DETECTED",
                        "message": f"segments[{idx}].script_text contains hard prompt leakage markers",
                    }
                )
    dedup: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in errors:
        key = (str(item.get("error_code", "")), str(item.get("message", "")))
        if key in seen:
            continue
        seen.add(key)
        dedup.append(item)
    return dedup


def _has_soft_prompt_leakage(summary_internal_payload: dict[str, Any]) -> bool:
    text_fields = [
        str(summary_internal_payload.get("title", "")),
        str(summary_internal_payload.get("plot_summary", "")),
        str(summary_internal_payload.get("moral_lesson", "")),
    ]
    if any(contains_soft_prompt_leakage(x) for x in text_fields):
        return True

    evidence = summary_internal_payload.get("evidence", [])
    if isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, dict) and contains_soft_prompt_leakage(str(item.get("claim", ""))):
                return True

    segments = summary_internal_payload.get("segments", [])
    if isinstance(segments, list):
        for seg in segments:
            if isinstance(seg, dict) and contains_soft_prompt_leakage(str(seg.get("script_text", ""))):
                return True
    return False


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
                if _collect_prompt_leakage_errors(payload):
                    raise ValueError("replayed summarize artifact contains prompt leakage markers")
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
    audio_fp = _file_fingerprint(Path(config.audio_transcripts_path), strict_hash=True)
    caption_fp = _file_fingerprint(Path(config.visual_captions_path), strict_hash=True)
    video_fp = _file_fingerprint(Path(config.raw_video_path), strict_hash=bool(config.strict_replay_hash))
    runtime = _collect_runtime_fingerprints()
    schema_checksums = _collect_schema_checksums()

    input_checksums = {
        "audio_transcripts_sha256": audio_fp["sha256"],
        "visual_captions_sha256": caption_fp["sha256"],
        "raw_video_sha256": video_fp["sha256"],
    }
    tracked = {
        "input_profile": config.input_profile,
        "strict_replay_hash": config.strict_replay_hash,
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
        "summarize_prompt_max_chars": config.summarize_prompt_max_chars,
        "summarize_production_strict": config.summarize_production_strict,
        "allow_heuristic_for_tests": config.allow_heuristic_for_tests,
        "min_segment_duration_ms": config.min_segment_duration_ms,
        "max_segment_duration_ms": config.max_segment_duration_ms,
        "min_total_duration_ms": config.min_total_duration_ms,
        "max_total_duration_ms": config.max_total_duration_ms,
        "target_ratio": config.target_ratio,
        "target_ratio_tolerance": config.target_ratio_tolerance,
        "qc_enforce_thresholds": config.qc_enforce_thresholds,
        "qc_blackdetect_mode": config.qc_blackdetect_mode,
        "qc_min_parse_validity_rate": config.qc_min_parse_validity_rate,
        "qc_min_timeline_consistency_score": config.qc_min_timeline_consistency_score,
        "qc_min_grounding_score": config.qc_min_grounding_score,
        "qc_max_black_frame_ratio": config.qc_max_black_frame_ratio,
        "qc_max_no_match_rate": config.qc_max_no_match_rate,
        "qc_min_median_confidence": config.qc_min_median_confidence,
        "qc_min_high_confidence_ratio": config.qc_min_high_confidence_ratio,
        "pipeline_version": runtime["pipeline_version"],
        "ffmpeg_version": runtime["ffmpeg_version"],
        "ffprobe_version": runtime["ffprobe_version"],
        "schema_checksums": schema_checksums,
        "audio_transcripts_quick": audio_fp["quick"],
        "visual_captions_quick": caption_fp["quick"],
        "raw_video_quick": video_fp["quick"],
        **input_checksums,
    }

    stage_inputs = {
        "validate": {
            "input_profile": config.input_profile,
            "strict_replay_hash": config.strict_replay_hash,
            "pipeline_version": runtime["pipeline_version"],
            "audio_transcripts_sha256": input_checksums["audio_transcripts_sha256"],
            "visual_captions_sha256": input_checksums["visual_captions_sha256"],
            "raw_video_sha256": input_checksums["raw_video_sha256"],
            "audio_transcripts_quick": audio_fp["quick"],
            "visual_captions_quick": caption_fp["quick"],
            "raw_video_quick": video_fp["quick"],
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
            "summarize_prompt_max_chars": config.summarize_prompt_max_chars,
            "summarize_production_strict": config.summarize_production_strict,
            "allow_heuristic_for_tests": config.allow_heuristic_for_tests,
            "schema_summary_internal_sha256": schema_checksums.get("summary_script.internal.schema.json", "missing"),
        },
        "segment_plan": {
            "min_segment_duration_ms": config.min_segment_duration_ms,
            "max_segment_duration_ms": config.max_segment_duration_ms,
            "min_total_duration_ms": config.min_total_duration_ms,
            "max_total_duration_ms": config.max_total_duration_ms,
            "target_ratio": config.target_ratio,
            "target_ratio_tolerance": config.target_ratio_tolerance,
        },
        "manifest": {
            "schema_summary_script_sha256": schema_checksums.get("summary_script.schema.json", "missing"),
            "schema_summary_manifest_sha256": schema_checksums.get("summary_video_manifest.schema.json", "missing"),
        },
        "assemble": {
            "ffmpeg_version": runtime["ffmpeg_version"],
            "ffprobe_version": runtime["ffprobe_version"],
        },
        "qc": {
            "input_profile": config.input_profile,
            "ffmpeg_version": runtime["ffmpeg_version"],
            "schema_quality_report_sha256": schema_checksums.get("quality_report.schema.json", "missing"),
            "qc_enforce_thresholds": config.qc_enforce_thresholds,
            "qc_blackdetect_mode": config.qc_blackdetect_mode,
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


def _file_fingerprint(path: Path, strict_hash: bool) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {
            "exists": False,
            "size": -1,
            "mtime_ns": -1,
            "quick": "missing",
            "sha256": "missing",
        }

    stat = path.stat()
    size = int(stat.st_size)
    mtime_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)))
    quick_material = f"{path.resolve()}|{size}|{mtime_ns}"
    quick = hashlib.sha256(quick_material.encode("utf-8")).hexdigest()
    sha256 = _file_sha256(path) if strict_hash else f"quick:{quick}"
    return {
        "exists": True,
        "size": size,
        "mtime_ns": mtime_ns,
        "quick": quick,
        "sha256": sha256,
    }


def _collect_runtime_fingerprints() -> dict[str, str]:
    return {
        "pipeline_version": _detect_pipeline_version(),
        "ffmpeg_version": _detect_binary_version("ffmpeg"),
        "ffprobe_version": _detect_binary_version("ffprobe"),
    }


def _detect_pipeline_version() -> str:
    env_version = os.getenv("PIPELINE_VERSION", "").strip()
    if env_version:
        return env_version

    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if proc.returncode == 0:
            value = (proc.stdout or "").strip()
            if value:
                return value
    except Exception:
        pass
    return "unknown"


def _detect_binary_version(binary: str) -> str:
    try:
        proc = subprocess.run([binary, "-version"], capture_output=True, text=True, timeout=2)
        if proc.returncode != 0:
            return "unavailable"
        first_line = (proc.stdout or "").splitlines()
        if first_line:
            return first_line[0].strip()
    except Exception:
        return "unavailable"
    return "unavailable"


def _collect_schema_checksums() -> dict[str, str]:
    schema_paths = [
        Path("docs/Reasoning-NLP/schema/alignment_result.schema.json"),
        Path("docs/Reasoning-NLP/schema/summary_script.internal.schema.json"),
        Path("docs/Reasoning-NLP/schema/quality_report.schema.json"),
        Path("contracts/v1/template/summary_script.schema.json"),
        Path("contracts/v1/template/summary_video_manifest.schema.json"),
    ]
    checksums: dict[str, str] = {}
    for path in schema_paths:
        checksums[path.name] = _file_sha256(path)
    return checksums


def main() -> int:
    from reasoning_nlp.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
