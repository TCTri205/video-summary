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
