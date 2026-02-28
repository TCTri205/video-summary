from __future__ import annotations

import re


_BLOCK_PATTERNS = [
    re.compile(r"<system-reminder>.*?</system-reminder>", re.IGNORECASE | re.DOTALL),
]

_HARD_SINGLE_MARKERS = (
    "<system-reminder>",
    "</system-reminder>",
)

_HARD_COMBINATION_MARKERS = (
    "plan mode",
    "read-only phase",
    "strictly forbidden",
    "overrides all other instructions",
    "you may only observe",
    "the user indicated that they do not want you to execute yet",
)

_SOFT_MARKERS = (
    "critical:",
    "system reminder",
    "do not use",
    "responsibility",
    "direct user edit requests",
)


def contains_hard_prompt_leakage(text: str) -> bool:
    normalized = _normalize(text)
    if not normalized:
        return False
    if any(marker in normalized for marker in _HARD_SINGLE_MARKERS):
        return True
    hits = sum(1 for marker in _HARD_COMBINATION_MARKERS if marker in normalized)
    return hits >= 2


def contains_soft_prompt_leakage(text: str) -> bool:
    normalized = _normalize(text)
    if not normalized:
        return False
    if contains_hard_prompt_leakage(normalized):
        return True
    return any(marker in normalized for marker in _SOFT_MARKERS)


def summarize_leakage_hits(text: str) -> list[str]:
    normalized = _normalize(text)
    if not normalized:
        return []
    hits: list[str] = []
    for marker in _HARD_SINGLE_MARKERS + _HARD_COMBINATION_MARKERS + _SOFT_MARKERS:
        if marker in normalized and marker not in hits:
            hits.append(marker)
    return hits


def scrub_llm_generated_text(text: str) -> tuple[str, bool]:
    original = str(text or "")
    cleaned = original
    for pattern in _BLOCK_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    if contains_hard_prompt_leakage(cleaned):
        kept_lines = []
        for raw_line in cleaned.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if contains_hard_prompt_leakage(line):
                continue
            kept_lines.append(line)
        cleaned = " ".join(kept_lines)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, cleaned != original.strip()


def is_raw_text_unsafe_for_script(text: str) -> bool:
    return contains_hard_prompt_leakage(text)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()
