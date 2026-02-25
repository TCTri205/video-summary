from __future__ import annotations

from reasoning_nlp.common.errors import fail
from reasoning_nlp.validators.cross_file_checks import check_script_manifest_consistency


def validate_manifest_stage(
    script_payload: dict,
    manifest_payload: dict,
    source_duration_ms: int | None,
) -> None:
    errors = check_script_manifest_consistency(
        script_payload=script_payload,
        manifest_payload=manifest_payload,
        source_duration_ms=source_duration_ms,
    )
    if errors:
        raise fail("manifest", "MANIFEST_CONSISTENCY", errors[0], details={"errors": errors})
