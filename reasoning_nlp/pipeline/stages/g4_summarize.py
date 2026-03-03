from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from reasoning_nlp.common.errors import PipelineError, fail
from reasoning_nlp.common.io_json import write_json
from reasoning_nlp.pipeline.stages.stage_utils import append_stage_result
from reasoning_nlp.segment_planner.budget_policy import BudgetConfig
from reasoning_nlp.segment_planner.planner import plan_segments_from_context
from reasoning_nlp.summarizer.grounding_checks import check_grounding
from reasoning_nlp.summarizer.llm_client import generate_internal_summary
from reasoning_nlp.summarizer.parse_repair import repair_internal_summary
from reasoning_nlp.qc.metrics import compute_parse_validity_rate
from reasoning_nlp.validators.artifact_validator import validate_summary_internal_artifact


def run_g4_summarize(
    config,
    context_payload: list[dict[str, Any]],
    source_duration_ms: int | None,
    base: Path,
    stage_results: list[dict[str, Any]],
    logger,
) -> dict[str, Any]:
    import time

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
        if bool(config.emit_internal_artifacts):
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

        if bool(config.emit_internal_artifacts):
            out_path = base / "g4_summarize" / "summary_script.internal.json"
            write_json(out_path, repaired)

        append_stage_result(stage_results, stage, "pass", started)
        logger.info("run stage=%s status=pass", stage)
        return repaired
    except PipelineError as err:
        append_stage_result(stage_results, stage, "fail", started, error_code=err.code)
        logger.error("run stage=%s status=fail error_code=%s", stage, err.code)
        raise
    except Exception as exc:
        append_stage_result(stage_results, stage, "fail", started, error_code="LLM_BACKEND_ALL_FAILED")
        logger.error("run stage=%s status=fail error_code=LLM_BACKEND_ALL_FAILED", stage)
        raise fail(stage, "LLM_BACKEND_ALL_FAILED", str(exc)) from exc
