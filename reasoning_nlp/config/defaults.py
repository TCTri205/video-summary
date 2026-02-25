"""Default configuration for Reasoning-NLP pipeline."""

DEFAULT_ALIGNMENT = {
    "k": 1.2,
    "min_delta_ms": 1500,
    "max_delta_ms": 6000,
}

DEFAULT_RUNTIME = {
    "input_profile": "strict_contract_v1",
    "artifacts_root": "artifacts",
    "emit_internal_artifacts": True,
}

DEFAULT_SUMMARIZATION = {
    "seed": 42,
    "temperature": 0.1,
    "model_version": "Qwen2.5-3B-Instruct",
    "tokenizer_version": "default",
}

DEFAULT_SEGMENT_BUDGET = {
    "min_segment_duration_ms": 1200,
    "max_segment_duration_ms": 15000,
    "min_total_duration_ms": 3000,
    "max_total_duration_ms": 45000,
    "target_ratio": None,
    "target_ratio_tolerance": 0.20,
}
