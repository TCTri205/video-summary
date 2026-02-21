# Troubleshooting

## 1) OOM khi doi model

Trieu chung:
- CUDA out of memory khi load Moondream2 sau Whisper.

Huong xu ly:
- Xoa tham chieu model Whisper.
- Goi `torch.cuda.empty_cache()`.
- Giam batch size caption.
- Neu can, dung precision thap hon.

## 2) Qua nhieu keyframe

Trieu chung:
- `keyframes/` qua day, gay ton thoi gian caption.

Huong xu ly:
- Tang `threshold`.
- Tang `min_scene_len`.
- Chi lay 1 frame dai dien moi scene.

## 3) Sot canh

Trieu chung:
- Mat canh quan trong trong metadata.

Huong xu ly:
- Giam nhe `threshold`.
- Giam `min_scene_len`.
- Kiem tra fps va dieu chinh theo fps video.

## 4) Timestamp khong chuan

Trieu chung:
- Output bi fail schema do thieu milliseconds.

Huong xu ly:
- Chuan hoa tat ca moc thoi gian ve `HH:MM:SS.mmm` truoc khi ghi JSON.
