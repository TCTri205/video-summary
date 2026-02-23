# Summarization Output Spec

## Muc tieu

Chuan hoa output noi dung va output lap rap video de dam bao parse duoc, doi soat duoc, va replay duoc.

## Nguyen tac contract-first (bat buoc)

- Deliverable I/O cua toan he thong phai theo `contracts/v1/`.
- Cac truong mo rong chi duoc dat trong artifact noi bo, khong chen vao deliverable I/O.

Deliverable machine-checkable:

- `contracts/v1/summary_script.schema.json`
- `contracts/v1/summary_video_manifest.schema.json`

Artifact noi bo Module 3 (khong phai I/O ban giao lien module):

- `alignment_result.json`
- `quality_report.json`
- `final_summary.json` hoac artifact infer noi bo khac

## Schema version

- Deliverable I/O (`summary_script.json`, `summary_video_manifest.json`) theo schema v1 trong `contracts/v1`.
- Artifact noi bo Module 3 co the dung `schema_version` rieng (de xuat `1.1`).

## Dinh dang output

`summary_script.json`:

```json
{
  "title": "...",
  "plot_summary": "...",
  "moral_lesson": "...",
  "segments": [
    {
      "segment_id": 1,
      "source_start": "00:00:06.000",
      "source_end": "00:00:13.200",
      "script_text": "..."
    }
  ]
}
```

`summary_video_manifest.json`:

```json
{
  "source_video_path": "raw_video.mp4",
  "output_video_path": "summary_video.mp4",
  "keep_original_audio": true,
  "segments": [
    {
      "segment_id": 1,
      "source_start": "00:00:06.000",
      "source_end": "00:00:13.200",
      "script_ref": 1,
      "transition": "cut"
    }
  ]
}
```

## Segment planning policy (bat buoc)

- Segment phai duoc sap theo `segment_id` tang dan.
- Moi segment bat buoc thoa:
  - `min_segment_duration_ms >= 1200`
  - `max_segment_duration_ms <= 15000`
  - `source_end > source_start`
- Tong do dai summary phai nam trong budget:
  - `target_ratio` de xuat: `0.15` do dai video goc
  - `min_total_duration_ms` va `max_total_duration_ms` do he thong cau hinh.

Luu y: `role`, `confidence` la metadata noi bo, khong chen vao `summary_script.json` deliverable.

## Cross-file consistency checks

- Moi `segment_id` trong script phai unique.
- Moi `segment_id` trong manifest phai unique.
- Moi `script_ref` trong manifest phai ton tai trong `summary_script.segments.segment_id`.
- `source_start/source_end` cua script va manifest phai dong nhat theo tung segment.
- Tat ca timestamps phai nam trong [0, source_video_duration].

## Rule chat luong

- `plot_summary`: dung trinh tu su kien, ngan gon, co lien ket.
- `moral_lesson`: ro rang, lien quan truc tiep den noi dung.
- `segments`: map duoc vao video goc, khong overlap bat thuong.
- `summary_video.mp4`: duoc cat/ghep tu video goc va giu audio goc.

## Rule ky thuat

- File parse JSON hop le.
- Co du key bat buoc theo schema trong `contracts/v1` cho `summary_script` va `summary_video_manifest`.
- Gia tri string khong rong sau khi trim.
- Khong cho phep `NaN`, `null` cho cac field bat buoc.

## Chi so danh gia de xuat

- `parse_validity_rate`
- `timeline_consistency_score`
- `grounding_score`
- `compression_ratio`
- `manifest_consistency_pass`
