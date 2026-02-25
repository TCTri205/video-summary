from __future__ import annotations

from typing import Any


def check_grounding(summary_payload: dict[str, Any], context_blocks: list[dict[str, object]]) -> list[str]:
    context_timestamps = {str(x.get("timestamp", "")) for x in context_blocks}
    errors: list[str] = []

    evidence = summary_payload.get("evidence", [])
    if not isinstance(evidence, list):
        return ["LLM_EVIDENCE_TYPE"]

    for idx, item in enumerate(evidence):
        if not isinstance(item, dict):
            errors.append(f"LLM_EVIDENCE_ITEM_TYPE_{idx}")
            continue
        timestamps = item.get("timestamps")
        if not isinstance(timestamps, list) or len(timestamps) == 0:
            errors.append(f"LLM_EVIDENCE_TIMESTAMPS_{idx}")
            continue
        for ts in timestamps:
            if str(ts) not in context_timestamps:
                errors.append(f"LLM_GROUNDING_TIMESTAMP_MISSING_{idx}")
    return errors
