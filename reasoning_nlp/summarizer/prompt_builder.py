from __future__ import annotations


def build_summary_prompt(context_blocks: list[dict[str, object]]) -> str:
    lines: list[str] = []
    for block in context_blocks:
        text = str(block.get("context_text", "")).strip()
        if text:
            lines.append(text)
    return "\n\n".join(lines)
