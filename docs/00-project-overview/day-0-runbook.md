# Day 0 Runbook (Demo thong luong)

Muc tieu: xac nhan kien truc chay thong tu input JSON den output tom tat ma khong sua logic khi doi mock -> data that.

## Buoc 1 - Chuan bi

- Mock data da co san:
  - `docs/00-project-overview/mock-data/audio_transcripts.json`
  - `docs/00-project-overview/mock-data/visual_captions.json`
- Xac nhan timestamp dang `HH:MM:SS.mmm`.

## Buoc 2 - Chay Module 3 voi mock

- Nhap 2 file mock.
- Merge theo timeline.
- Tao context hop nhat.
- Sinh `final_summary.json`.

## Buoc 3 - Validate truoc khi ket luan

- Validate schema cho 3 file dau vao/dau ra.
- Kiem tra output co du khoa:
  - `plot_summary`
  - `moral_lesson`
  - `full_combined_context_used`

## Buoc 4 - Chuyen sang data that

- Thay 2 file mock bang 2 file that tu Thanh vien 1.
- Chay lai y het pipeline Module 3.
- Neu pass khong can sua logic merge, Day 0 thanh cong.
