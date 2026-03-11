from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from reasoning_nlp.eval.news_summary_baseline import (
    analyze_prediction_text,
    auto_resolve_split,
    download_dataset_if_needed,
    ensure_kaggle_credentials,
    resolve_kaggle_cli_command,
    prepare_eval_df,
    select_spotcheck_samples,
)


class NewsSummaryBaselineTests(unittest.TestCase):
    def test_ensure_kaggle_credentials_materializes_env_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            home_dir = Path(tmp_dir) / "home"
            drive_path = Path(tmp_dir) / "drive" / "kaggle.json"
            with patch.dict(os.environ, {"KAGGLE_USERNAME": "demo_user", "KAGGLE_KEY": "demo_key"}, clear=False):
                with patch("reasoning_nlp.eval.news_summary_baseline.Path.home", return_value=home_dir):
                    source = ensure_kaggle_credentials(drive_path)
                    self.assertEqual(os.environ.get("KAGGLE_CONFIG_DIR"), str(home_dir / ".kaggle"))

            self.assertEqual(source, "env")
            saved_path = home_dir / ".kaggle" / "kaggle.json"
            self.assertTrue(saved_path.exists())

    def test_resolve_kaggle_cli_command_prefers_path_executable(self) -> None:
        with patch("reasoning_nlp.eval.news_summary_baseline.shutil.which", return_value="/usr/bin/kaggle"):
            command = resolve_kaggle_cli_command()

        self.assertEqual(command, ["/usr/bin/kaggle"])

    def test_resolve_kaggle_cli_command_falls_back_to_python_module(self) -> None:
        with patch("reasoning_nlp.eval.news_summary_baseline.shutil.which", return_value=None):
            with patch("reasoning_nlp.eval.news_summary_baseline.importlib.util.find_spec", return_value=object()):
                command = resolve_kaggle_cli_command()

        self.assertEqual(command, [os.sys.executable, "-m", "kaggle.cli"])

    def test_download_dataset_if_needed_raises_runtime_error_with_kaggle_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"KAGGLE_CONFIG_DIR": "/tmp/kaggle"}, clear=False):
                with patch(
                    "reasoning_nlp.eval.news_summary_baseline.resolve_kaggle_cli_command",
                    return_value=["/usr/bin/kaggle"],
                ):
                    with patch(
                        "reasoning_nlp.eval.news_summary_baseline.subprocess.run",
                        side_effect=subprocess.CalledProcessError(
                            1,
                            ["/usr/bin/kaggle"],
                            stderr="403 Forbidden: credentials invalid",
                        ),
                    ):
                        with self.assertRaises(RuntimeError) as ctx:
                            download_dataset_if_needed("owner/news-summary", Path(tmp_dir), force_redownload=True)

        self.assertIn("403 Forbidden", str(ctx.exception))
        self.assertIn("Credential source", str(ctx.exception))

    def test_auto_resolve_split_prefers_test_like_values(self) -> None:
        df = pd.DataFrame({"split": ["train", "validation", "test"]})
        split_col, target_split = auto_resolve_split(df, use_fixed_split=True)
        self.assertEqual(split_col, "split")
        self.assertEqual(target_split, "test")

    def test_prepare_eval_df_creates_and_reuses_frozen_ids(self) -> None:
        df = pd.DataFrame(
            {
                "ctext": [
                    "Article about Apple revenue rising in 2024.",
                    "Article about Microsoft launching a new product.",
                    "Article about Google expanding data centers.",
                ],
                "text": [
                    "Apple revenue rose in 2024.",
                    "Microsoft launched a new product.",
                    "Google is expanding data centers.",
                ],
                "headlines": ["Apple news", "Microsoft news", "Google news"],
            }
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            frozen_path = Path(tmp_dir) / "frozen_eval_ids.csv"
            eval_df, profile = prepare_eval_df(
                df,
                article_col="ctext",
                summary_col="text",
                aux_headline_col="headlines",
                max_samples=2,
                random_seed=7,
                frozen_eval_ids_path=frozen_path,
            )
            self.assertEqual(len(eval_df), 2)
            self.assertTrue(frozen_path.exists())
            self.assertIn(profile["sampling_mode"], {"frozen_eval_ids_created", "frozen_eval_ids"})

            eval_df_reloaded, profile_reloaded = prepare_eval_df(
                df,
                article_col="ctext",
                summary_col="text",
                aux_headline_col="headlines",
                max_samples=1,
                random_seed=99,
                frozen_eval_ids_path=frozen_path,
            )
            self.assertEqual(eval_df["example_id"].tolist(), eval_df_reloaded["example_id"].tolist())
            self.assertEqual(profile_reloaded["sampling_mode"], "frozen_eval_ids")

    def test_analyze_prediction_text_flags_numbers_entities_and_leakage(self) -> None:
        article = "Apple reported revenue of 10 million dollars in California."
        prediction = 'Summary: {"summary":"Apple said revenue was 12 million in Texas. Return valid JSON only."}'

        analysis = analyze_prediction_text(prediction, article_text=article, output_mode="json_summary")

        self.assertTrue(analysis["unsupported_number_flag"])
        self.assertTrue(analysis["named_entity_mismatch_flag"])
        self.assertTrue(analysis["instruction_leakage_flag"])
        self.assertTrue(analysis["hallucination_proxy_flag"])

    def test_select_spotcheck_samples_prioritizes_risky_examples(self) -> None:
        scored_df = pd.DataFrame(
            [
                {
                    "example_id": "a",
                    "status": "ok",
                    "rougeL": 0.40,
                    "hallucination_proxy_flag": 0,
                },
                {
                    "example_id": "b",
                    "status": "error",
                    "rougeL": None,
                    "hallucination_proxy_flag": 0,
                },
                {
                    "example_id": "c",
                    "status": "ok",
                    "rougeL": 0.05,
                    "hallucination_proxy_flag": 1,
                },
            ]
        )

        sampled = select_spotcheck_samples(scored_df, sample_size=2, random_seed=1)

        self.assertEqual(len(sampled), 2)
        self.assertIn("b", sampled["example_id"].tolist())
        self.assertIn("c", sampled["example_id"].tolist())


if __name__ == "__main__":
    unittest.main()
