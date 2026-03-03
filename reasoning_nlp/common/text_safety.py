from __future__ import annotations

import re


CTA_PATTERNS = [
    re.compile(r"\blike\b", re.IGNORECASE),
    re.compile(r"\bcomment\b", re.IGNORECASE),
    re.compile(r"\bsubscribe\b", re.IGNORECASE),
    re.compile(r"\bdang\s*ky\b", re.IGNORECASE),
    re.compile(r"\bdang\s*ki\b", re.IGNORECASE),
]


def looks_like_cta(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return False
    return any(pattern.search(lowered) for pattern in CTA_PATTERNS)
