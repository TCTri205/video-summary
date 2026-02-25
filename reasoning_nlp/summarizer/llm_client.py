from __future__ import annotations

from collections import Counter


def generate_internal_summary(
    context_blocks: list[dict[str, object]],
    run_seed: int,
    model_version: str,
    tokenizer_version: str,
    temperature: float = 0.1,
) -> dict[str, object]:
    if not context_blocks:
        return {
            "schema_version": "1.1",
            "title": "Neutral Summary",
            "plot_summary": "Khong du du lieu de tao tom tat chi tiet.",
            "moral_lesson": "Hay dua tren bang chung ro rang truoc khi ket luan.",
            "evidence": [],
            "quality_flags": ["LLM_NEUTRAL_FALLBACK"],
            "generation_meta": {
                "model": model_version,
                "seed": run_seed,
                "temperature": temperature,
            },
        }

    timestamps = [str(x.get("timestamp", "")) for x in context_blocks if str(x.get("timestamp", ""))]
    dialogue_non_empty = [
        str(x.get("dialogue_text", "")).strip()
        for x in context_blocks
        if str(x.get("dialogue_text", "")).strip() and str(x.get("dialogue_text", "")).strip() != "(khong co)"
    ]
    image_non_empty = [
        str(x.get("image_text", "")).strip()
        for x in context_blocks
        if str(x.get("image_text", "")).strip() and str(x.get("image_text", "")).strip() != "(khong co)"
    ]

    sample_image = image_non_empty[0] if image_non_empty else "Khung hinh khong ro"
    sample_dialogue = dialogue_non_empty[0] if dialogue_non_empty else "(khong co)"

    fallback_counter = Counter(str(x.get("fallback_type", "")) for x in context_blocks)
    quality_flags: list[str] = []
    if fallback_counter.get("no_match", 0) > 0:
        quality_flags.append("ALIGN_HAS_NO_MATCH")

    evidence = []
    if timestamps:
        evidence.append(
            {
                "claim": "Tom tat dua tren cac moc canh/chu thich va hoi thoai da align.",
                "timestamps": sorted(set(timestamps))[:3],
            }
        )

    return {
        "schema_version": "1.1",
        "title": "Video Summary",
        "plot_summary": (
            "Noi dung cho thay dien bien theo thu tu thoi gian voi hinh anh chinh la "
            f"'{sample_image}' va hoi thoai noi bat la '{sample_dialogue}'."
        ),
        "moral_lesson": "Thong diep duoc rut ra tu cac su kien da xuat hien trong video.",
        "evidence": evidence,
        "quality_flags": quality_flags,
        "generation_meta": {
            "model": model_version,
            "seed": run_seed,
            "temperature": temperature,
        },
    }
