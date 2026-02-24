# Thanh vien 2 - Reasoning and NLP Lead

Ban phu trach Module 3 va chien luoc QLoRA.

## Input nhan tu Thanh vien 1

- `audio_transcripts.json`
- `visual_captions.json`

## Output ban giao

- `summary_script.json`
- `summary_video_manifest.json`
- `summary_video.mp4`
- (Giai doan fine-tune) LoRA adapter weights

## Rule tich hop

- Input phai pass schema v1.
- Timestamp su dung `HH:MM:SS.mmm`.
- Neu input fail schema, dung pipeline va bao loi ro nguyen nhan.
- Video summary phai duoc cat/ghep tu video goc va giu audio goc.
