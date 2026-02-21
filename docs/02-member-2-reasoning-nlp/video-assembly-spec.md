# Video Assembly Spec

## Muc tieu

Tao `summary_video.mp4` bang cach cat cac doan tu video goc va ghep lai theo thu tu script.

## Input bat buoc

- `raw_video.mp4`
- `summary_script.json`
- `summary_video_manifest.json`

## Rule lap rap

- Cat theo tung segment `source_start` -> `source_end`.
- Ghep dung thu tu segment tang dan theo `segment_id`.
- Giu audio goc cua tung doan cat (`keep_original_audio = true`).
- Khong chen voiceover moi o pha MVP.

## Output

- `summary_video.mp4`

## Kiem tra nhanh

- Video phat duoc, khong vo codec.
- Co am thanh va am thanh la am thanh goc tu video nguon.
- Noi dung video khop voi script segment.
