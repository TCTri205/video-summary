# Project Overview

## Muc tieu

Xay dung he thong tom tat video theo 3 module doc lap:
- Module 1: Data extraction (audio + keyframes + scene metadata).
- Module 2: Perception AI (speech-to-text + visual captioning).
- Module 3: Fusion and reasoning (alignment + summary + moral lesson).

Dau vao toan he thong: `raw_video.mp4`.
Dau ra cuoi: `final_summary.json`.

## Nguyen tac tich hop

- Moi module giao tiep qua file JSON theo data contract.
- Timestamp bat buoc theo dinh dang `HH:MM:SS.mmm`.
- Duong dan file trong JSON dung relative path.
- Neu sai schema thi fail som, khong cho chay tiep.

## Phan cong

- Thanh vien 1: Module 1 + 2, giao ra:
  - `audio_transcripts.json`
  - `visual_captions.json`
- Thanh vien 2: Module 3, nhan 2 file tren va giao ra:
  - `final_summary.json`

## Muc tieu MVP

- Chay thong luong end-to-end voi 1 video mau.
- 100% output dung schema v1 trong `contracts/v1/`.
- Co the thay mock data bang data that ma khong sua logic merge.
