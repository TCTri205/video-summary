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
- Runtime hien tai giu audio goc theo cut/concat, chua ap dung loudness smoothing rieng.

## Fallback rules

- Runtime hien tai retry 1 lan voi safe render profile khi profile chinh fail.
- Runtime hien tai KHONG tu dong merge segment trong stage assemble.
- Neu van loi sau retry, dung pipeline va tra `RENDER_FATAL`.

## Output

- `summary_video.mp4`
- Render metadata ky thuat duoc ghi trong `artifacts/<run_id>/g7_assemble/render_meta.json` (vi du: `duration_ms`, `expected_duration_ms`, `duration_match_score`, `retry_count`, `output_video_path`)
- `quality_report.json` chi tong hop cac metric QC lien quan den render nhu `render_success`, `audio_present`, `duration_match_score`, `black_frame_ratio`, `decode_error_count`

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
