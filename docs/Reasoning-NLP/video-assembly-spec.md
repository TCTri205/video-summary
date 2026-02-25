# Video Assembly Spec

## Muc tieu

Tao `summary_video.mp4` bang cach cat cac doan tu video goc va ghep lai theo thu tu script, dam bao playable va giu audio goc.

## Input bat buoc

- `raw_video.mp4`
- `summary_script.json`
- `summary_video_manifest.json`

## Pre-assembly checks (bat buoc)

- Manifest parse duoc va pass schema deliverable trong `contracts/v1/template/summary_video_manifest.schema.json`.
- Script parse duoc va pass `contracts/v1/template/summary_script.schema.json`.
- Cross-file consistency script-manifest da pass.
- Moi segment hop le: `source_end > source_start`, do dai trong nguong cho phep.
- Tat ca timestamps trong range video nguon.

Neu fail, dung stage voi `MANIFEST_*` hoac `RENDER_*`.

Luu y: `schema_version` chi ap dung cho artifact noi bo, khong bat buoc trong deliverable manifest global v1.

## Rule lap rap

- Cat theo tung segment `source_start` -> `source_end`.
- Ghep dung thu tu segment tang dan theo `segment_id`.
- Giu audio goc cua tung doan cat (`keep_original_audio = true`).
- Khong chen voice-over moi o pha MVP.
- Transition mac dinh: `cut`.

## Audio policy

- Giu nguyen track audio goc.
- Cho phep loudness smoothing nhe giua cac doan cat de giam nhay am luong (khong thay doi noi dung).

## Fallback rules

- Neu segment ngan hon `min_segment_duration_ms`, thu merge voi doan ke can de tranh flicker.
- Neu render loi profile chinh, retry 1 lan voi profile an toan (codec/container fallback da dinh nghia san).
- Neu van loi, dung pipeline va tra `RENDER_FATAL`.

Neu co merge segment do fallback:

1. Bat buoc cap nhat dong bo ca `summary_script.json` va `summary_video_manifest.json`.
2. Validate lai 2 file theo global contracts.
3. Chay lai cross-file consistency.
4. Chi render tiep khi cac check deu pass.

## Output

- `summary_video.mp4`
- Metadata render trong `quality_report.json` (`duration`, `codec`, `retry_count`, `warnings`)

## Post-assembly QC (bat buoc)

- Video playable, khong vo codec.
- Co am thanh va am thanh la am thanh goc tu video nguon.
- Noi dung video khop voi script segment theo timeline.
- Khong co spike frame den/dong bang bat thuong vuot nguong he thong.

## QC chi so de xuat

- `render_success` (bool)
- `audio_present` (bool)
- `duration_match_score`
- `black_frame_ratio`
- `decode_error_count`
