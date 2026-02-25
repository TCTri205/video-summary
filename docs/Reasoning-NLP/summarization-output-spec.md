# Summarization Output Spec

## Muc tieu

Chuan hoa output noi dung va output lap rap video de dam bao parse duoc, doi soat duoc, va replay duoc.

## Nguyen tac contract-first (bat buoc)

- Deliverable I/O cua toan he thong phai theo `contracts/v1/template/`.
- Cac truong mo rong chi duoc dat trong artifact noi bo, khong chen vao deliverable I/O.

Deliverable machine-checkable (duong dan thuc te trong repo):

- `contracts/v1/template/summary_script.schema.json`
- `contracts/v1/template/summary_video_manifest.schema.json`
- `contracts/v1/template/final_summary.schema.json` (neu co xuat)

Artifact noi bo Module 3 (khong phai I/O ban giao lien module):

- `context_blocks.json`
- `alignment_result.json`
- `quality_report.json`
- `summary_script.internal.json`
- `summary_video_manifest.internal.json` (neu can debug)

## Artifact lanes (de tranh nham)

Contract lane (deliverable):

- `summary_script.json`
- `summary_video_manifest.json`
- `summary_video.mp4`
- `final_summary.json` (optional, strict schema)

Reasoning lane (internal):

- `summary_script.internal.json` (noi luu `evidence`, `quality_flags`, `generation_meta`)
- `context_blocks.json`
- `alignment_result.json`
- `quality_report.json`

## Schema version

- Deliverable I/O theo global schema v1 trong `contracts/v1/template/`.
- Internal artifacts co `schema_version` rieng (de xuat `1.1`).

## Dinh dang output deliverable

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

`final_summary.json` (optional):

```json
{
  "plot_summary": "...",
  "moral_lesson": "...",
  "full_combined_context_used": "..."
}
```

## Dinh dang output internal (khuyen nghi)

`summary_script.internal.json` toi thieu phai co:

- `schema_version`
- `plot_summary`
- `moral_lesson`
- `evidence`
- `quality_flags`
- `generation_meta`
- `segments` (co `confidence`, `role`)

Validate bang `docs/Reasoning-NLP/schema/summary_script.internal.schema.json`.

## Mapping tu internal sang deliverable

- `summary_script.internal.plot_summary` -> `summary_script.plot_summary`
- `summary_script.internal.moral_lesson` -> `summary_script.moral_lesson`
- `summary_script.internal.segments[].script_text` -> `summary_script.segments[].script_text`
- `summary_script.internal.segments[].source_start/end` -> script + manifest

Khong map cac field noi bo sau vao deliverable:

- `evidence`
- `quality_flags`
- `generation_meta`
- `confidence`
- `role`

## Segment planning policy (bat buoc)

- Segment phai sap theo `segment_id` tang dan.
- Moi segment bat buoc thoa:
  - `min_segment_duration_ms >= 1200`
  - `max_segment_duration_ms <= 15000`
  - `source_end > source_start`
- Tong do dai summary phai nam trong budget:
  - `target_ratio` de xuat: `0.15` do dai video goc
  - `min_total_duration_ms` va `max_total_duration_ms` do he thong cau hinh
  - Neu bat threshold ratio: tong duration hop le khi nam trong `target_ratio +- target_ratio_tolerance` (de xuat tolerance `0.20`)

## Cross-file consistency checks

- Moi `segment_id` trong script phai unique.
- Moi `segment_id` trong manifest phai unique.
- Moi `script_ref` trong manifest phai ton tai trong `summary_script.segments.segment_id`.
- `source_start/source_end` cua script va manifest phai dong nhat theo tung segment.
- Tat ca timestamps phai nam trong `[0, source_video_duration]`.
- Segment timeline trong moi file phai khong overlap va giu thu tu tang dan theo thoi gian.

## Rule chat luong

- `plot_summary`: dung trinh tu su kien, ngan gon, co lien ket.
- `moral_lesson`: ro rang, lien quan truc tiep den noi dung.
- `segments`: map duoc vao video goc, khong overlap bat thuong.
- `summary_video.mp4`: duoc cat/ghep tu video goc va giu audio goc.

## Rule ky thuat

- File parse JSON hop le.
- Co du key bat buoc theo schema cho tung artifact.
- Gia tri string khong rong sau trim.
- Khong cho phep `NaN`, `null` cho cac field bat buoc.

## Input profile va normalize

- Pipeline chap nhan 2 profile transcript:
  - `strict_contract_v1` (uu tien)
  - `legacy_member1` (object + float giay)
- Truoc summarization, bat buoc normalize ve 1 canonical format noi bo.
- Bat buoc luu `input_profile` da dung trong `quality_report.json`.

## Chi so danh gia de xuat

- `parse_validity_rate`
- `timeline_consistency_score`
- `grounding_score`
- `compression_ratio`
- `manifest_consistency_pass`
- `no_match_rate`
- `median_confidence`
- `high_confidence_ratio`
