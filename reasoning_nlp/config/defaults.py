"""Default configuration for Reasoning-NLP pipeline."""

DEFAULT_ALIGNMENT = {
    "k": 1.2,
    "min_delta_ms": 1500,
    "max_delta_ms": 6000,
}

DEFAULT_RUNTIME = {
    "input_profile": "strict_contract_v1",
    "artifacts_root": "artifacts",
    "deliverables_root": "deliverables",
    "emit_internal_artifacts": True,
    "strict_replay_hash": False,
}

DEFAULT_SUMMARIZATION = {
    "seed": 42,
    "temperature": 0.1,
    "model_version": "Qwen2.5-3B-Instruct",
    "tokenizer_version": "default",
    "backend": "api",
    "fallback_backend": "local",
    "timeout_ms": 30000,
    "max_retries": 2,
    "max_new_tokens": 512,
    "do_sample": False,
    "prompt_max_chars": 12000,
}

DEFAULT_SEGMENT_BUDGET = {
    "min_segment_duration_ms": 1200,
    "max_segment_duration_ms": 15000,
    "min_total_duration_ms": 3000,
    "max_total_duration_ms": 45000,
    "target_ratio": None,
    "target_ratio_tolerance": 0.20,
}

DEFAULT_QC = {
    "enforce_thresholds": False,
    "blackdetect_mode": "auto",
    "min_parse_validity_rate": 0.995,
    "min_timeline_consistency_score": 0.90,
    "min_grounding_score": 0.85,
    "max_black_frame_ratio": 0.02,
    "max_no_match_rate": 0.30,
    "min_median_confidence": 0.60,
    "min_high_confidence_ratio": 0.50,
}
