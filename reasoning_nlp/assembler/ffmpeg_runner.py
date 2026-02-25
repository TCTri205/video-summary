from __future__ import annotations

import subprocess
import tempfile
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
    with tempfile.TemporaryDirectory(prefix="rnlp_segments_", dir=str(output.parent)) as tmp_dir:
        tmp_path = Path(tmp_dir)
        clip_paths: list[Path] = []

        for idx, seg in enumerate(segments, start=1):
            start = str(seg.get("source_start", ""))
            end = str(seg.get("source_end", ""))
            clip = tmp_path / f"clip_{idx:04d}.mp4"
            clip_paths.append(clip)
            _cut_segment(source, clip, start, end, safe_profile=safe_profile)

        concat_file = tmp_path / "concat_list.txt"
        concat_file.write_text("".join([f"file '{_escape_concat_path(x)}'\n" for x in clip_paths]), encoding="utf-8")

        concat_cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
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


def _cut_segment(source: Path, clip: Path, start: str, end: str, safe_profile: bool) -> None:
    cut_cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        start,
        "-to",
        end,
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
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
        str(clip),
    ]
    _run_checked(cut_cmd, "cut")


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


def _escape_concat_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "'\\''")
