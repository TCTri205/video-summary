from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from typing import Iterable

_VI_STOPWORDS = {
    "a",
    "ai",
    "anh",
    "ay",
    "ba",
    "bao",
    "bay",
    "bi",
    "biet",
    "boi",
    "cac",
    "cai",
    "can",
    "cang",
    "chi",
    "chinh",
    "cho",
    "chu",
    "chua",
    "chuyen",
    "co",
    "con",
    "cua",
    "cung",
    "cung_nhu",
    "da",
    "dang",
    "de",
    "den",
    "di",
    "do",
    "duoc",
    "gi",
    "gio",
    "giu",
    "gom",
    "hay",
    "het",
    "hon",
    "khi",
    "khong",
    "lam",
    "lan",
    "la",
    "lai",
    "len",
    "luc",
    "ma",
    "mang",
    "minh",
    "mot",
    "neu",
    "ngay",
    "ngoai",
    "nhieu",
    "nhung",
    "nho",
    "noi",
    "o",
    "qua",
    "ra",
    "rang",
    "roi",
    "rang",
    "sau",
    "se",
    "tai",
    "the",
    "thi",
    "thoi",
    "thu",
    "tren",
    "trong",
    "tu",
    "ve",
    "voi",
    "vua",
    "vi",
    "vay",
    "va",
}

_CTA_TOKENS = {"like", "comment", "subscribe", "dang", "ky", "ki"}


def compute_lexical_salience_scores(
    context_blocks: list[dict[str, object]],
    *,
    enabled: bool,
    weight: float,
    min_df: int,
    min_token_len: int,
    use_idf: bool,
    stopwords_profile: str,
) -> list[float]:
    if not enabled or weight <= 0.0 or not context_blocks:
        return [0.0 for _ in context_blocks]
    if str(stopwords_profile).strip().lower() != "vi":
        return [0.0 for _ in context_blocks]

    tokenized_docs = [_extract_tokens(block, min_token_len=max(1, int(min_token_len))) for block in context_blocks]
    if not any(tokenized_docs):
        return [0.0 for _ in context_blocks]

    doc_freq = Counter()
    for tokens in tokenized_docs:
        for token in set(tokens):
            doc_freq[token] += 1

    total_docs = len(tokenized_docs)
    effective_min_df = max(1, int(min_df))
    raw_scores: list[float] = []
    for tokens in tokenized_docs:
        if not tokens:
            raw_scores.append(0.0)
            continue
        tf = Counter(tokens)
        score = 0.0
        for token, freq in tf.items():
            df = int(doc_freq.get(token, 0))
            if df < effective_min_df:
                continue
            if use_idf:
                idf = math.log((1.0 + total_docs) / (1.0 + df)) + 1.0
            else:
                idf = 1.0
            score += float(freq) * float(idf)
        raw_scores.append(score)

    return _normalize_scores(raw_scores)


def _extract_tokens(block: dict[str, object], *, min_token_len: int) -> list[str]:
    text = " ".join(
        [
            str(block.get("dialogue_text", "")).strip(),
            str(block.get("image_text", "")).strip(),
        ]
    ).strip()
    if not text:
        return []

    out: list[str] = []
    for raw in _tokenize(text):
        token = raw.strip().lower()
        if len(token) < min_token_len:
            continue
        if token.isdigit():
            continue
        ascii_token = _ascii_fold(token)
        if not ascii_token:
            continue
        if ascii_token in _CTA_TOKENS:
            continue
        if ascii_token in _VI_STOPWORDS:
            continue
        out.append(ascii_token)
    return out


def _tokenize(text: str) -> Iterable[str]:
    return re.findall(r"\b\w+\b", str(text).lower(), flags=re.UNICODE)


def _ascii_fold(value: str) -> str:
    folded = unicodedata.normalize("NFD", value)
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    folded = folded.replace("đ", "d").replace("Đ", "d")
    return folded.strip().lower()


def _normalize_scores(values: list[float]) -> list[float]:
    if not values:
        return []
    high = max(values)
    low = min(values)
    if high <= 0.0 or math.isclose(high, low):
        return [0.0 for _ in values]
    span = high - low
    return [max(0.0, min(1.0, (value - low) / span)) for value in values]
