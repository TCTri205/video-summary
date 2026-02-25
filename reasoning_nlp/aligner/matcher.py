from __future__ import annotations

import statistics
from dataclasses import dataclass

from reasoning_nlp.common.types import CanonicalCaption, CanonicalTranscript


@dataclass(frozen=True)
class MatchResult:
    transcript_ids: list[str]
    dialogue_text: str
    fallback_type: str
    distance_ms: int
    match_type_rank: int


def compute_adaptive_delta_ms(
    transcripts: list[CanonicalTranscript],
    k: float,
    min_delta_ms: int,
    max_delta_ms: int,
) -> int:
    durations = [max(1, t.end_ms - t.start_ms) for t in transcripts]
    median_duration = statistics.median(durations) if durations else min_delta_ms
    raw = int(round(k * float(median_duration)))
    return max(min_delta_ms, min(max_delta_ms, raw))


def match_captions(
    transcripts: list[CanonicalTranscript],
    captions: list[CanonicalCaption],
    delta_ms: int,
) -> list[MatchResult]:
    results: list[MatchResult] = []
    for caption in captions:
        t = caption.timestamp_ms
        candidates: list[tuple[int, int, int, int, CanonicalTranscript]] = []
        for tr in transcripts:
            in_range = tr.start_ms <= t <= tr.end_ms
            dist = min(abs(t - tr.start_ms), abs(t - tr.end_ms))
            if in_range:
                candidates.append((0, dist, tr.start_ms, tr.index, tr))
            elif dist <= delta_ms:
                candidates.append((1, dist, tr.start_ms, tr.index, tr))

        if not candidates:
            results.append(
                MatchResult(
                    transcript_ids=[],
                    dialogue_text="(khong co)",
                    fallback_type="no_match",
                    distance_ms=delta_ms,
                    match_type_rank=2,
                )
            )
            continue

        best = sorted(candidates, key=lambda x: (x[0], x[1], x[2], x[3]))[0]
        _, dist, _, _, tr = best
        fallback = "containment" if best[0] == 0 else "nearest"
        results.append(
            MatchResult(
                transcript_ids=[tr.transcript_id],
                dialogue_text=tr.text,
                fallback_type=fallback,
                distance_ms=dist,
                match_type_rank=best[0],
            )
        )

    return results
