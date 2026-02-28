from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reasoning_nlp.common.errors import fail
from reasoning_nlp.common.io_json import read_json
from reasoning_nlp.common.timecode import ms_to_timestamp, to_ms
from reasoning_nlp.common.types import CanonicalCaption, CanonicalTranscript


@dataclass(frozen=True)
class ValidatedInput:
    input_profile: str
    transcripts: list[CanonicalTranscript]
    captions: list[CanonicalCaption]
    raw_video_path: str


def validate_and_normalize_inputs(
    audio_transcripts_path: Path,
    visual_captions_path: Path,
    raw_video_path: Path,
    profile: str,
) -> ValidatedInput:
    if not audio_transcripts_path.exists():
        raise fail("validate", "SCHEMA_INPUT_MISSING_FILE", f"Missing file: {audio_transcripts_path}")
    if not visual_captions_path.exists():
        raise fail("validate", "SCHEMA_INPUT_MISSING_FILE", f"Missing file: {visual_captions_path}")
    if not raw_video_path.exists():
        raise fail("validate", "SCHEMA_INPUT_MISSING_FILE", f"Missing file: {raw_video_path}")
    if raw_video_path.stat().st_size <= 0:
        raise fail("validate", "TIME_SOURCE_VIDEO_INVALID", "raw_video.mp4 must have size > 0")

    transcripts_payload = read_json(audio_transcripts_path)
    captions_payload = read_json(visual_captions_path)

    if profile not in {"strict_contract_v1", "legacy_member1"}:
        raise fail("validate", "SCHEMA_INPUT_PROFILE_UNSUPPORTED", f"Unsupported profile: {profile}")

    if profile == "strict_contract_v1":
        transcripts = _normalize_strict_transcripts(transcripts_payload)
    else:
        transcripts = _normalize_legacy_transcripts(transcripts_payload)
    captions = _normalize_captions(captions_payload)

    return ValidatedInput(
        input_profile=profile,
        transcripts=transcripts,
        captions=captions,
        raw_video_path=str(raw_video_path),
    )


def _normalize_strict_transcripts(payload: Any) -> list[CanonicalTranscript]:
    if not isinstance(payload, list):
        raise fail("validate", "SCHEMA_INPUT_TRANSCRIPT_TYPE", "audio_transcripts must be an array")

    normalized: list[CanonicalTranscript] = []
    for idx, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise fail("validate", "SCHEMA_INPUT_TRANSCRIPT_ITEM_TYPE", f"Item {idx} must be an object")
        start = item.get("start")
        end = item.get("end")
        text_raw = item.get("text", "")
        if not isinstance(start, str) or not isinstance(end, str):
            raise fail("validate", "SCHEMA_INPUT_TRANSCRIPT_FIELD_TYPE", f"Item {idx} start/end must be string")

        try:
            start_ms = to_ms(start)
            end_ms = to_ms(end)
        except Exception as exc:
            raise fail("validate", "TIME_PARSE_TRANSCRIPT_TIMESTAMP", f"Item {idx}: {exc}") from exc
        if end_ms <= start_ms:
            raise fail("validate", "TIME_ORDER_TRANSCRIPT", f"Item {idx} must satisfy start < end")

        text = str(text_raw).strip()
        is_empty = len(text) == 0
        if is_empty:
            text = "(khong co)"

        transcript_id = str(item.get("transcript_id") or f"t_{idx:04d}")
        normalized.append(
            CanonicalTranscript(
                transcript_id=transcript_id,
                start=ms_to_timestamp(start_ms),
                end=ms_to_timestamp(end_ms),
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
                index=idx - 1,
                is_empty_text=is_empty,
            )
        )

    return sorted(normalized, key=lambda x: (x.start_ms, x.index))


def _normalize_legacy_transcripts(payload: Any) -> list[CanonicalTranscript]:
    if not isinstance(payload, dict):
        raise fail("validate", "SCHEMA_INPUT_TRANSCRIPT_TYPE", "legacy transcript payload must be an object")
    segments = payload.get("segments")
    if not isinstance(segments, list):
        raise fail("validate", "SCHEMA_INPUT_TRANSCRIPT_SEGMENTS", "legacy transcript payload must contain segments[]")

    normalized: list[CanonicalTranscript] = []
    for idx, item in enumerate(segments, start=1):
        if not isinstance(item, dict):
            raise fail("validate", "SCHEMA_INPUT_TRANSCRIPT_ITEM_TYPE", f"Legacy segment {idx} must be an object")
        start_ms = _legacy_time_to_ms(item.get("start"), f"segments[{idx}].start")
        end_ms = _legacy_time_to_ms(item.get("end"), f"segments[{idx}].end")
        if end_ms <= start_ms:
            raise fail("validate", "TIME_ORDER_TRANSCRIPT", f"Legacy segment {idx} must satisfy start < end")

        text = str(item.get("text", "")).strip()
        is_empty = len(text) == 0
        if is_empty:
            text = "(khong co)"

        transcript_id = str(item.get("transcript_id") or f"t_{idx:04d}")
        normalized.append(
            CanonicalTranscript(
                transcript_id=transcript_id,
                start=ms_to_timestamp(start_ms),
                end=ms_to_timestamp(end_ms),
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
                index=idx - 1,
                is_empty_text=is_empty,
            )
        )

    return sorted(normalized, key=lambda x: (x.start_ms, x.index))


def _legacy_time_to_ms(value: Any, field_name: str) -> int:
    if isinstance(value, (int, float)):
        if value < 0:
            raise fail("validate", "TIME_NEGATIVE_VALUE", f"{field_name} must be >= 0")
        return int(round(float(value) * 1000))
    if isinstance(value, str):
        try:
            return to_ms(value)
        except Exception as exc:
            raise fail("validate", "TIME_PARSE_TRANSCRIPT_TIMESTAMP", f"{field_name}: {exc}") from exc
    raise fail("validate", "SCHEMA_INPUT_TRANSCRIPT_FIELD_TYPE", f"{field_name} must be float seconds or timestamp string")


def _normalize_captions(payload: Any) -> list[CanonicalCaption]:
    if not isinstance(payload, list):
        raise fail("validate", "SCHEMA_INPUT_CAPTION_TYPE", "visual_captions must be an array")

    normalized: list[CanonicalCaption] = []
    for idx, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise fail("validate", "SCHEMA_INPUT_CAPTION_ITEM_TYPE", f"Caption {idx} must be an object")
        timestamp = item.get("timestamp")
        if not isinstance(timestamp, str):
            raise fail("validate", "SCHEMA_INPUT_CAPTION_FIELD_TYPE", f"Caption {idx} timestamp must be string")

        try:
            ts_ms = to_ms(timestamp)
        except Exception as exc:
            raise fail("validate", "TIME_PARSE_CAPTION_TIMESTAMP", f"Caption {idx}: {exc}") from exc

        caption = str(item.get("caption", "")).strip()
        is_empty = len(caption) == 0
        if is_empty:
            caption = "(khong co)"

        caption_id = str(item.get("caption_id") or f"c_{idx:04d}")
        normalized.append(
            CanonicalCaption(
                caption_id=caption_id,
                timestamp=ms_to_timestamp(ts_ms),
                timestamp_ms=ts_ms,
                caption=caption,
                index=idx - 1,
                is_empty_text=is_empty,
            )
        )

    return sorted(normalized, key=lambda x: (x.timestamp_ms, x.index))
