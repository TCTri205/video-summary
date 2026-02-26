from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Iterable

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
    assume_sorted: bool = False,
) -> list[MatchResult]:
    if not captions:
        return []

    results: list[MatchResult | None] = [None] * len(captions)
    if assume_sorted:
        ordered_captions = list(enumerate(captions))
    else:
        ordered_captions = sorted(enumerate(captions), key=lambda x: (x[1].timestamp_ms, x[1].index))

    left = 0
    right = 0
    transcript_count = len(transcripts)

    for original_idx, caption in ordered_captions:
        t = caption.timestamp_ms
        upper_bound = t + delta_ms
        lower_bound = t - delta_ms

        while right < transcript_count and transcripts[right].start_ms <= upper_bound:
            right += 1

        while left < right and transcripts[left].end_ms < lower_bound:
            left += 1

        best = _select_best_candidate(t, transcripts[left:right], delta_ms)
        if best is None:
            results[original_idx] = MatchResult(
                transcript_ids=[],
                dialogue_text="(khong co)",
                fallback_type="no_match",
                distance_ms=delta_ms,
                match_type_rank=2,
            )
            continue

        _, dist, _, _, tr = best
        fallback = "containment" if best[0] == 0 else "nearest"
        results[original_idx] = MatchResult(
            transcript_ids=[tr.transcript_id],
            dialogue_text=tr.text,
            fallback_type=fallback,
            distance_ms=dist,
            match_type_rank=best[0],
        )

    final_results: list[MatchResult] = []
    for item in results:
        if item is None:
            raise RuntimeError("internal matcher error: missing result item")
        final_results.append(item)
    return final_results


def _select_best_candidate(
    timestamp_ms: int,
    candidates: Iterable[CanonicalTranscript],
    delta_ms: int,
) -> tuple[int, int, int, int, CanonicalTranscript] | None:
    best: tuple[int, int, int, int, CanonicalTranscript] | None = None
    for tr in candidates:
        in_range = tr.start_ms <= timestamp_ms <= tr.end_ms
        dist = min(abs(timestamp_ms - tr.start_ms), abs(timestamp_ms - tr.end_ms))
        if in_range:
            candidate = (0, dist, tr.start_ms, tr.index, tr)
        elif dist <= delta_ms:
            candidate = (1, dist, tr.start_ms, tr.index, tr)
        else:
            continue

        if best is None or candidate < best:
            best = candidate
    return best
