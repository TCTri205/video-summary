from __future__ import annotations

from pathlib import Path
from typing import Any

from reasoning_nlp.common.errors import fail
from reasoning_nlp.common.io_json import read_json

try:
    import jsonschema
except Exception:
    jsonschema = None


def validate_alignment_artifact(alignment_payload: dict[str, Any], schema_path: Path) -> None:
    _validate_with_schema(
        payload=alignment_payload,
        schema_path=schema_path,
        stage="align",
        code="SCHEMA_ALIGNMENT_RESULT",
    )


def validate_summary_internal_artifact(summary_payload: dict[str, Any], schema_path: Path) -> None:
    _validate_with_schema(
        payload=summary_payload,
        schema_path=schema_path,
        stage="summarize",
        code="SCHEMA_SUMMARY_INTERNAL",
    )


def validate_deliverable_artifacts(
    script_payload: dict[str, Any],
    manifest_payload: dict[str, Any],
    script_schema_path: Path,
    manifest_schema_path: Path,
) -> None:
    _validate_with_schema(
        payload=script_payload,
        schema_path=script_schema_path,
        stage="segment_plan",
        code="SCHEMA_SUMMARY_SCRIPT",
    )
    _validate_with_schema(
        payload=manifest_payload,
        schema_path=manifest_schema_path,
        stage="segment_plan",
        code="SCHEMA_SUMMARY_MANIFEST",
    )


def validate_quality_report_artifact(report_payload: dict[str, Any], schema_path: Path) -> None:
    _validate_with_schema(
        payload=report_payload,
        schema_path=schema_path,
        stage="qc",
        code="SCHEMA_QUALITY_REPORT",
    )


def _validate_with_schema(payload: dict[str, Any], schema_path: Path, stage: str, code: str) -> None:
    if jsonschema is None:
        raise fail(
            stage,
            "SCHEMA_ENGINE_MISSING",
            "jsonschema package is required for artifact validation",
        )

    schema = read_json(schema_path)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: str(e.path))
    if errors:
        first = errors[0]
        loc = ".".join(str(x) for x in first.path) or "<root>"
        raise fail(stage, code, f"{loc}: {first.message}")
