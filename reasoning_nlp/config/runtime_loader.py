from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from reasoning_nlp.config.defaults import (
    DEFAULT_PLANNER_SCORING,
    DEFAULT_QC,
    DEFAULT_RUNTIME,
    DEFAULT_SEGMENT_BUDGET,
    DEFAULT_SUMMARIZATION,
)
from reasoning_nlp.pipeline import PipelineConfig


def coerce_bool(value: Any, default: bool = False) -> bool:
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


def load_json_config(path: str | None) -> dict[str, Any]:
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


def resolve_value(cli_value: Any, env_name: str, config: Mapping[str, Any], config_key: str, default: Any) -> Any:
    if cli_value is not None:
        return cli_value
    env_value = os.getenv(env_name)
    if env_value is not None:
        return env_value
    if config_key in config:
        return config[config_key]
    return default


def build_pipeline_config(values: Mapping[str, Any]) -> PipelineConfig:
    replay_mode = coerce_bool(values.get("replay_mode", values.get("replay", False)), default=False)

    debug_candidate = values.get("debug_artifacts")
    if debug_candidate is None:
        debug_candidate = values.get("emit_internal_artifacts", DEFAULT_RUNTIME["emit_internal_artifacts"])
    emit_internal_artifacts = coerce_bool(debug_candidate, default=bool(DEFAULT_RUNTIME["emit_internal_artifacts"]))
    if replay_mode and not emit_internal_artifacts:
        emit_internal_artifacts = True

    return PipelineConfig(
        audio_transcripts_path=str(values["audio_transcripts_path"]),
        visual_captions_path=str(values["visual_captions_path"]),
        scene_metadata_path=str(values["scene_metadata_path"]),
        raw_video_path=str(values["raw_video_path"]),
        run_id=values.get("run_id"),
        artifacts_root=str(values.get("artifacts_root", DEFAULT_RUNTIME["artifacts_root"])),
        deliverables_root=str(values.get("deliverables_root", DEFAULT_RUNTIME["deliverables_root"])),
        input_profile=str(values.get("input_profile", DEFAULT_RUNTIME["input_profile"])),
        source_duration_ms=values.get("source_duration_ms"),
        min_segment_duration_ms=int(values.get("min_segment_duration_ms", DEFAULT_SEGMENT_BUDGET["min_segment_duration_ms"])),
        max_segment_duration_ms=int(values.get("max_segment_duration_ms", DEFAULT_SEGMENT_BUDGET["max_segment_duration_ms"])),
        min_total_duration_ms=(
            int(values["min_total_duration_ms"])
            if values.get("min_total_duration_ms", DEFAULT_SEGMENT_BUDGET["min_total_duration_ms"]) is not None
            else None
        ),
        max_total_duration_ms=(
            int(values["max_total_duration_ms"])
            if values.get("max_total_duration_ms", DEFAULT_SEGMENT_BUDGET["max_total_duration_ms"]) is not None
            else None
        ),
        target_ratio=(
            float(values["target_ratio"])
            if values.get("target_ratio", DEFAULT_SEGMENT_BUDGET["target_ratio"]) is not None
            else None
        ),
        target_ratio_tolerance=float(values.get("target_ratio_tolerance", DEFAULT_SEGMENT_BUDGET["target_ratio_tolerance"])),
        min_candidate_segment_ms=int(
            values.get("min_candidate_segment_ms", DEFAULT_SEGMENT_BUDGET["min_candidate_segment_ms"])
        ),
        max_selected_segments=int(values.get("max_selected_segments", DEFAULT_SEGMENT_BUDGET["max_selected_segments"])),
        model_version=str(values.get("model_version", DEFAULT_SUMMARIZATION["model_version"])),
        summarize_backend=str(values.get("summarize_backend", DEFAULT_SUMMARIZATION["backend"])),
        summarize_fallback_backend=str(values.get("summarize_fallback_backend", DEFAULT_SUMMARIZATION["fallback_backend"])),
        summarize_timeout_ms=int(values.get("summarize_timeout_ms", DEFAULT_SUMMARIZATION["timeout_ms"])),
        summarize_max_retries=int(values.get("summarize_max_retries", DEFAULT_SUMMARIZATION["max_retries"])),
        summarize_max_new_tokens=int(values.get("summarize_max_new_tokens", DEFAULT_SUMMARIZATION["max_new_tokens"])),
        summarize_do_sample=coerce_bool(values.get("summarize_do_sample", DEFAULT_SUMMARIZATION["do_sample"]), default=False),
        summarize_prompt_max_chars=(
            int(values["summarize_prompt_max_chars"])
            if values.get("summarize_prompt_max_chars") is not None
            else None
        ),
        summarize_production_strict=coerce_bool(
            values.get("summarize_production_strict", DEFAULT_SUMMARIZATION["production_strict"]),
            default=bool(DEFAULT_SUMMARIZATION["production_strict"]),
        ),
        allow_heuristic_for_tests=coerce_bool(values.get("allow_heuristic_for_tests", False), default=False),
        planner_lexical_enabled=coerce_bool(
            values.get("planner_lexical_enabled", DEFAULT_PLANNER_SCORING["lexical_enabled"]),
            default=bool(DEFAULT_PLANNER_SCORING["lexical_enabled"]),
        ),
        planner_lexical_weight=float(values.get("planner_lexical_weight", DEFAULT_PLANNER_SCORING["lexical_weight"])),
        planner_lexical_min_df=int(values.get("planner_lexical_min_df", DEFAULT_PLANNER_SCORING["lexical_min_df"])),
        planner_lexical_min_token_len=int(
            values.get("planner_lexical_min_token_len", DEFAULT_PLANNER_SCORING["lexical_min_token_len"])
        ),
        planner_lexical_use_idf=coerce_bool(
            values.get("planner_lexical_use_idf", DEFAULT_PLANNER_SCORING["lexical_use_idf"]),
            default=bool(DEFAULT_PLANNER_SCORING["lexical_use_idf"]),
        ),
        planner_lexical_stopwords_profile=str(
            values.get("planner_lexical_stopwords_profile", DEFAULT_PLANNER_SCORING["lexical_stopwords_profile"])
        ),
        qc_enforce_thresholds=coerce_bool(values.get("qc_enforce_thresholds", DEFAULT_QC["enforce_thresholds"]), default=False),
        qc_blackdetect_mode=str(values.get("qc_blackdetect_mode", DEFAULT_QC["blackdetect_mode"])),
        qc_min_parse_validity_rate=float(values.get("qc_min_parse_validity_rate", DEFAULT_QC["min_parse_validity_rate"])),
        qc_min_timeline_consistency_score=float(
            values.get("qc_min_timeline_consistency_score", DEFAULT_QC["min_timeline_consistency_score"])
        ),
        qc_min_grounding_score=float(values.get("qc_min_grounding_score", DEFAULT_QC["min_grounding_score"])),
        qc_max_black_frame_ratio=float(values.get("qc_max_black_frame_ratio", DEFAULT_QC["max_black_frame_ratio"])),
        qc_max_no_match_rate=float(values.get("qc_max_no_match_rate", DEFAULT_QC["max_no_match_rate"])),
        qc_min_median_confidence=float(values.get("qc_min_median_confidence", DEFAULT_QC["min_median_confidence"])),
        qc_min_high_confidence_ratio=float(
            values.get("qc_min_high_confidence_ratio", DEFAULT_QC["min_high_confidence_ratio"])
        ),
        emit_internal_artifacts=emit_internal_artifacts,
        strict_replay_hash=coerce_bool(values.get("strict_replay_hash", DEFAULT_RUNTIME["strict_replay_hash"]), default=False),
        replay_mode=replay_mode,
        runtime_profile=str(values.get("runtime_profile", "full")),
    )
