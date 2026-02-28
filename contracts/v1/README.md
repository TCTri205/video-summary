# Contracts v1

Thu muc nay la nguon chuan de rang buoc Input/Output giua cac module.

## Timestamp standard

- Bat buoc dung dinh dang `HH:MM:SS.mmm`.
- Regex tham chieu: `^\d{2}:[0-5]\d:[0-5]\d\.\d{3}$`
- Vi du hop le: `00:00:01.000`, `12:34:56.789`

## Files

- `scene_metadata.schema.json`
- `audio_transcripts.schema.json`
- `visual_captions.schema.json`
- `summary_script.schema.json`
- `summary_video_manifest.schema.json`
- `final_summary.schema.json` (optional contract artifact)

Luu y runtime hien tai:

- Pipeline publish deliverable cuoi mac dinh: `summary_video.mp4` + `summary_text.txt`.
- `final_summary.json` la optional contract artifact, chi validate/xu ly khi duoc xuat bo sung.

## Examples

- `valid/`: du lieu hop le de test happy path.
- `invalid/`: du lieu sai de test fail-fast.

## Versioning

- `v1.x`: thay doi khong pha vo schema (backward compatible).
- `v2`: thay doi key/cau truc pha vo compatibility.
