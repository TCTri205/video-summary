from __future__ import annotations


def build_summary_prompt(context_blocks: list[dict[str, object]], max_chars: int | None = None) -> str:
    items = _extract_items(context_blocks)
    lines = [x["text"] for x in items]
    if max_chars is None or int(max_chars) <= 0:
        return "\n\n".join(lines)

    budget = int(max_chars)
    if budget <= 0 or not lines:
        return ""

    selected = _select_with_balanced_coverage(lines, items, budget)
    return "\n\n".join(selected)


def _extract_items(context_blocks: list[dict[str, object]]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for block in context_blocks:
        text = str(block.get("context_text", "")).strip()
        if text:
            items.append({"text": text, "confidence": _to_float(block.get("confidence", 0.0))})
    return items


def _select_with_balanced_coverage(
    lines: list[str],
    items: list[dict[str, object]],
    budget: int,
) -> list[str]:
    separators = 2
    total = len(lines)
    if total == 0:
        return []

    anchors = []
    for idx in (0, total // 2, total - 1):
        if 0 <= idx < total and idx not in anchors:
            anchors.append(idx)

    candidate_indexes = list(range(total))
    candidate_indexes.sort(
        key=lambda i: (
            -_confidence_at(items, i),
            i,
        )
    )

    ordered_indexes: list[int] = []
    seen: set[int] = set()
    for idx in anchors + candidate_indexes:
        if idx not in seen:
            seen.add(idx)
            ordered_indexes.append(idx)

    selected_idx: list[int] = []
    used = 0
    for idx in ordered_indexes:
        text = lines[idx]
        extra = len(text)
        if selected_idx:
            extra += separators
        if selected_idx and used + extra > budget:
            continue
        if not selected_idx and extra > budget:
            selected_idx.append(idx)
            break
        selected_idx.append(idx)
        used += extra

    if not selected_idx:
        return []
    selected_idx.sort()
    return [lines[i] for i in selected_idx]


def _confidence_at(items: list[dict[str, object]], idx: int) -> float:
    if idx < 0 or idx >= len(items):
        return 0.0
    return _to_float(items[idx].get("confidence", 0.0))


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0
