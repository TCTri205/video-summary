# Integration Protocol

Muc tieu: 2 thanh vien lam song song, ghep noi chi qua JSON, khong phu thuoc code noi bo cua nhau.

## Contract-first workflow

1. Chot schema trong `contracts/v1/`.
2. Thanh vien 1 va 2 cung phat trien dua tren contract do.
3. Moi output deu phai validate schema truoc khi ban giao.

## Day 0 flow

- Thanh vien 2 tao mock data theo schema v1:
  - `audio_transcripts.json`
  - `visual_captions.json`
- Thanh vien 2 code merge + tao `summary_script.json` + tao manifest cat/ghep video.
- Thanh vien 1 xay pipeline that cho Module 1 + 2.

Khi co data that:
1. Thay mock data bang data that (giu nguyen ten file va schema).
2. Validate schema.
3. Chay Module 3 de tao `summary_script.json` va `summary_video_manifest.json`.
4. Render `summary_video.mp4` tu manifest, giu audio goc cua tung doan cat.

## Rule de ghep chinh xac

- Timestamp chung dinh dang `HH:MM:SS.mmm`.
- JSON key name khong duoc thay doi.
- Relative path trong JSON phai dung workspace root.
- Sai schema => fail ngay.
- `keep_original_audio` trong manifest phai la `true`.
