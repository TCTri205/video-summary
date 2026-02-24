# Thanh vien 1 - Perception and Extraction Lead

Ban phu trach Module 1 + Module 2 trong mot luong thong nhat.

## Input

- `raw_video.mp4`

## Output ban giao (bat buoc)

- `audio_transcripts.json`
- `visual_captions.json`

## Output trung gian

- `audio_16k.wav`
- `keyframes/*.jpg`
- `scene_metadata.json`

## Rule chat luong

- Timestamp tat ca output theo `HH:MM:SS.mmm`.
- Output phai pass schema trong `contracts/v1/`.
- Neu output khong pass schema thi khong ban giao.
