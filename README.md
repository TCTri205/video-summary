# Video Summary Project

Du an tom tat video theo pipeline 3 module, phan tach ro trach nhiem de 2 thanh vien lam viec doc lap.

## Requirements
- Python 3.8+
- FFmpeg:
  + https://www.gyan.dev/ffmpeg/builds/
  + Chọn bản ffmpeg-release-essentials.zip
  + Giải nén, thêm thư mục `bin/` vào PATH của hệ thống.


## Architecture

- Module 1: Data extraction (`raw_video.mp4` -> `audio_16k.wav`, `keyframes/`, `scene_metadata.json`)
- Module 2: Perception AI (`audio_16k.wav` + keyframes -> `audio_transcripts.json`, `visual_captions.json`)
- Module 3: Fusion, reasoning, and assembly (`audio_transcripts.json` + `visual_captions.json` -> `summary_script.json` + `summary_video_manifest.json` -> `summary_video.mp4`)

## Final deliverables

- `summary_script.json` (script tom tat chuan may doc)
- `summary_video.mp4` (cat + ghep tu video goc, giu audio goc)

Ghi chu: `final_summary.json` chi la artifact noi bo (optional) de debug/fine-tune, khong phai deliverable cuoi.

## Contract-first integration

- Data contracts nam tai `contracts/v1/`.
- Timestamp standard bat buoc: `HH:MM:SS.mmm`.
- Moi module chi can dung Input/Output schema de ghep noi chinh xac.
- Video assembly theo manifest, giu audio goc cua doan cat (`keep_original_audio: true`).

## Project docs

- `docs/00-project-overview/`
- `docs/01-member-1-perception-extraction/`
- `docs/02-member-2-reasoning-nlp/`

## Environment split

- Thanh vien 1: `requirements-1.txt`
- Thanh vien 2: `requirements-2.txt`

## Day 0 quick start

1. Thanh vien 2 dung mock data trong `docs/Overview-Project/mock-data/`.
2. Thanh vien 1 chay pipeline that de tao 2 JSON that.
3. Thay mock bang JSON that, chay lai Module 3 khong doi logic.
