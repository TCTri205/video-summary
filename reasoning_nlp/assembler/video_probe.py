from __future__ import annotations

import subprocess
from pathlib import Path

from reasoning_nlp.common.errors import fail


def probe_source_duration_ms(raw_video_path: str) -> int:
    path = Path(raw_video_path)
    if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
        raise fail("validate", "TIME_SOURCE_VIDEO_INVALID", f"Invalid source video: {raw_video_path}")

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
        msg = (proc.stderr or "ffprobe failed").strip()
        raise fail("validate", "TIME_SOURCE_VIDEO_INVALID", msg)

    raw = (proc.stdout or "").strip()
    try:
        duration_ms = int(round(float(raw) * 1000.0))
    except Exception as exc:
        raise fail("validate", "TIME_SOURCE_VIDEO_INVALID", f"Invalid duration value: {raw}") from exc

    if duration_ms <= 0:
        raise fail("validate", "TIME_SOURCE_VIDEO_INVALID", f"Source duration must be > 0, got {duration_ms}")
    return duration_ms
