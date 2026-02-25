from __future__ import annotations

from reasoning_nlp.common.timecode import to_ms


def check_strict_increasing_segment_ids(segments: list[dict]) -> list[str]:
    errors: list[str] = []
    prev = None
    for idx, seg in enumerate(segments):
        seg_id = seg.get("segment_id")
        if not isinstance(seg_id, int):
            errors.append(f"segment index {idx}: segment_id must be integer")
            continue
        if prev is not None and seg_id <= prev:
            errors.append("segment_id must be strictly increasing")
        prev = seg_id
    return errors


def check_unique_segment_ids(segments: list[dict], label: str) -> list[str]:
    errors: list[str] = []
    seen: set[int] = set()
    for idx, seg in enumerate(segments):
        seg_id = seg.get("segment_id")
        if not isinstance(seg_id, int):
            errors.append(f"{label}[{idx}] segment_id must be integer")
            continue
        if seg_id in seen:
            errors.append(f"{label}[{idx}] duplicate segment_id={seg_id}")
        seen.add(seg_id)
    return errors


def check_time_order_and_overlap(segments: list[dict], label: str) -> list[str]:
    errors: list[str] = []
    prev_start = None
    prev_end = None
    prev_id = None
    for idx, seg in enumerate(segments):
        try:
            start = to_ms(str(seg.get("source_start")))
            end = to_ms(str(seg.get("source_end")))
        except Exception:
            errors.append(f"{label}[{idx}] invalid source_start/source_end")
            continue
        if end <= start:
            errors.append(f"{label}[{idx}] source_end must be > source_start")
        if prev_start is not None and start < prev_start:
            errors.append(f"{label}[{idx}] timeline must be non-decreasing")
        if prev_end is not None and start < prev_end:
            errors.append(f"{label}[{idx}] overlaps previous segment_id={prev_id}")
        prev_start = start
        prev_end = end
        prev_id = seg.get("segment_id")
    return errors


def check_script_manifest_consistency(
    script_payload: dict,
    manifest_payload: dict,
    source_duration_ms: int | None,
) -> list[str]:
    errors: list[str] = []
    script_segments = script_payload.get("segments", [])
    manifest_segments = manifest_payload.get("segments", [])
    if not isinstance(script_segments, list) or not isinstance(manifest_segments, list):
        return ["script/manifest segments must be arrays"]

    errors.extend(check_unique_segment_ids(script_segments, "script"))
    errors.extend(check_unique_segment_ids(manifest_segments, "manifest"))
    errors.extend(check_strict_increasing_segment_ids(script_segments))
    errors.extend(check_strict_increasing_segment_ids(manifest_segments))
    errors.extend(check_time_order_and_overlap(script_segments, "script"))
    errors.extend(check_time_order_and_overlap(manifest_segments, "manifest"))

    script_by_id = {seg.get("segment_id"): seg for seg in script_segments if isinstance(seg.get("segment_id"), int)}
    for idx, m_seg in enumerate(manifest_segments):
        ref = m_seg.get("script_ref")
        if ref not in script_by_id:
            errors.append(f"manifest[{idx}] script_ref={ref} not found")
            continue
        s_seg = script_by_id[ref]
        if m_seg.get("source_start") != s_seg.get("source_start") or m_seg.get("source_end") != s_seg.get("source_end"):
            errors.append(f"manifest[{idx}] timestamps mismatch with script_ref={ref}")

        if source_duration_ms is not None:
            try:
                start = to_ms(str(m_seg.get("source_start")))
                end = to_ms(str(m_seg.get("source_end")))
            except Exception:
                errors.append(f"manifest[{idx}] invalid timestamp range")
                continue
            if start < 0 or end > source_duration_ms:
                errors.append(f"manifest[{idx}] out of source duration range 0..{source_duration_ms}")

    return errors
