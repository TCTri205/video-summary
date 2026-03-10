from __future__ import annotations

import json
import inspect
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from reasoning_nlp.eval.news_summary_baseline import (
    NewsSummaryBaselineConfig,
    auto_resolve_split,
    build_production_adapted_prompt_profile,
    normalize_text,
    read_csv_robust,
    render_user_prompt,
    resolve_csv_file,
    validate_columns,
)


@dataclass(frozen=True)
class NewsSummaryFineTuneConfig:
    base_model_name: str
    dataset_slug: str
    output_root: Path
    checkpoint_root: Path
    cache_dir: Path
    kaggle_json_drive_path: Path
    csv_filename: str = "news_summary.csv"
    article_column: str = "ctext"
    summary_column: str = "text"
    aux_headline_column: str = "headlines"
    split_column: str = ""
    target_split: str = ""
    frozen_eval_ids_path: Path | None = None
    baseline_manifest_path: Path | None = None
    random_seed: int = 42
    max_eval_samples: int = 128
    max_seq_length: int = 2048
    learning_rate: float = 2e-4
    num_train_epochs: float = 2.0
    per_device_train_batch_size: int = 2
    per_device_eval_batch_size: int = 2
    gradient_accumulation_steps: int = 4
    warmup_steps: int = 20
    save_steps: int = 50
    eval_steps: int = 50
    logging_steps: int = 10
    save_total_limit: int = 2
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.0
    weight_decay: float = 0.01

    def to_serializable_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key, value in list(payload.items()):
            if isinstance(value, Path):
                payload[key] = str(value)
        return payload


@dataclass(frozen=True)
class ColabGpuProfile:
    name: str
    max_seq_length: int
    per_device_train_batch_size: int
    per_device_eval_batch_size: int
    gradient_accumulation_steps: int
    lora_rank: int
    lora_alpha: int
    max_eval_samples: int


def resolve_colab_safe_profile(gpu_name: str | None) -> ColabGpuProfile:
    normalized = str(gpu_name or "").strip().lower()
    if "l4" in normalized:
        return ColabGpuProfile(
            name="l4_safe",
            max_seq_length=1536,
            per_device_train_batch_size=1,
            per_device_eval_batch_size=1,
            gradient_accumulation_steps=8,
            lora_rank=16,
            lora_alpha=32,
            max_eval_samples=128,
        )
    return ColabGpuProfile(
        name="t4_safe",
        max_seq_length=1024,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=8,
        lora_rank=8,
        lora_alpha=16,
        max_eval_samples=64,
    )


def resolve_runtime_precision(bf16_supported: bool) -> dict[str, Any]:
    if bf16_supported:
        return {
            "dtype_name": "bfloat16",
            "bf16": True,
            "fp16": False,
        }
    return {
        "dtype_name": "float16",
        "bf16": False,
        "fp16": True,
    }


def load_baseline_manifest(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def require_baseline_manifest(baseline_manifest: dict[str, Any], enabled: bool) -> None:
    if enabled and not baseline_manifest:
        raise ValueError(
            "Baseline comparison is enabled but baseline manifest is missing. "
            "Set NEWS_SUMMARY_BASELINE_MANIFEST_PATH or disable comparison."
        )


def resolve_training_split_config(
    config: NewsSummaryFineTuneConfig,
    baseline_manifest: dict[str, Any],
    raw_df: pd.DataFrame,
) -> tuple[str, str]:
    manifest_split_column = normalize_text(baseline_manifest.get("split_column", ""))
    manifest_target_split = normalize_text(baseline_manifest.get("target_split", ""))
    if baseline_manifest:
        split_column = manifest_split_column or config.split_column
        target_split = manifest_target_split or config.target_split
        return auto_resolve_split(raw_df, split_col=split_column, target_split=target_split, use_fixed_split=True)
    return auto_resolve_split(raw_df, split_col=config.split_column, target_split=config.target_split, use_fixed_split=True)


def validate_baseline_protocol_compatibility(
    config: NewsSummaryFineTuneConfig,
    baseline_manifest: dict[str, Any],
    csv_filename: str,
    split_column: str,
    target_split: str,
) -> None:
    if not baseline_manifest:
        return
    mismatches: list[str] = []
    expected_dataset_slug = normalize_text(baseline_manifest.get("dataset_slug", ""))
    if expected_dataset_slug and expected_dataset_slug != normalize_text(config.dataset_slug):
        mismatches.append(f"dataset_slug baseline={expected_dataset_slug} current={config.dataset_slug}")
    expected_csv = normalize_text(baseline_manifest.get("selected_csv", ""))
    if expected_csv and expected_csv != normalize_text(csv_filename):
        mismatches.append(f"csv baseline={expected_csv} current={csv_filename}")
    expected_split_column = normalize_text(baseline_manifest.get("split_column", ""))
    expected_target_split = normalize_text(baseline_manifest.get("target_split", ""))
    if expected_split_column != normalize_text(split_column):
        mismatches.append(f"split_column baseline={expected_split_column or '<empty>'} current={split_column or '<empty>'}")
    if expected_target_split != normalize_text(target_split):
        mismatches.append(f"target_split baseline={expected_target_split or '<empty>'} current={target_split or '<empty>'}")
    if mismatches:
        raise ValueError("Fine-tune protocol does not match baseline manifest: " + "; ".join(mismatches))


def resolve_frozen_eval_ids_path(config: NewsSummaryFineTuneConfig, baseline_manifest: dict[str, Any]) -> Path:
    if config.frozen_eval_ids_path is not None:
        return config.frozen_eval_ids_path
    manifest_path = baseline_manifest.get("frozen_eval_ids_path")
    if manifest_path:
        return Path(str(manifest_path))
    default_name = f"{config.dataset_slug.replace('/', '__')}_frozen_eval_ids.csv"
    return config.output_root / "shared_eval" / default_name


def prepare_clean_corpus(
    df: pd.DataFrame,
    article_col: str,
    summary_col: str,
    aux_headline_col: str = "",
    split_col: str = "",
    target_split: str = "",
) -> pd.DataFrame:
    working = df.copy()
    working[article_col] = working[article_col].map(normalize_text)
    working[summary_col] = working[summary_col].map(normalize_text)
    if aux_headline_col and aux_headline_col in working.columns:
        working[aux_headline_col] = working[aux_headline_col].map(normalize_text)
    if split_col:
        wanted = normalize_text(target_split).lower()
        split_values = working[split_col].astype(str).str.strip().str.lower()
        if wanted:
            working = working.loc[split_values == wanted].copy()
    working = working.loc[working[article_col].ne("") & working[summary_col].ne("")].copy()
    working = working.drop_duplicates(subset=[article_col]).reset_index(drop=True)
    working = working.rename(columns={article_col: "article_text", summary_col: "reference_summary"})
    if aux_headline_col and aux_headline_col in working.columns:
        working = working.rename(columns={aux_headline_col: "headline_text"})
    else:
        working["headline_text"] = ""
    working.insert(0, "example_id", [f"example_{idx:05d}" for idx in range(len(working))])
    return working.reset_index(drop=True)


def split_train_eval_by_frozen_ids(
    clean_df: pd.DataFrame,
    frozen_eval_ids_path: Path,
    max_eval_samples: int,
    random_seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    frozen_eval_ids_path.parent.mkdir(parents=True, exist_ok=True)
    if frozen_eval_ids_path.exists():
        eval_ids = pd.read_csv(frozen_eval_ids_path)["example_id"].astype(str).tolist()
        sampling_mode = "reuse_existing_frozen_ids"
    else:
        sampled = clean_df.sample(
            n=min(max_eval_samples, len(clean_df)),
            random_state=int(random_seed),
        ).sort_values("example_id")
        eval_ids = sampled["example_id"].astype(str).tolist()
        pd.DataFrame({"example_id": eval_ids}).to_csv(frozen_eval_ids_path, index=False)
        sampling_mode = "created_new_frozen_ids"
    eval_df = clean_df.loc[clean_df["example_id"].isin(eval_ids)].sort_values("example_id").reset_index(drop=True)
    train_df = clean_df.loc[~clean_df["example_id"].isin(eval_ids)].sort_values("example_id").reset_index(drop=True)
    if eval_df.empty:
        raise ValueError("Frozen eval ids produced an empty eval set")
    if train_df.empty:
        raise ValueError("Train set is empty after removing frozen eval ids")
    return train_df, eval_df, {
        "sampling_mode": sampling_mode,
        "train_rows": int(len(train_df)),
        "eval_rows": int(len(eval_df)),
        "frozen_eval_ids_path": str(frozen_eval_ids_path),
    }


def build_training_messages(row: dict[str, Any]) -> list[dict[str, str]]:
    prompt_profile = build_production_adapted_prompt_profile()
    assistant_payload = json.dumps({"summary": normalize_text(row["reference_summary"])}, ensure_ascii=False)
    return [
        {"role": "system", "content": prompt_profile.system_prompt},
        {"role": "user", "content": render_user_prompt(row["article_text"], row.get("headline_text", ""))},
        {"role": "assistant", "content": assistant_payload},
    ]


def build_training_text(row: dict[str, Any], tokenizer: Any) -> str:
    messages = build_training_messages(row)
    if hasattr(tokenizer, "apply_chat_template"):
        return tokenizer.apply_chat_template(messages, tokenize=False)
    fallback_lines = []
    for message in messages:
        fallback_lines.append(f"{message['role'].upper()}: {message['content']}")
    return "\n\n".join(fallback_lines)


def prepare_training_records(clean_df: pd.DataFrame, tokenizer: Any) -> pd.DataFrame:
    records = clean_df[["example_id", "article_text", "headline_text", "reference_summary"]].copy()
    records["text"] = records.apply(lambda row: build_training_text(row.to_dict(), tokenizer), axis=1)
    records["assistant_json"] = records["reference_summary"].map(lambda value: json.dumps({"summary": normalize_text(value)}, ensure_ascii=False))
    return records


def build_run_paths(output_root: Path, run_name: str) -> dict[str, Path]:
    run_root = output_root / run_name
    return {
        "run_root": run_root,
        "archive_dir": run_root / "archive",
        "latest_dir": run_root / "latest",
        "best_dir": run_root / "best",
        "adapter_dir": run_root / "adapter_model",
        "post_eval_dir": run_root / "eval_after_train",
        "checkpoint_index_path": run_root / "checkpoint_index.json",
        "training_manifest_path": run_root / "training_manifest.json",
        "before_after_csv": run_root / "before_after_comparison.csv",
    }


def build_sft_config_kwargs(
    sft_config_cls: Any,
    *,
    output_dir: str,
    num_train_epochs: float,
    per_device_train_batch_size: int,
    per_device_eval_batch_size: int,
    gradient_accumulation_steps: int,
    learning_rate: float,
    warmup_steps: int,
    lr_scheduler_type: str,
    optim: str,
    weight_decay: float,
    logging_steps: int,
    save_steps: int,
    eval_steps: int,
    save_total_limit: int,
    report_to: str,
    seed: int,
    max_seq_length: int,
    bf16: bool,
    fp16: bool,
    eval_accumulation_steps: int = 1,
) -> dict[str, Any]:
    params = inspect.signature(sft_config_cls.__init__).parameters
    kwargs: dict[str, Any] = {
        "output_dir": output_dir,
        "overwrite_output_dir": False,
        "num_train_epochs": num_train_epochs,
        "per_device_train_batch_size": per_device_train_batch_size,
        "per_device_eval_batch_size": per_device_eval_batch_size,
        "gradient_accumulation_steps": gradient_accumulation_steps,
        "learning_rate": learning_rate,
        "warmup_steps": warmup_steps,
        "lr_scheduler_type": lr_scheduler_type,
        "optim": optim,
        "weight_decay": weight_decay,
        "logging_steps": logging_steps,
        "save_steps": save_steps,
        "eval_steps": eval_steps,
        "load_best_model_at_end": True,
        "metric_for_best_model": "eval_loss",
        "greater_is_better": False,
        "save_total_limit": save_total_limit,
        "report_to": report_to,
        "seed": seed,
        "packing": False,
    }
    if "bf16" in params:
        kwargs["bf16"] = bf16
    if "fp16" in params:
        kwargs["fp16"] = fp16
    if "eval_accumulation_steps" in params:
        kwargs["eval_accumulation_steps"] = eval_accumulation_steps
    if "save_strategy" in params:
        kwargs["save_strategy"] = "steps"
    if "evaluation_strategy" in params:
        kwargs["evaluation_strategy"] = "steps"
    elif "eval_strategy" in params:
        kwargs["eval_strategy"] = "steps"
    if "max_length" in params:
        kwargs["max_length"] = max_seq_length
    elif "max_seq_length" in params:
        kwargs["max_seq_length"] = max_seq_length
    if "dataset_text_field" in params:
        kwargs["dataset_text_field"] = "text"
    return kwargs


def _checkpoint_step(path: Path) -> int:
    suffix = path.name.split("-")[-1]
    try:
        return int(suffix)
    except ValueError:
        return -1


def list_checkpoints(archive_dir: Path) -> list[Path]:
    if not archive_dir.exists():
        return []
    return sorted(
        [path for path in archive_dir.iterdir() if path.is_dir() and path.name.startswith("checkpoint-")],
        key=_checkpoint_step,
    )


def write_checkpoint_alias(alias_dir: Path, checkpoint_path: Path, label: str) -> None:
    alias_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "label": label,
        "checkpoint_path": str(checkpoint_path),
        "step": _checkpoint_step(checkpoint_path),
    }
    (alias_dir / "checkpoint_ref.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def refresh_checkpoint_index(
    run_root: Path,
    archive_dir: Path,
    keep_last: int,
    best_checkpoint_path: str | Path | None = None,
) -> dict[str, Any]:
    checkpoints = list_checkpoints(archive_dir)
    latest = checkpoints[-1] if checkpoints else None
    best = Path(best_checkpoint_path) if best_checkpoint_path else None
    kept_paths = set()
    if latest is not None:
        kept_paths.add(latest.resolve())
        write_checkpoint_alias(run_root / "latest", latest, "latest")
    if best is not None and best.exists():
        kept_paths.add(best.resolve())
        write_checkpoint_alias(run_root / "best", best, "best")
    recent = checkpoints[-keep_last:] if keep_last > 0 else []
    for checkpoint in recent:
        kept_paths.add(checkpoint.resolve())
    pruned: list[str] = []
    for checkpoint in checkpoints:
        if checkpoint.resolve() in kept_paths:
            continue
        shutil.rmtree(checkpoint, ignore_errors=True)
        pruned.append(str(checkpoint))
    remaining = [str(path) for path in list_checkpoints(archive_dir)]
    payload = {
        "latest_checkpoint": str(latest) if latest else "",
        "best_checkpoint": str(best) if best and best.exists() else "",
        "remaining_checkpoints": remaining,
        "pruned_checkpoints": pruned,
        "keep_last": int(keep_last),
    }
    (run_root / "checkpoint_index.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def resolve_resume_checkpoint(run_root: Path, archive_dir: Path) -> str | None:
    latest_ref = run_root / "latest" / "checkpoint_ref.json"
    if latest_ref.exists():
        payload = json.loads(latest_ref.read_text(encoding="utf-8"))
        checkpoint_path = Path(str(payload.get("checkpoint_path", "")))
        if checkpoint_path.exists():
            return str(checkpoint_path)
    checkpoints = list_checkpoints(archive_dir)
    return str(checkpoints[-1]) if checkpoints else None


def build_training_manifest(
    config: NewsSummaryFineTuneConfig,
    run_name: str,
    run_paths: dict[str, Path],
    baseline_manifest: dict[str, Any],
    split_profile: dict[str, Any],
    resume_from_checkpoint: str | None,
) -> dict[str, Any]:
    return {
        "run_name": run_name,
        "base_model_name": config.base_model_name,
        "dataset_slug": config.dataset_slug,
        "baseline_manifest_path": str(config.baseline_manifest_path) if config.baseline_manifest_path else "",
        "baseline_metrics": baseline_manifest.get("metrics", {}),
        "frozen_eval_ids_path": split_profile.get("frozen_eval_ids_path", ""),
        "train_rows": split_profile.get("train_rows", 0),
        "eval_rows": split_profile.get("eval_rows", 0),
        "resume_from_checkpoint": resume_from_checkpoint or "",
        "paths": {name: str(path) for name, path in run_paths.items()},
        "hyperparameters": config.to_serializable_dict(),
    }


def write_training_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_before_after_comparison(
    baseline_metrics: dict[str, Any],
    finetuned_metrics: dict[str, Any],
) -> pd.DataFrame:
    metric_names = sorted(set(baseline_metrics) | set(finetuned_metrics))
    rows = []
    for name in metric_names:
        base_value = baseline_metrics.get(name)
        tuned_value = finetuned_metrics.get(name)
        delta = None
        if isinstance(base_value, (int, float)) and isinstance(tuned_value, (int, float)):
            delta = float(tuned_value) - float(base_value)
        rows.append(
            {
                "metric": name,
                "baseline": base_value,
                "finetuned": tuned_value,
                "delta": delta,
            }
        )
    return pd.DataFrame(rows)


def build_checkpoint_callback(run_root: Path, archive_dir: Path, keep_last: int) -> Any:
    from transformers import TrainerCallback

    class SmartCheckpointCallback(TrainerCallback):
        def on_save(self, args, state, control, **kwargs):
            refresh_checkpoint_index(
                run_root=run_root,
                archive_dir=archive_dir,
                keep_last=keep_last,
                best_checkpoint_path=state.best_model_checkpoint,
            )
            return control

        def on_train_end(self, args, state, control, **kwargs):
            refresh_checkpoint_index(
                run_root=run_root,
                archive_dir=archive_dir,
                keep_last=keep_last,
                best_checkpoint_path=state.best_model_checkpoint,
            )
            return control

    return SmartCheckpointCallback()


def load_training_dataframe(
    csv_path: Path,
    article_column: str,
    summary_column: str,
    aux_headline_column: str,
    split_column: str = "",
    target_split: str = "",
) -> pd.DataFrame:
    raw_df = read_csv_robust(csv_path)
    validate_columns(raw_df, article_column, summary_column, aux_headline_column)
    return prepare_clean_corpus(
        raw_df,
        article_col=article_column,
        summary_col=summary_column,
        aux_headline_col=aux_headline_column,
        split_col=split_column,
        target_split=target_split,
    )


def build_post_train_baseline_config(
    baseline_manifest: dict[str, Any],
    model_path: Path,
    results_dir: Path,
    frozen_eval_ids_path: Path,
    kaggle_json_drive_path: Path,
) -> NewsSummaryBaselineConfig:
    return NewsSummaryBaselineConfig(
        protocol_version=str(baseline_manifest.get("protocol_version", "news-summary-baseline-v1")),
        dataset_slug=str(baseline_manifest.get("dataset_slug", "sunnysai12345/news-summary")),
        cache_dir=results_dir.parent / "cache",
        results_dir=results_dir,
        kaggle_json_drive_path=kaggle_json_drive_path,
        csv_filename=str(baseline_manifest.get("selected_csv", "news_summary.csv")),
        article_column="ctext",
        summary_column="text",
        aux_headline_column="headlines",
        split_column=str(baseline_manifest.get("split_column", "")),
        target_split=str(baseline_manifest.get("target_split", "")),
        use_fixed_split=bool(baseline_manifest.get("split_column")),
        frozen_eval_ids_path=frozen_eval_ids_path,
        model_name=str(model_path),
        backend="local",
        max_samples=10**9,
        random_seed=42,
        save_predictions_with_article=False,
    )
