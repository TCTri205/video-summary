from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from reasoning_nlp.eval.news_summary_finetune import (
    ColabGpuProfile,
    NewsSummaryFineTuneConfig,
    build_before_after_comparison,
    build_post_train_baseline_config,
    build_sft_config_kwargs,
    prepare_clean_corpus,
    refresh_checkpoint_index,
    require_baseline_manifest,
    resolve_colab_safe_profile,
    resolve_runtime_precision,
    resolve_training_split_config,
    split_train_eval_by_frozen_ids,
    validate_baseline_protocol_compatibility,
)


class NewsSummaryFineTuneTests(unittest.TestCase):
    def test_split_train_eval_by_frozen_ids_reuses_existing_file(self) -> None:
        clean_df = pd.DataFrame(
            {
                "example_id": ["example_00000", "example_00001", "example_00002"],
                "article_text": ["a", "b", "c"],
                "headline_text": ["ha", "hb", "hc"],
                "reference_summary": ["sa", "sb", "sc"],
            }
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            frozen_path = Path(tmp_dir) / "frozen_eval_ids.csv"
            pd.DataFrame({"example_id": ["example_00001"]}).to_csv(frozen_path, index=False)

            train_df, eval_df, profile = split_train_eval_by_frozen_ids(
                clean_df=clean_df,
                frozen_eval_ids_path=frozen_path,
                max_eval_samples=2,
                random_seed=42,
            )

            self.assertEqual(eval_df["example_id"].tolist(), ["example_00001"])
            self.assertEqual(sorted(train_df["example_id"].tolist()), ["example_00000", "example_00002"])
            self.assertEqual(profile["sampling_mode"], "reuse_existing_frozen_ids")

    def test_prepare_clean_corpus_matches_baseline_style(self) -> None:
        raw_df = pd.DataFrame(
            {
                "ctext": ["  A story   ", "B story", "B story"],
                "text": [" Summary A ", "Summary B", "Summary B dup"],
                "headlines": [" Head A ", "Head B", "Head B"],
            }
        )
        clean_df = prepare_clean_corpus(
            raw_df,
            article_col="ctext",
            summary_col="text",
            aux_headline_col="headlines",
        )
        self.assertEqual(clean_df["example_id"].tolist(), ["example_00000", "example_00001"])
        self.assertEqual(clean_df["article_text"].tolist(), ["A story", "B story"])
        self.assertEqual(clean_df["headline_text"].tolist(), ["Head A", "Head B"])

    def test_refresh_checkpoint_index_keeps_latest_and_best(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_root = Path(tmp_dir) / "run"
            archive_dir = run_root / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            for step in (10, 20, 30):
                checkpoint = archive_dir / f"checkpoint-{step}"
                checkpoint.mkdir(parents=True, exist_ok=True)
                (checkpoint / "trainer_state.json").write_text("{}", encoding="utf-8")

            payload = refresh_checkpoint_index(
                run_root=run_root,
                archive_dir=archive_dir,
                keep_last=1,
                best_checkpoint_path=str(archive_dir / "checkpoint-20"),
            )

            self.assertEqual(payload["latest_checkpoint"], str(archive_dir / "checkpoint-30"))
            self.assertEqual(payload["best_checkpoint"], str(archive_dir / "checkpoint-20"))
            self.assertTrue((run_root / "latest" / "checkpoint_ref.json").exists())
            self.assertTrue((run_root / "best" / "checkpoint_ref.json").exists())
            self.assertFalse((archive_dir / "checkpoint-10").exists())
            self.assertTrue((archive_dir / "checkpoint-20").exists())
            self.assertTrue((archive_dir / "checkpoint-30").exists())

    def test_build_before_after_comparison_computes_delta(self) -> None:
        frame = build_before_after_comparison(
            baseline_metrics={"rougeL": 0.2, "bertscore_f1": 0.8},
            finetuned_metrics={"rougeL": 0.25, "bertscore_f1": 0.82},
        )
        payload = {row["metric"]: row for row in frame.to_dict(orient="records")}
        self.assertAlmostEqual(payload["rougeL"]["delta"], 0.05, places=6)
        self.assertAlmostEqual(payload["bertscore_f1"]["delta"], 0.02, places=6)

    def test_build_post_train_baseline_config_reuses_supplied_cache_dir(self) -> None:
        cache_dir = Path('shared-cache')
        config = build_post_train_baseline_config(
            baseline_manifest={
                'protocol_version': 'news-summary-baseline-v1',
                'dataset_slug': 'sunnysai12345/news-summary',
                'selected_csv': 'news_summary.csv',
                'split_column': 'split',
                'target_split': 'test',
            },
            model_path=Path('runs/run_1/adapter_model'),
            results_dir=Path('runs/run_1/post_eval'),
            frozen_eval_ids_path=Path('shared/frozen_eval_ids.csv'),
            kaggle_json_drive_path=Path('kaggle.json'),
            cache_dir=cache_dir,
        )

        self.assertEqual(config.cache_dir, cache_dir)
        self.assertEqual(config.model_name, str(Path('runs/run_1/adapter_model')))

    def test_require_baseline_manifest_fails_fast_when_enabled(self) -> None:
        with self.assertRaises(ValueError):
            require_baseline_manifest({}, enabled=True)

    def test_resolve_training_split_config_prefers_baseline_manifest(self) -> None:
        df = pd.DataFrame({"split": ["train", "test"]})
        config = NewsSummaryFineTuneConfig(
            base_model_name="Qwen/Qwen2.5-3B-Instruct",
            dataset_slug="sunnysai12345/news-summary",
            output_root=Path("out"),
            checkpoint_root=Path("ckpt"),
            cache_dir=Path("cache"),
            kaggle_json_drive_path=Path("kaggle.json"),
            split_column="ignored_split",
            target_split="ignored_target",
        )
        split_col, target_split = resolve_training_split_config(
            config,
            baseline_manifest={"split_column": "split", "target_split": "test"},
            raw_df=df,
        )
        self.assertEqual(split_col, "split")
        self.assertEqual(target_split, "test")

    def test_validate_baseline_protocol_compatibility_detects_mismatch(self) -> None:
        config = NewsSummaryFineTuneConfig(
            base_model_name="Qwen/Qwen2.5-3B-Instruct",
            dataset_slug="sunnysai12345/news-summary",
            output_root=Path("out"),
            checkpoint_root=Path("ckpt"),
            cache_dir=Path("cache"),
            kaggle_json_drive_path=Path("kaggle.json"),
        )
        with self.assertRaises(ValueError):
            validate_baseline_protocol_compatibility(
                config,
                baseline_manifest={
                    "dataset_slug": "sunnysai12345/news-summary",
                    "selected_csv": "news_summary.csv",
                    "split_column": "split",
                    "target_split": "test",
                },
                csv_filename="news_summary.csv",
                split_column="split",
                target_split="validation",
            )

    def test_resolve_colab_safe_profile_uses_t4_defaults_by_fallback(self) -> None:
        profile = resolve_colab_safe_profile(None)
        self.assertEqual(
            profile,
            ColabGpuProfile(
                name="t4_safe",
                max_seq_length=1024,
                per_device_train_batch_size=1,
                per_device_eval_batch_size=1,
                gradient_accumulation_steps=8,
                lora_rank=8,
                lora_alpha=16,
                max_eval_samples=64,
            ),
        )

    def test_resolve_colab_safe_profile_uses_l4_defaults_when_detected(self) -> None:
        profile = resolve_colab_safe_profile("NVIDIA L4")
        self.assertEqual(profile.name, "l4_safe")
        self.assertEqual(profile.max_seq_length, 1536)
        self.assertEqual(profile.per_device_train_batch_size, 1)
        self.assertEqual(profile.per_device_eval_batch_size, 1)
        self.assertEqual(profile.gradient_accumulation_steps, 8)
        self.assertEqual(profile.lora_rank, 16)
        self.assertEqual(profile.lora_alpha, 32)
        self.assertEqual(profile.max_eval_samples, 128)

    def test_resolve_runtime_precision_prefers_bf16_when_supported(self) -> None:
        self.assertEqual(
            resolve_runtime_precision(True),
            {"dtype_name": "bfloat16", "bf16": True, "fp16": False},
        )
        self.assertEqual(
            resolve_runtime_precision(False),
            {"dtype_name": "float16", "bf16": False, "fp16": True},
        )

    def test_build_sft_config_kwargs_sets_precision_and_eval_accumulation_when_supported(self) -> None:
        class DummySFTConfig:
            def __init__(
                self,
                output_dir: str,
                bf16: bool = False,
                fp16: bool = False,
                eval_accumulation_steps: int = 0,
                max_seq_length: int = 0,
                dataset_text_field: str = "",
                evaluation_strategy: str = "",
                save_strategy: str = "",
                **_: object,
            ) -> None:
                self.output_dir = output_dir

        kwargs = build_sft_config_kwargs(
            DummySFTConfig,
            output_dir="out",
            num_train_epochs=1.0,
            per_device_train_batch_size=1,
            per_device_eval_batch_size=1,
            gradient_accumulation_steps=8,
            learning_rate=2e-4,
            warmup_steps=20,
            lr_scheduler_type="cosine",
            optim="adamw_8bit",
            weight_decay=0.01,
            logging_steps=10,
            save_steps=50,
            eval_steps=50,
            save_total_limit=2,
            report_to="none",
            seed=42,
            max_seq_length=1024,
            bf16=False,
            fp16=True,
            eval_accumulation_steps=1,
        )

        self.assertTrue(kwargs["fp16"])
        self.assertFalse(kwargs["bf16"])
        self.assertEqual(kwargs["eval_accumulation_steps"], 1)
        self.assertEqual(kwargs["max_seq_length"], 1024)
        self.assertEqual(kwargs["dataset_text_field"], "text")


if __name__ == "__main__":
    unittest.main()
