from __future__ import annotations

from reasoning_nlp.common.types import AlignmentBlock


def build_context_blocks(alignment_blocks: list[AlignmentBlock]) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    for block in alignment_blocks:
        image_line = f"[Image @{block.timestamp}]: {block.image_text}"
        dialogue_line = f"[Dialogue]: {block.dialogue_text}"
        blocks.append(
            {
                "caption_id": block.caption_id,
                "timestamp": block.timestamp,
                "context_text": f"{image_line}\n{dialogue_line}",
                "image_text": block.image_text,
                "dialogue_text": block.dialogue_text,
                "matched_transcript_ids": block.matched_transcript_ids,
                "fallback_type": block.fallback_type,
                "confidence": block.confidence,
            }
        )
    return blocks
