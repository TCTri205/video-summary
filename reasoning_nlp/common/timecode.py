from __future__ import annotations

import re


TIMESTAMP_RE = re.compile(r"^\d{2}:[0-5]\d:[0-5]\d\.\d{3}$")


def to_ms(timestamp: str) -> int:
    if not isinstance(timestamp, str) or not TIMESTAMP_RE.match(timestamp):
        raise ValueError(f"Invalid timestamp format: {timestamp}")
    hh = int(timestamp[0:2])
    mm = int(timestamp[3:5])
    ss = int(timestamp[6:8])
    ms = int(timestamp[9:12])
    return (((hh * 60) + mm) * 60 + ss) * 1000 + ms


def ms_to_timestamp(value: int) -> str:
    if value < 0:
        raise ValueError("Milliseconds must be >= 0")
    hh = value // 3600000
    rem = value % 3600000
    mm = rem // 60000
    rem = rem % 60000
    ss = rem // 1000
    ms = rem % 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d}.{ms:03d}"


def seconds_to_timestamp(value: float) -> str:
    if value < 0:
        raise ValueError("Seconds must be >= 0")
    ms = int(round(value * 1000))
    return ms_to_timestamp(ms)
