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

Ghi chu: `final_summary.json` la artifact optional theo global contract (khong phai deliverable media chinh), co the dung cho debug/fine-tune va nghiem thu schema.

## Contract-first integration

- Data contracts nam tai `contracts/v1/`.
- Timestamp standard bat buoc: `HH:MM:SS.mmm`.
- Moi module chi can dung Input/Output schema de ghep noi chinh xac.
- Video assembly theo manifest, giu audio goc cua doan cat (`keep_original_audio: true`).

## Project docs

- `docs/Overview-Project/`
- `docs/Perception-Extraction/`
- `docs/Reasoning-NLP/`

## Environment split

- Thanh vien 1: `requirements-1.txt`
- Thanh vien 2: `requirements-2.txt`

## Colab notebooks

- Muc tieu: chay tung module hoac full pipeline tren Google Colab de tan dung CPU/GPU.
- URL repo da duoc gan san trong notebook: `https://github.com/TCTri205/video-summary.git`.

Open in Colab (branch `02-member-2-reasoning-nlp`):

- [Module 1 Extraction](https://colab.research.google.com/github/TCTri205/video-summary/blob/02-member-2-reasoning-nlp/notebooks/module1_extraction_colab.ipynb)
- [Module 2 Perception](https://colab.research.google.com/github/TCTri205/video-summary/blob/02-member-2-reasoning-nlp/notebooks/module2_perception_colab.ipynb)
- [Module 3 Reasoning](https://colab.research.google.com/github/TCTri205/video-summary/blob/02-member-2-reasoning-nlp/notebooks/module3_reasoning_colab.ipynb)
- [Full Pipeline M1->M2->M3](https://colab.research.google.com/github/TCTri205/video-summary/blob/02-member-2-reasoning-nlp/notebooks/full_pipeline_m1_m2_m3_colab.ipynb)

Notebook san co:

- `notebooks/module1_extraction_colab.ipynb`: chay Module 1 (extraction).
- `notebooks/module2_perception_colab.ipynb`: chay Module 2 (ASR + visual caption).
- `notebooks/module3_reasoning_colab.ipynb`: chay Module 3 (Reasoning-NLP G1->G8 + validate artifacts).
- `notebooks/full_pipeline_m1_m2_m3_colab.ipynb`: chay full he thong 3 module.

Input/Output mac dinh tren Drive:

- Input video: `/content/drive/MyDrive/video-summary/input/raw_video.mp4`
- Processed data: `/content/drive/MyDrive/video-summary/processed`
- Artifacts: `/content/drive/MyDrive/video-summary/artifacts`

Hardware behavior:

- Notebook tu dong detect `torch.cuda.is_available()`.
- Neu co GPU thi uu tien backend GPU; neu khong thi fallback CPU.

## Day 0 quick start

1. Thanh vien 2 dung mock data trong `docs/Overview-Project/mock-data/`.
2. Thanh vien 1 chay pipeline that de tao 2 JSON that.
3. Thay mock bang JSON that, chay lai Module 3 khong doi logic.
