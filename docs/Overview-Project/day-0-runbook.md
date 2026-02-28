# Day 0 Runbook (Demo thong luong)

Muc tieu: xac nhan kien truc chay thong tu input JSON den output tom tat ma khong sua logic khi doi mock -> data that.

## Buoc 1 - Chuan bi

- Mock data da co san:
- `Data/mock/audio_transcripts.json`
- `Data/mock/visual_captions.json`
- Xac nhan timestamp dang `HH:MM:SS.mmm`.

## Buoc 2 - Chay Module 3 voi mock

- Nhap 2 file mock.
- Merge theo timeline.
- Tao context hop nhat.
- Sinh `summary_script.json`.
- Sinh `summary_video_manifest.json`.
- Render `summary_video.mp4` (cat/ghep tu video goc, giu audio goc).

## Buoc 3 - Validate truoc khi ket luan

- Validate schema cho output:
  - `summary_script.json`
  - `summary_video_manifest.json`
- Kiem tra `keep_original_audio = true`.
- Kiem tra `summary_video.mp4` phat duoc, co audio.

## Buoc 4 - Chuyen sang data that

- Thay 2 file mock bang 2 file that tu Thanh vien 1.
- Chay lai y het pipeline Module 3.
- Neu pass khong can sua logic merge, Day 0 thanh cong.
