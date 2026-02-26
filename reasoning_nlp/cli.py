from __future__ import annotations

import argparse
import json

from reasoning_nlp.common.errors import PipelineError
from reasoning_nlp.config.defaults import DEFAULT_QC, DEFAULT_RUNTIME, DEFAULT_SUMMARIZATION
from reasoning_nlp.pipeline_runner import PipelineConfig, run_pipeline_g1_g3, run_pipeline_g1_g5, run_pipeline_g1_g8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Reasoning-NLP pipeline")
    parser.add_argument("--audio-transcripts", required=True, help="Path to audio_transcripts.json")
    parser.add_argument("--visual-captions", required=True, help="Path to visual_captions.json")
    parser.add_argument("--raw-video", required=True, help="Path to raw_video.mp4")
    parser.add_argument("--stage", choices=["g3", "g5", "g8"], default="g8", help="Pipeline target stage")
    parser.add_argument("--run-id", default=None, help="Run id; required for replay")
    parser.add_argument("--artifacts-root", default=DEFAULT_RUNTIME["artifacts_root"], help="Artifacts root directory")
    parser.add_argument("--input-profile", default=DEFAULT_RUNTIME["input_profile"], choices=["strict_contract_v1", "legacy_member1"])
    parser.add_argument("--source-duration-ms", type=int, default=None)
    parser.add_argument("--summarize-backend", choices=["api", "local"], default=DEFAULT_SUMMARIZATION["backend"])
    parser.add_argument("--summarize-fallback-backend", choices=["api", "local"], default=DEFAULT_SUMMARIZATION["fallback_backend"])
    parser.add_argument("--summarize-timeout-ms", type=int, default=DEFAULT_SUMMARIZATION["timeout_ms"])
    parser.add_argument("--summarize-max-retries", type=int, default=DEFAULT_SUMMARIZATION["max_retries"])
    parser.add_argument("--summarize-max-new-tokens", type=int, default=DEFAULT_SUMMARIZATION["max_new_tokens"])
    parser.add_argument("--summarize-do-sample", action="store_true", default=DEFAULT_SUMMARIZATION["do_sample"])
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
    parser.add_argument("--emit-internal-artifacts", action="store_true", default=True)
    parser.add_argument("--no-emit-internal-artifacts", action="store_false", dest="emit_internal_artifacts")
    return parser.parse_args()


def build_config_from_args(args: argparse.Namespace) -> PipelineConfig:
    return PipelineConfig(
        audio_transcripts_path=args.audio_transcripts,
        visual_captions_path=args.visual_captions,
        raw_video_path=args.raw_video,
        run_id=args.run_id,
        artifacts_root=args.artifacts_root,
        input_profile=args.input_profile,
        source_duration_ms=args.source_duration_ms,
        summarize_backend=args.summarize_backend,
        summarize_fallback_backend=args.summarize_fallback_backend,
        summarize_timeout_ms=args.summarize_timeout_ms,
        summarize_max_retries=args.summarize_max_retries,
        summarize_max_new_tokens=args.summarize_max_new_tokens,
        summarize_do_sample=args.summarize_do_sample,
        qc_enforce_thresholds=args.qc_enforce_thresholds,
        qc_blackdetect_mode=args.qc_blackdetect_mode,
        qc_min_parse_validity_rate=args.qc_min_parse_validity_rate,
        qc_min_timeline_consistency_score=args.qc_min_timeline_consistency_score,
        qc_min_grounding_score=args.qc_min_grounding_score,
        qc_max_black_frame_ratio=args.qc_max_black_frame_ratio,
        qc_max_no_match_rate=args.qc_max_no_match_rate,
        qc_min_median_confidence=args.qc_min_median_confidence,
        qc_min_high_confidence_ratio=args.qc_min_high_confidence_ratio,
        emit_internal_artifacts=args.emit_internal_artifacts,
        replay_mode=bool(args.replay),
    )


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
