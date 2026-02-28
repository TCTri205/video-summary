# Video Summary Project

Du an tom tat video theo pipeline 3 module, phan tach ro trach nhiem de 2 thanh vien lam viec doc lap.

## Requirements
- Python 3.8+
- FFmpeg:
  + https://www.gyan.dev/ffmpeg/builds/
  + Chọn bản ffmpeg-release-essentials.zip
  + Giải nén, thêm thư mục `bin/` vào PATH của hệ thống.

## One-command local run

Muc tieu: chi can mot lenh `python main.py` de chay full he thong Module 1 -> 2 -> 3.

Lenh mac dinh:

```bash
python main.py
```

Mac dinh se:

- Input video: `Data/raw/video1.mp4`
- Output extraction/perception: `Data/processed/<video_name>/extraction/...`
- Stage reasoning: `g8` (full)
- Summarize backend: `local` (khong can API key)

Artifact cuoi (G8):

- `artifacts/<run_id>/g5_segment/summary_script.json`
- `artifacts/<run_id>/g5_segment/summary_video_manifest.json`
- `artifacts/<run_id>/g7_assemble/summary_video.mp4`
- `artifacts/<run_id>/g8_qc/quality_report.json`

Co the override linh hoat qua CLI/env/config JSON.

Vi du CLI:

```bash
python main.py --video-path Data/raw/video2.mp4 --run-id run_local_002 --stage g8
```

Vi du ENV:

```bash
set VIDEO_SUMMARY_VIDEO_PATH=Data/raw/video2.mp4
set VIDEO_SUMMARY_SUMMARIZE_BACKEND=local
python main.py
```

Vi du config file:

```json
{
  "video_path": "Data/raw/video2.mp4",
  "output_root": "Data/processed",
  "artifacts_root": "artifacts",
  "stage": "g8",
  "run_id": "run_local_cfg_001",
  "summarize_backend": "local",
  "summarize_fallback_backend": "local",
  "qc_enforce_thresholds": false
}
```

```bash
python main.py --config run_config.json
```

Thu tu uu tien config: `CLI > ENV > config file > default`.


## Architecture

- Module 1: Data extraction (`raw_video.mp4` -> `audio_16k.wav`, `keyframes/`, `scene_metadata.json`)
- Module 2: Perception AI (`audio_16k.wav` + keyframes -> `audio_transcripts.json`, `visual_captions.json`)
- Module 3: Fusion, reasoning, and assembly (`audio_transcripts.json` + `visual_captions.json` -> `summary_script.json` + `summary_video_manifest.json` -> `summary_video.mp4`)

## Final deliverables

- `deliverables/<run_id>/summary_video.mp4` (video tom tat cat + ghep tu video goc, giu audio goc)
- `deliverables/<run_id>/summary_text.txt` (van ban tom tat de doc cho nguoi dung)

Ghi chu: `summary_script.json`, `summary_video_manifest.json`, `quality_report.json` la artifact ky thuat trong `artifacts/<run_id>/` de debug va nghiem thu.

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

1. Thanh vien 2 dung mock data trong `Data/mock/`.
2. Thanh vien 1 chay pipeline that de tao 2 JSON that.
3. Thay mock bang JSON that, chay lai Module 3 khong doi logic.

## Colab hybrid runbook (optimized)

- Muc tieu: giu nguyen core pipeline, toi uu toc do/bo nho khi chay Colab.
- Cach chay: xu ly trung gian o `/content/video-summary-work`, sau do sync co chon loc ve Drive.
- Mac dinh summarize backend tren Colab: `local` (khong can API key).

### Runtime profiles

- Notebook tu detect profile va tu dieu chinh tham so:
  - `CPU`: batch caption nho, token summarize thap de on dinh RAM.
  - `T4`: can bang toc do va bo nho.
  - `L4`: uu tien throughput cao hon.

### Resume an toan (replay)

- Dat `RUN_ID` co dinh qua bien moi truong truoc khi chay cell pipeline:
  - `VIDEO_SUMMARY_RUN_ID=<run-id-ban-muon-replay>`
- Trong notebook, dat `REPLAY_MODE = True` de bat `--replay`.
- Replay se skip stage hop le dua tren `run_meta.json` + stage hashes.

### Balanced checkpoint policy

- Notebook giu cac artifact can cho replay nhanh va an toan:
  - `run_meta.json`
  - `g1_validate/normalized_input.json`
  - `g2_align/alignment_result.json`
  - `g3_context/context_blocks.json`
  - `g4_summarize/parse_meta.json`
  - `g4_summarize/summary_script.internal.json`
  - `g5_segment/summary_script.json`
  - `g5_segment/summary_video_manifest.json`
  - `g6_manifest/manifest_validation.json`
  - `g7_assemble/render_meta.json`
  - `g7_assemble/summary_video.mp4`
  - `g8_qc/quality_report.json`

### Disk cleanup policy

- Co the xoa endpoint nang sau khi dong bo artifact cuoi:
  - `processed/<video>/extraction/keyframes/`
  - `processed/<video>/extraction/audio/audio_16k.wav`
- Giu so luong run gan nhat bang `KEEP_LAST_RUNS` de tranh day Drive.
