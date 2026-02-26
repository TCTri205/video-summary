from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from reasoning_nlp.common.errors import fail
from reasoning_nlp.common.timecode import to_ms


def render_summary_video(source_video_path: str, output_video_path: str, segments: list[dict[str, Any]]) -> dict[str, object]:
    source = Path(source_video_path).resolve()
    output = Path(output_video_path).resolve()

    if not source.exists() or source.stat().st_size <= 0:
        raise fail("assemble", "RENDER_SOURCE_INVALID", f"Invalid source video: {source_video_path}")
    if not isinstance(segments, list) or len(segments) == 0:
        raise fail("assemble", "RENDER_SEGMENTS_EMPTY", "Manifest segments must be a non-empty list")

    output.parent.mkdir(parents=True, exist_ok=True)

    retry_count = 0
    try:
        _render_with_profile(source, output, segments, safe_profile=False)
    except PipelineRuntimeError:
        retry_count = 1
        try:
            _render_with_profile(source, output, segments, safe_profile=True)
        except PipelineRuntimeError as exc:
            raise fail("assemble", "RENDER_FATAL", str(exc)) from exc

    duration_ms = _probe_duration_ms(output)
    audio_present = _probe_has_audio_stream(output)
    if not audio_present:
        raise fail("assemble", "RENDER_AUDIO_MISSING", "Rendered summary video does not contain audio stream")

    expected_total_duration_ms = _sum_segment_durations_ms(segments)
    duration_match_score = _duration_match_score(duration_ms, expected_total_duration_ms)

    return {
        "render_success": True,
        "audio_present": audio_present,
        "decode_error_count": 0,
        "duration_ms": duration_ms,
        "expected_duration_ms": expected_total_duration_ms,
        "duration_match_score": duration_match_score,
        "retry_count": retry_count,
        "output_video_path": str(output),
    }


class PipelineRuntimeError(RuntimeError):
    pass


def _render_with_profile(source: Path, output: Path, segments: list[dict[str, Any]], safe_profile: bool) -> None:
    filter_complex = _build_filter_complex(segments)
    concat_cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast" if safe_profile else "veryfast",
        "-crf",
        "23" if safe_profile else "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output),
    ]
    _run_checked(concat_cmd, "concat")


def _build_filter_complex(segments: list[dict[str, Any]]) -> str:
    chains: list[str] = []
    v_labels: list[str] = []
    a_labels: list[str] = []

    for idx, seg in enumerate(segments):
        start = str(seg.get("source_start", "00:00:00.000"))
        end = str(seg.get("source_end", "00:00:00.000"))
        start_sec = _ts_to_seconds(start)
        end_sec = _ts_to_seconds(end)
        if end_sec <= start_sec:
            raise PipelineRuntimeError(f"RENDER_CUT_FAILED: invalid segment range {start} -> {end}")

        v_label = f"v{idx}"
        a_label = f"a{idx}"
        v_labels.append(f"[{v_label}]")
        a_labels.append(f"[{a_label}]")
        chains.append(
            f"[0:v]trim=start={start_sec:.3f}:end={end_sec:.3f},setpts=PTS-STARTPTS[{v_label}]"
        )
        chains.append(
            f"[0:a]atrim=start={start_sec:.3f}:end={end_sec:.3f},asetpts=PTS-STARTPTS[{a_label}]"
        )

    concat_inputs = "".join([f"{v}{a}" for v, a in zip(v_labels, a_labels)])
    chains.append(f"{concat_inputs}concat=n={len(segments)}:v=1:a=1[vout][aout]")
    return ";".join(chains)


def _run_checked(cmd: list[str], step: str) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        snippet = stderr[-1200:] if len(stderr) > 1200 else stderr
        raise PipelineRuntimeError(f"RENDER_{step.upper()}_FAILED: {snippet}")


def _probe_duration_ms(video_path: Path) -> int:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise fail("assemble", "RENDER_DURATION_PROBE_FAILED", (proc.stderr or "ffprobe failed").strip())
    value = (proc.stdout or "").strip()
    try:
        return int(round(float(value) * 1000.0))
    except Exception as exc:
        raise fail("assemble", "RENDER_DURATION_PARSE_FAILED", f"Invalid duration value: {value}") from exc


def _probe_has_audio_stream(video_path: Path) -> bool:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=codec_type",
        "-of",
        "csv=p=0",
        str(video_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return False
    out = (proc.stdout or "").strip().lower()
    return "audio" in out


def _sum_segment_durations_ms(segments: list[dict[str, Any]]) -> int:
    total = 0
    for seg in segments:
        start = to_ms(str(seg.get("source_start", "00:00:00.000")))
        end = to_ms(str(seg.get("source_end", "00:00:00.000")))
        total += max(0, end - start)
    return total


def _duration_match_score(actual_ms: int, expected_ms: int) -> float:
    if expected_ms <= 0:
        return 0.0
    diff = abs(actual_ms - expected_ms)
    score = 1.0 - (float(diff) / float(expected_ms))
    return max(0.0, min(1.0, score))


def _ts_to_seconds(timestamp: str) -> float:
    ms = to_ms(timestamp)
    return max(0.0, float(ms) / 1000.0)
