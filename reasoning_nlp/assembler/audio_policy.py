from __future__ import annotations


def ensure_keep_original_audio(manifest_payload: dict) -> None:
    manifest_payload["keep_original_audio"] = True
