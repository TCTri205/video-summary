# Video Summary Project

Du an tom tat video theo pipeline 3 module, phan tach ro trach nhiem de 2 thanh vien lam viec doc lap.

## Architecture

- Module 1: Data extraction (`raw_video.mp4` -> `audio_16k.wav`, `keyframes/`, `scene_metadata.json`)
- Module 2: Perception AI (`audio_16k.wav` + keyframes -> `audio_transcripts.json`, `visual_captions.json`)
- Module 3: Fusion and reasoning (2 JSON tren -> `final_summary.json`)

## Contract-first integration

- Data contracts nam tai `contracts/v1/`.
- Timestamp standard bat buoc: `HH:MM:SS.mmm`.
- Moi module chi can dung Input/Output schema de ghep noi chinh xac.

## Project docs

- `docs/00-project-overview/`
- `docs/01-member-1-perception-extraction/`
- `docs/02-member-2-reasoning-nlp/`

## Environment split

- Thanh vien 1: `requirements-member-1.txt`
- Thanh vien 2: `requirements-member-2.txt`

## Day 0 quick start

1. Thanh vien 2 dung mock data trong `docs/00-project-overview/mock-data/`.
2. Thanh vien 1 chay pipeline that de tao 2 JSON that.
3. Thay mock bang JSON that, chay lai Module 3 khong doi logic.
