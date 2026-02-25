from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalTranscript:
    transcript_id: str
    start: str
    end: str
    start_ms: int
    end_ms: int
    text: str
    index: int
    is_empty_text: bool = False


@dataclass(frozen=True)
class CanonicalCaption:
    caption_id: str
    timestamp: str
    timestamp_ms: int
    caption: str
    index: int
    is_empty_text: bool = False


@dataclass(frozen=True)
class AlignmentBlock:
    caption_id: str
    timestamp: str
    image_text: str
    dialogue_text: str
    matched_transcript_ids: list[str]
    fallback_type: str
    confidence: float
