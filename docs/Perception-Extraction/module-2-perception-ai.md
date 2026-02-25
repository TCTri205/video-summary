# Module 2 - Perception AI

## Nhiem vu

1. Chay Faster-Whisper (`distil-large-v3`) tren `audio_16k.wav`.
2. Sinh `audio_transcripts.json` theo schema v1.
3. Chay Moondream2 tren keyframes de sinh `visual_captions.json`.

## Rule timestamp

- `start`, `end`, `timestamp` deu theo `HH:MM:SS.mmm`.
- Transcript duoc sap xep tang dan theo `start`.
- Visual captions bat buoc sap xep tang dan theo `timestamp` (stable sort).
- Neu nhieu caption co cung `timestamp`, giu thu tu keyframe dau vao (stable).

## VRAM strategy (bat buoc)

1. Load Whisper.
2. Chay transcript va ghi JSON.
3. Giai phong model Whisper.
4. Goi `torch.cuda.empty_cache()`.
5. Load Moondream2 va caption keyframes.

## Prompt goi y cho Moondream2

"Mo ta ngan gon hanh dong chinh va bieu cam nhan vat trong anh. Neu co boi canh quan trong, neu trong 1 cau ngan."

## Tieu chi ban giao Module 2

- `audio_transcripts.json` pass schema.
- `visual_captions.json` pass schema.
- Du lieu khong rong, doc duoc, timestamp hop le.
- `visual_captions.json` co thu tu `timestamp` khong giam (non-decreasing).
