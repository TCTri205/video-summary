from __future__ import annotations

from reasoning_nlp.common.types import CanonicalCaption, CanonicalTranscript


def normalize_for_alignment(
    transcripts: list[CanonicalTranscript], captions: list[CanonicalCaption]
) -> tuple[list[CanonicalTranscript], list[CanonicalCaption]]:
    sorted_transcripts = sorted(transcripts, key=lambda x: (x.start_ms, x.index))
    sorted_captions = sorted(captions, key=lambda x: (x.timestamp_ms, x.index))
    return sorted_transcripts, sorted_captions
