from __future__ import annotations

import argparse
import json
from argparse import SUPPRESS
from typing import Any

from reasoning_nlp.common.errors import PipelineError
from reasoning_nlp.config.defaults import DEFAULT_PLANNER_SCORING, DEFAULT_QC, DEFAULT_RUNTIME, DEFAULT_SUMMARIZATION
from reasoning_nlp.config.runtime_loader import build_pipeline_config
from reasoning_nlp.pipeline import PipelineConfig, run_pipeline_g1_g3, run_pipeline_g1_g5, run_pipeline_g1_g8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Reasoning-NLP pipeline")
    parser.add_argument("--audio-transcripts", required=True, help="Path to audio_transcripts.json")
    parser.add_argument("--visual-captions", required=True, help="Path to visual_captions.json")
    parser.add_argument("--raw-video", required=True, help="Path to raw_video.mp4")
    parser.add_argument("--stage", choices=["g3", "g5", "g8"], default="g8", help="Pipeline target stage")
    parser.add_argument("--run-id", default=None, help="Run id; required for replay")
    parser.add_argument("--artifacts-root", default=DEFAULT_RUNTIME["artifacts_root"], help="Artifacts root directory")
    parser.add_argument("--deliverables-root", default=DEFAULT_RUNTIME["deliverables_root"], help="Final deliverables root directory")
    parser.add_argument("--input-profile", default=DEFAULT_RUNTIME["input_profile"], choices=["strict_contract_v1", "legacy_member1"])
    parser.add_argument("--source-duration-ms", type=int, default=None)
    parser.add_argument("--model-version", default=DEFAULT_SUMMARIZATION["model_version"])
    parser.add_argument("--summarize-backend", choices=["api", "local"], default=DEFAULT_SUMMARIZATION["backend"])
    parser.add_argument(
        "--summarize-fallback-backend",
        choices=["api", "local"],
        default=DEFAULT_SUMMARIZATION["fallback_backend"],
    )
    parser.add_argument("--summarize-timeout-ms", type=int, default=DEFAULT_SUMMARIZATION["timeout_ms"])
    parser.add_argument("--summarize-max-retries", type=int, default=DEFAULT_SUMMARIZATION["max_retries"])
    parser.add_argument("--summarize-max-new-tokens", type=int, default=DEFAULT_SUMMARIZATION["max_new_tokens"])
    parser.add_argument("--summarize-do-sample", action="store_true", default=DEFAULT_SUMMARIZATION["do_sample"])
    parser.add_argument("--summarize-prompt-max-chars", type=int, default=DEFAULT_SUMMARIZATION["prompt_max_chars"])
    parser.add_argument(
        "--summarize-production-strict",
        action="store_true",
        default=DEFAULT_SUMMARIZATION["production_strict"],
    )
    parser.add_argument(
        "--no-summarize-production-strict",
        action="store_false",
        dest="summarize_production_strict",
    )
    parser.add_argument("--allow-heuristic-for-tests", action="store_true", default=False, help=SUPPRESS)
    parser.add_argument(
        "--planner-lexical-enabled",
        action="store_true",
        default=DEFAULT_PLANNER_SCORING["lexical_enabled"],
    )
    parser.add_argument(
        "--no-planner-lexical-enabled",
        action="store_false",
        dest="planner_lexical_enabled",
    )
    parser.add_argument("--planner-lexical-weight", type=float, default=DEFAULT_PLANNER_SCORING["lexical_weight"])
    parser.add_argument("--planner-lexical-min-df", type=int, default=DEFAULT_PLANNER_SCORING["lexical_min_df"])
    parser.add_argument(
        "--planner-lexical-min-token-len",
        type=int,
        default=DEFAULT_PLANNER_SCORING["lexical_min_token_len"],
    )
    parser.add_argument(
        "--planner-lexical-use-idf",
        action="store_true",
        default=DEFAULT_PLANNER_SCORING["lexical_use_idf"],
    )
    parser.add_argument(
        "--no-planner-lexical-use-idf",
        action="store_false",
        dest="planner_lexical_use_idf",
    )
    parser.add_argument(
        "--planner-lexical-stopwords-profile",
        choices=["vi"],
        default=DEFAULT_PLANNER_SCORING["lexical_stopwords_profile"],
    )
    parser.add_argument("--qc-enforce-thresholds", action="store_true", default=DEFAULT_QC["enforce_thresholds"])
    parser.add_argument(
        "--qc-blackdetect-mode",
        choices=["auto", "full", "sampled", "off"],
        default=DEFAULT_QC["blackdetect_mode"],
    )
    parser.add_argument("--qc-min-parse-validity-rate", type=float, default=DEFAULT_QC["min_parse_validity_rate"])
    parser.add_argument(
        "--qc-min-timeline-consistency-score",
        type=float,
        default=DEFAULT_QC["min_timeline_consistency_score"],
    )
    parser.add_argument("--qc-min-grounding-score", type=float, default=DEFAULT_QC["min_grounding_score"])
    parser.add_argument("--qc-max-black-frame-ratio", type=float, default=DEFAULT_QC["max_black_frame_ratio"])
    parser.add_argument("--qc-max-no-match-rate", type=float, default=DEFAULT_QC["max_no_match_rate"])
    parser.add_argument("--qc-min-median-confidence", type=float, default=DEFAULT_QC["min_median_confidence"])
    parser.add_argument(
        "--qc-min-high-confidence-ratio",
        type=float,
        default=DEFAULT_QC["min_high_confidence_ratio"],
    )
    parser.add_argument("--replay", action="store_true", help="Replay valid existing stage artifacts")
    parser.add_argument("--debug-artifacts", action="store_true", default=None, help="Emit internal debug artifacts")
    parser.add_argument("--emit-internal-artifacts", action="store_true", default=None, help=SUPPRESS)
    parser.add_argument("--no-emit-internal-artifacts", action="store_false", dest="emit_internal_artifacts", default=None)
    parser.add_argument("--strict-replay-hash", action="store_true", default=DEFAULT_RUNTIME["strict_replay_hash"])
    parser.add_argument("--runtime-profile", choices=["full", "simple"], default="full")
    return parser.parse_args()


def build_config_from_args(args: argparse.Namespace) -> PipelineConfig:
    def pick(name: str, default: Any = None) -> Any:
        return getattr(args, name, default)

    debug_artifacts = pick("debug_artifacts")
    if debug_artifacts is None:
        debug_artifacts = pick("emit_internal_artifacts")
    payload: dict[str, Any] = {
        "audio_transcripts_path": pick("audio_transcripts"),
        "visual_captions_path": pick("visual_captions"),
        "raw_video_path": pick("raw_video"),
        "run_id": pick("run_id"),
        "artifacts_root": pick("artifacts_root"),
        "deliverables_root": pick("deliverables_root"),
        "input_profile": pick("input_profile"),
        "source_duration_ms": pick("source_duration_ms"),
        "model_version": pick("model_version"),
        "summarize_backend": pick("summarize_backend"),
        "summarize_fallback_backend": pick("summarize_fallback_backend"),
        "summarize_timeout_ms": pick("summarize_timeout_ms"),
        "summarize_max_retries": pick("summarize_max_retries"),
        "summarize_max_new_tokens": pick("summarize_max_new_tokens"),
        "summarize_do_sample": pick("summarize_do_sample"),
        "summarize_prompt_max_chars": pick("summarize_prompt_max_chars"),
        "summarize_production_strict": pick("summarize_production_strict"),
        "allow_heuristic_for_tests": pick("allow_heuristic_for_tests"),
        "planner_lexical_enabled": pick("planner_lexical_enabled"),
        "planner_lexical_weight": pick("planner_lexical_weight"),
        "planner_lexical_min_df": pick("planner_lexical_min_df"),
        "planner_lexical_min_token_len": pick("planner_lexical_min_token_len"),
        "planner_lexical_use_idf": pick("planner_lexical_use_idf"),
        "planner_lexical_stopwords_profile": pick("planner_lexical_stopwords_profile"),
        "qc_enforce_thresholds": pick("qc_enforce_thresholds"),
        "qc_blackdetect_mode": pick("qc_blackdetect_mode"),
        "qc_min_parse_validity_rate": pick("qc_min_parse_validity_rate"),
        "qc_min_timeline_consistency_score": pick("qc_min_timeline_consistency_score"),
        "qc_min_grounding_score": pick("qc_min_grounding_score"),
        "qc_max_black_frame_ratio": pick("qc_max_black_frame_ratio"),
        "qc_max_no_match_rate": pick("qc_max_no_match_rate"),
        "qc_min_median_confidence": pick("qc_min_median_confidence"),
        "qc_min_high_confidence_ratio": pick("qc_min_high_confidence_ratio"),
        "debug_artifacts": debug_artifacts,
        "strict_replay_hash": pick("strict_replay_hash"),
        "replay_mode": pick("replay"),
        "runtime_profile": pick("runtime_profile", "full"),
    }
    return build_pipeline_config(payload)


def main() -> int:
    args = parse_args()
    config = build_config_from_args(args)
    if config.replay_mode and not config.run_id:
        print("Replay mode requires --run-id")
        return 2

    try:
        if args.stage == "g3":
            result = run_pipeline_g1_g3(config)
        elif args.stage == "g5":
            result = run_pipeline_g1_g5(config)
        else:
            result = run_pipeline_g1_g8(config)
        print(json.dumps({"run_id": result["run_id"], "stage_results": result["stage_results"]}, ensure_ascii=False, indent=2))
        return 0
    except PipelineError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
