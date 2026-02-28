from __future__ import annotations


def build_summary_prompt(context_blocks: list[dict[str, object]], max_chars: int | None = None) -> str:
    items = _extract_items(context_blocks)
    lines = [x[0] for x in items]
    if max_chars is None or int(max_chars) <= 0:
        return "\n\n".join(lines)

    budget = int(max_chars)
    if budget <= 0 or not lines:
        return ""

    selected = _select_with_balanced_coverage(lines, items, budget)
    return "\n\n".join(selected)


def _extract_items(context_blocks: list[dict[str, object]]) -> list[tuple[str, float]]:
    items: list[tuple[str, float]] = []
    for idx, block in enumerate(context_blocks):
        text = _render_context_block(block, idx)
        if text:
            items.append((text, _to_float(block.get("confidence", 0.0))))
    return items


def _render_context_block(block: dict[str, object], idx: int) -> str:
    timestamp = _normalize_text(str(block.get("timestamp", "")).strip())
    image_text = _normalize_text(str(block.get("image_text", "")).strip())
    dialogue_text = _normalize_text(str(block.get("dialogue_text", "")).strip())
    confidence = _to_float(block.get("confidence", 0.0))

    has_structured_fields = bool(timestamp or image_text or dialogue_text)
    if not has_structured_fields:
        context_text = _normalize_text(str(block.get("context_text", "")).strip())
        return context_text

    lines = [f"[Block {idx + 1}]"]
    if timestamp:
        lines.append(f"timestamp={timestamp}")
    if image_text:
        lines.append(f"image_text={image_text}")
    if dialogue_text:
        lines.append(f"dialogue_text={dialogue_text}")
    lines.append(f"confidence={confidence:.3f}")
    return "\n".join(lines).strip()


def _select_with_balanced_coverage(
    lines: list[str],
    items: list[tuple[str, float]],
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


def _confidence_at(items: list[tuple[str, float]], idx: int) -> float:
    if idx < 0 or idx >= len(items):
        return 0.0
    return float(items[idx][1])


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _normalize_text(text: str) -> str:
    return " ".join(text.split())
