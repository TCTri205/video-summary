from __future__ import annotations

import re
import statistics
import subprocess
from pathlib import Path
from typing import Any

from reasoning_nlp.common.timecode import to_ms


def compute_alignment_metrics(alignment_payload: dict) -> dict[str, float]:
    blocks = alignment_payload.get("blocks", [])
    if not isinstance(blocks, list) or not blocks:
        return {
            "no_match_rate": 1.0,
            "median_confidence": 0.0,
            "high_confidence_ratio": 0.0,
        }

    confidences = [float(b.get("confidence", 0.0)) for b in blocks]
    no_match_count = sum(1 for b in blocks if b.get("fallback_type") == "no_match")
    high_count = sum(1 for c in confidences if c >= 0.75)
    total = len(blocks)

    return {
        "no_match_rate": no_match_count / total,
        "median_confidence": float(statistics.median(confidences)),
        "high_confidence_ratio": high_count / total,
    }


def compute_timeline_consistency(script_payload: dict, manifest_payload: dict) -> float:
    script = script_payload.get("segments", [])
    manifest = manifest_payload.get("segments", [])
    if not isinstance(script, list) or not isinstance(manifest, list) or len(script) == 0:
        return 0.0
    if len(script) != len(manifest):
        return 0.0
    matches = 0
    for s, m in zip(script, manifest):
        if s.get("source_start") == m.get("source_start") and s.get("source_end") == m.get("source_end"):
            matches += 1
    return matches / len(script)


def compute_compression_ratio(script_payload: dict, source_duration_ms: int | None) -> float:
    if source_duration_ms is None or source_duration_ms <= 0:
        return 0.0
    segments = script_payload.get("segments", [])
    if not isinstance(segments, list) or not segments:
        return 0.0
    total = 0
    for seg in segments:
        try:
            total += to_ms(str(seg.get("source_end"))) - to_ms(str(seg.get("source_start")))
        except Exception:
            continue
    return max(0.0, float(total) / float(source_duration_ms))


def compute_grounding_score(summary_payload: dict[str, Any], context_payload: list[dict[str, Any]]) -> float:
    evidence = summary_payload.get("evidence", [])
    if not isinstance(evidence, list):
        return 0.0
    if not evidence:
        return 0.0

    context_timestamps = {str(x.get("timestamp", "")) for x in context_payload if str(x.get("timestamp", ""))}
    if not context_timestamps:
        return 0.0

    item_scores: list[float] = []
    for item in evidence:
        if not isinstance(item, dict):
            item_scores.append(0.0)
            continue
        timestamps = item.get("timestamps", [])
        if not isinstance(timestamps, list) or not timestamps:
            item_scores.append(0.0)
            continue
        valid = sum(1 for ts in timestamps if str(ts) in context_timestamps)
        item_scores.append(valid / len(timestamps))

    if not item_scores:
        return 0.0
    return max(0.0, min(1.0, float(statistics.mean(item_scores))))


def compute_parse_validity_rate(summary_payload: dict[str, Any]) -> float:
    required_keys = {"title", "plot_summary", "moral_lesson", "evidence", "quality_flags", "generation_meta", "segments"}
    if not all(key in summary_payload for key in required_keys):
        return 0.0

    if not str(summary_payload.get("plot_summary", "")).strip():
        return 0.0
    if not str(summary_payload.get("moral_lesson", "")).strip():
        return 0.0

    return 1.0


def compute_black_frame_ratio(video_path: str, duration_ms: int | None = None, mode: str = "full") -> float:
    result = compute_black_frame_ratio_with_status(video_path, duration_ms=duration_ms, mode=mode)
    return float(result["ratio"])


def compute_text_video_consistency_metrics(
    summary_text: str,
    summary_text_internal: dict[str, Any],
    script_payload: dict[str, Any],
) -> dict[str, float]:
    sentences = summary_text_internal.get("sentences", [])
    if not isinstance(sentences, list):
        sentences = []

    sentence_count = len(sentences)
    grounded_count = 0
    sentence_cta_count = 0
    covered_ids: set[int] = set()

    for item in sentences:
        if not isinstance(item, dict):
            continue
        supports = item.get("support_segment_ids", [])
        if isinstance(supports, list) and any(isinstance(x, int) for x in supports):
            grounded_count += 1
            covered_ids.update(int(x) for x in supports if isinstance(x, int))
        text = str(item.get("text", "")).strip()
        if _looks_like_cta(text):
            sentence_cta_count += 1

    script_segments = script_payload.get("segments", [])
    if not isinstance(script_segments, list):
        script_segments = []

    non_cta_segment_ids: list[int] = []
    ordered_segment_ids: list[int] = []
    segment_text_parts: list[str] = []
    for seg in script_segments:
        if not isinstance(seg, dict):
            continue
        seg_id = seg.get("segment_id")
        if not isinstance(seg_id, int):
            continue
        ordered_segment_ids.append(seg_id)
        text = str(seg.get("script_text", "")).strip()
        if text and not _looks_like_cta(text):
            non_cta_segment_ids.append(seg_id)
            segment_text_parts.append(text)

    grounded_ratio = 1.0 if sentence_count == 0 else grounded_count / sentence_count

    if non_cta_segment_ids:
        seg_covered = sum(1 for sid in non_cta_segment_ids if sid in covered_ids)
        coverage_ratio = seg_covered / len(non_cta_segment_ids)
    else:
        coverage_ratio = 1.0

    order_score = _compute_sentence_order_score(sentences, ordered_segment_ids)
    segment_text = " ".join(segment_text_parts)
    overlap_score = _token_overlap_score(summary_text, segment_text)
    cta_leak_ratio = 0.0 if sentence_count == 0 else sentence_cta_count / sentence_count

    return {
        "text_sentence_grounded_ratio": max(0.0, min(1.0, float(grounded_ratio))),
        "text_segment_coverage_ratio": max(0.0, min(1.0, float(coverage_ratio))),
        "text_temporal_order_score": max(0.0, min(1.0, float(order_score))),
        "text_video_keyword_overlap": max(0.0, min(1.0, float(overlap_score))),
        "text_cta_leak_ratio": max(0.0, min(1.0, float(cta_leak_ratio))),
    }


def compute_black_frame_ratio_with_status(
    video_path: str,
    duration_ms: int | None = None,
    mode: str = "full",
) -> dict[str, Any]:
    path = Path(video_path)
    if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
        return {
            "ratio": 1.0,
            "status": "error",
            "error_code": "QC_BLACKDETECT_VIDEO_INVALID",
            "message": f"Invalid video path: {video_path}",
        }

    selected_mode = str(mode).strip().lower()
    if selected_mode == "off":
        return {
            "ratio": 0.0,
            "status": "off",
            "error_code": None,
            "message": "blackdetect disabled",
        }
    if selected_mode not in {"full", "sampled"}:
        selected_mode = "full"

    duration_seconds = max(0.0, float(duration_ms or 0) / 1000.0)
    if duration_seconds <= 0:
        duration_seconds = _probe_duration_seconds(path)
    if duration_seconds <= 0:
        return {
            "ratio": 1.0,
            "status": "error",
            "error_code": "QC_BLACKDETECT_DURATION_INVALID",
            "message": "Cannot determine positive video duration",
        }

    vf = "blackdetect=d=0.05:pix_th=0.10"
    if selected_mode == "sampled":
        vf = "fps=2," + vf

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(path),
        "-vf",
        vf,
        "-an",
        "-f",
        "null",
        "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return {
            "ratio": 1.0,
            "status": "error",
            "error_code": "QC_BLACKDETECT_TIMEOUT",
            "message": "ffmpeg blackdetect timed out",
        }
    except Exception as exc:
        return {
            "ratio": 1.0,
            "status": "error",
            "error_code": "QC_BLACKDETECT_RUN_FAILED",
            "message": str(exc),
        }

    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "ffmpeg blackdetect failed").strip()
        return {
            "ratio": 1.0,
            "status": "error",
            "error_code": "QC_BLACKDETECT_FAILED",
            "message": msg[-500:],
        }

    text = f"{proc.stdout}\n{proc.stderr}"
    black_seconds = _sum_black_duration(text)
    ratio = black_seconds / duration_seconds if duration_seconds > 0 else 1.0
    return {
        "ratio": max(0.0, min(1.0, ratio)),
        "status": "ok",
        "error_code": None,
        "message": "",
    }


def _probe_duration_seconds(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return 0.0
    try:
        return float((proc.stdout or "").strip())
    except Exception:
        return 0.0


def _sum_black_duration(log_text: str) -> float:
    total = 0.0
    for match in re.findall(r"black_duration:([0-9]+(?:\.[0-9]+)?)", log_text):
        try:
            total += float(match)
        except Exception:
            continue
    return max(0.0, total)


def _compute_sentence_order_score(sentences: list[Any], ordered_segment_ids: list[int]) -> float:
    if len(ordered_segment_ids) <= 1:
        return 1.0
    index_by_id = {seg_id: idx for idx, seg_id in enumerate(ordered_segment_ids)}

    anchors: list[int] = []
    for item in sentences:
        if not isinstance(item, dict):
            continue
        supports = item.get("support_segment_ids", [])
        if not isinstance(supports, list):
            continue
        positions = [index_by_id[int(x)] for x in supports if isinstance(x, int) and int(x) in index_by_id]
        if positions:
            anchors.append(min(positions))

    if len(anchors) <= 1:
        return 1.0

    good = 0
    total = len(anchors) - 1
    for left, right in zip(anchors, anchors[1:]):
        if right >= left:
            good += 1
    return good / total if total > 0 else 1.0


def _token_overlap_score(left: str, right: str) -> float:
    left_tokens = set(_tokenize(left))
    right_tokens = set(_tokenize(right))
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    inter = len(left_tokens.intersection(right_tokens))
    union = len(left_tokens.union(right_tokens))
    if union <= 0:
        return 0.0
    return inter / union


def _tokenize(text: str) -> list[str]:
    return [x for x in re.findall(r"\b\w+\b", str(text).lower(), flags=re.UNICODE) if x]


def _looks_like_cta(text: str) -> bool:
    lowered = str(text).strip().lower()
    if not lowered:
        return False
    patterns = [
        r"\blike\b",
        r"\bcomment\b",
        r"\bsubscribe\b",
        r"\bdang\s*ky\b",
        r"\bdang\s*ki\b",
    ]
    return any(re.search(pattern, lowered) for pattern in patterns)
