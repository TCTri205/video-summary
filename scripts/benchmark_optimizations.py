from __future__ import annotations

import json
import random
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from reasoning_nlp.aligner.matcher import match_captions
from reasoning_nlp.assembler.ffmpeg_runner import _render_with_profile
from reasoning_nlp.common.types import CanonicalCaption, CanonicalTranscript


def _match_captions_old(
    transcripts: list[CanonicalTranscript],
    captions: list[CanonicalCaption],
    delta_ms: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for caption in captions:
        t = caption.timestamp_ms
        candidates: list[tuple[int, int, int, int, CanonicalTranscript]] = []
        for tr in transcripts:
            in_range = tr.start_ms <= t <= tr.end_ms
            dist = min(abs(t - tr.start_ms), abs(t - tr.end_ms))
            if in_range:
                candidates.append((0, dist, tr.start_ms, tr.index, tr))
            elif dist <= delta_ms:
                candidates.append((1, dist, tr.start_ms, tr.index, tr))

        if not candidates:
            results.append(
                {
                    "transcript_ids": [],
                    "dialogue_text": "(khong co)",
                    "fallback_type": "no_match",
                    "distance_ms": delta_ms,
                    "match_type_rank": 2,
                }
            )
            continue

        best = sorted(candidates, key=lambda x: (x[0], x[1], x[2], x[3]))[0]
        _, dist, _, _, tr = best
        fallback = "containment" if best[0] == 0 else "nearest"
        results.append(
            {
                "transcript_ids": [tr.transcript_id],
                "dialogue_text": tr.text,
                "fallback_type": fallback,
                "distance_ms": dist,
                "match_type_rank": best[0],
            }
        )

    return results


def _to_ts(ms: int) -> str:
    hh = ms // 3600000
    rem = ms % 3600000
    mm = rem // 60000
    rem %= 60000
    ss = rem // 1000
    mmm = rem % 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d}.{mmm:03d}"


def _build_synthetic_data(transcript_count: int, caption_count: int) -> tuple[list[CanonicalTranscript], list[CanonicalCaption]]:
    transcripts: list[CanonicalTranscript] = []
    for i in range(transcript_count):
        start_ms = i * 2500
        end_ms = start_ms + 1800
        transcripts.append(
            CanonicalTranscript(
                transcript_id=f"t_{i:05d}",
                start=_to_ts(start_ms),
                end=_to_ts(end_ms),
                start_ms=start_ms,
                end_ms=end_ms,
                text=f"text {i}",
                index=i,
                is_empty_text=False,
            )
        )

    rng = random.Random(42)
    max_ts = max(1, transcripts[-1].end_ms + 1000)
    captions: list[CanonicalCaption] = []
    for i in range(caption_count):
        ts_ms = rng.randint(0, max_ts)
        captions.append(
            CanonicalCaption(
                caption_id=f"c_{i:05d}",
                timestamp=_to_ts(ts_ms),
                timestamp_ms=ts_ms,
                caption=f"cap {i}",
                index=i,
                is_empty_text=False,
            )
        )
    return transcripts, captions


def benchmark_matcher() -> dict[str, Any]:
    transcripts, captions = _build_synthetic_data(10000, 10000)
    delta_ms = 2000

    # correctness check
    old_results = _match_captions_old(transcripts, captions, delta_ms)
    new_results = match_captions(transcripts, captions, delta_ms)
    parity = True
    for old, new in zip(old_results, new_results):
        if (
            old["transcript_ids"] != new.transcript_ids
            or old["dialogue_text"] != new.dialogue_text
            or old["fallback_type"] != new.fallback_type
            or old["distance_ms"] != new.distance_ms
            or old["match_type_rank"] != new.match_type_rank
        ):
            parity = False
            break

    # timed runs
    t0 = time.perf_counter()
    _match_captions_old(transcripts, captions, delta_ms)
    old_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    match_captions(transcripts, captions, delta_ms)
    new_ms = (time.perf_counter() - t1) * 1000

    return {
        "parity": parity,
        "old_ms": round(old_ms, 2),
        "new_ms": round(new_ms, 2),
        "speedup_x": round(old_ms / new_ms, 2) if new_ms > 0 else None,
    }


def _run_checked(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "command failed").strip())


def _make_test_video(path: Path, duration_s: int = 40) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=size=640x360:rate=24:duration={duration_s}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:sample_rate=48000:duration={duration_s}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(path),
    ]
    _run_checked(cmd)


def _render_old_style(source: Path, output: Path, segments: list[dict[str, Any]]) -> None:
    with tempfile.TemporaryDirectory(prefix="bench_segments_", dir=str(output.parent)) as tmp_dir:
        tmp_path = Path(tmp_dir)
        clip_paths: list[Path] = []
        for idx, seg in enumerate(segments, start=1):
            clip = tmp_path / f"clip_{idx:04d}.mp4"
            clip_paths.append(clip)
            cut_cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(seg["source_start"]),
                "-to",
                str(seg["source_end"]),
                "-i",
                str(source),
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                str(clip),
            ]
            _run_checked(cut_cmd)

        concat_file = tmp_path / "concat_list.txt"
        concat_lines = []
        for p in clip_paths:
            escaped = p.resolve().as_posix().replace("'", "'\\''")
            concat_lines.append(f"file '{escaped}'\n")
        concat_file.write_text("".join(concat_lines), encoding="utf-8")
        concat_cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(output),
        ]
        _run_checked(concat_cmd)


def benchmark_assemble() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "raw.mp4"
        old_output = root / "old.mp4"
        new_output = root / "new.mp4"
        _make_test_video(source, duration_s=40)

        segments = []
        # 12 segments x 2.5s
        for i in range(12):
            start_ms = i * 3000
            end_ms = start_ms + 2500
            segments.append(
                {
                    "segment_id": i + 1,
                    "source_start": _to_ts(start_ms),
                    "source_end": _to_ts(end_ms),
                }
            )

        t0 = time.perf_counter()
        _render_old_style(source, old_output, segments)
        old_ms = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        _render_with_profile(source, new_output, segments, safe_profile=False)
        new_ms = (time.perf_counter() - t1) * 1000

        return {
            "old_ms": round(old_ms, 2),
            "new_ms": round(new_ms, 2),
            "speedup_x": round(old_ms / new_ms, 2) if new_ms > 0 else None,
            "old_size_bytes": old_output.stat().st_size if old_output.exists() else 0,
            "new_size_bytes": new_output.stat().st_size if new_output.exists() else 0,
        }


def benchmark_caption_batch() -> dict[str, Any]:
    try:
        from PIL import Image
        from extraction_perception.perception.caption import VisualCaptioner
    except Exception as exc:
        return {"status": "skipped", "reason": str(exc)}

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        frames_dir = root / "keyframes"
        frames_dir.mkdir(parents=True, exist_ok=True)
        metadata = {"total_keyframes": 8, "frames": []}
        for i in range(8):
            ts_ms = i * 1000
            name = f"frame_{i:03d}.jpg"
            path = frames_dir / name
            img = Image.new("RGB", (224, 224), color=(10 * i, 30, 120))
            img.save(path)
            metadata["frames"].append(
                {
                    "frame_id": i + 1,
                    "timestamp": _to_ts(ts_ms),
                    "file_path": f"keyframes/{name}",
                }
            )

        metadata_path = root / "scene_metadata.json"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        out1 = root / "captions_bs1.json"
        outb = root / "captions_bsx.json"

        try:
            cap = VisualCaptioner()
        except Exception as exc:
            return {"status": "skipped", "reason": f"model init failed: {exc}"}

        t0 = time.perf_counter()
        cap.caption_from_metadata(str(metadata_path), str(out1), batch_size=1)
        s1 = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        cap.caption_from_metadata(str(metadata_path), str(outb), batch_size=cap.default_batch_size)
        sb = (time.perf_counter() - t1) * 1000

        return {
            "status": "ok",
            "batch_size": cap.default_batch_size,
            "single_ms": round(s1, 2),
            "batch_ms": round(sb, 2),
            "speedup_x": round(s1 / sb, 2) if sb > 0 else None,
        }


def main() -> int:
    report = {
        "matcher": benchmark_matcher(),
        "assembler": benchmark_assemble(),
        "caption": benchmark_caption_batch(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
