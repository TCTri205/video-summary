from __future__ import annotations

import unittest
from argparse import Namespace

from reasoning_nlp.cli import build_config_from_args


class CLIConfigTests(unittest.TestCase):
    def test_build_config_uses_model_version_arg(self) -> None:
        args = Namespace(
            audio_transcripts="a.json",
            visual_captions="b.json",
            raw_video="c.mp4",
            run_id="run_1",
            artifacts_root="artifacts",
            deliverables_root="deliverables",
            input_profile="strict_contract_v1",
            source_duration_ms=None,
            min_segment_duration_ms=1400,
            max_segment_duration_ms=12000,
            min_total_duration_ms=5000,
            max_total_duration_ms=160000,
            target_ratio=0.10,
            target_ratio_tolerance=0.15,
            model_version="Qwen/Qwen2.5-1.5B-Instruct",
            summarize_backend="local",
            summarize_fallback_backend="api",
            summarize_timeout_ms=30000,
            summarize_max_retries=1,
            summarize_max_new_tokens=256,
            summarize_do_sample=False,
            summarize_prompt_max_chars=12000,
            summarize_production_strict=True,
            allow_heuristic_for_tests=False,
            planner_lexical_enabled=False,
            planner_lexical_weight=0.33,
            planner_lexical_min_df=2,
            planner_lexical_min_token_len=3,
            planner_lexical_use_idf=False,
            planner_lexical_stopwords_profile="vi",
            qc_enforce_thresholds=False,
            qc_blackdetect_mode="auto",
            qc_min_parse_validity_rate=0.995,
            qc_min_timeline_consistency_score=0.90,
            qc_min_grounding_score=0.85,
            qc_max_black_frame_ratio=0.02,
            qc_max_no_match_rate=0.30,
            qc_min_median_confidence=0.60,
            qc_min_high_confidence_ratio=0.50,
            emit_internal_artifacts=None,
            debug_artifacts=None,
            strict_replay_hash=False,
            replay=False,
            runtime_profile="full",
        )

        config = build_config_from_args(args)
        self.assertEqual(config.model_version, "Qwen/Qwen2.5-1.5B-Instruct")
        self.assertEqual(config.summarize_backend, "local")
        self.assertEqual(config.summarize_fallback_backend, "api")
        self.assertFalse(config.planner_lexical_enabled)
        self.assertAlmostEqual(config.planner_lexical_weight, 0.33)
        self.assertEqual(config.planner_lexical_min_df, 2)
        self.assertEqual(config.planner_lexical_min_token_len, 3)
        self.assertFalse(config.planner_lexical_use_idf)
        self.assertEqual(config.planner_lexical_stopwords_profile, "vi")
        self.assertEqual(config.min_segment_duration_ms, 1400)
        self.assertEqual(config.max_segment_duration_ms, 12000)
        self.assertEqual(config.min_total_duration_ms, 5000)
        self.assertEqual(config.max_total_duration_ms, 160000)
        self.assertEqual(config.target_ratio, 0.10)
        self.assertEqual(config.target_ratio_tolerance, 0.15)
        self.assertFalse(config.emit_internal_artifacts)


if __name__ == "__main__":
    unittest.main()
