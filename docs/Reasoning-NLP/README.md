# Thanh vien 2 - Reasoning and NLP Lead

Ban phu trach Module 3 va chien luoc QLoRA.

## Pham vi module

- Nhan du lieu tu Module 1+2, can chinh timeline audio-visual, tao tom tat, lap script/manifest, va render video summary.
- Muc tieu: output dung su kien, khong bia them, on dinh format, de van hanh production.

## Input nhan tu Module 1+2

- `audio_transcripts.json`
- `visual_captions.json`

## Input compatibility profile (de tich hop)

- `strict_contract_v1` (uu tien): theo schema global trong `contracts/v1/template/`.
- `legacy_member1` (ho tro nguoc): chap nhan transcript dang object `{language, duration, segments[]}` voi `segments[].start/end` la float giay.
- Bat buoc normalize ve canonical format noi bo truoc stage align:
  - timestamp string `HH:MM:SS.mmm`
  - id on dinh (`transcript_id`, `caption_id`)
  - text da trim; neu rong thi gan co `is_empty_text=true`

## Output ban giao

Deliverable cuoi cho nguoi dung:

- `deliverables/<run_id>/summary_video.mp4`
- `deliverables/<run_id>/summary_text.txt`

Deliverable lien module (global contract, technical):

- `summary_script.json`
- `summary_video_manifest.json`
- `summary_video.mp4`

Internal artifacts (khong phai deliverable lien module):

- `context_blocks.json`
- `alignment_result.json`
- `quality_report.json`
- `summary_script.internal.json` (khuyen nghi dung de luu `evidence`, `quality_flags`, `generation_meta`)
- `summary_video_manifest.internal.json` (neu can debug)

Luu y quan trong:

- Runtime hien tai publish deliverable cuoi gom `summary_video.mp4` va `summary_text.txt`.
- `final_summary.json` la contract optional; neu duoc xuat bo sung thi phai strict theo `contracts/v1/template/final_summary.schema.json`.
- Khong chen `evidence`, `quality_flags`, `generation_meta`, `confidence`, `role` vao deliverable contract.

## Kien truc pipeline (bat buoc theo thu tu)

1. Validate input schema va time invariants.
2. Align transcript + caption tren cung truc thoi gian.
3. Build merged context co confidence metadata.
4. Summarize bang LLM voi structured output internal.
5. Segment planning theo budget va coverage.
6. Tao deliverable `summary_script.json` + `summary_video_manifest.json`.
7. Video assembly tu `raw_video.mp4` voi `keep_original_audio = true`.
8. Chay quality gates va xuat `quality_report.json`.

## Runtime guarantees

- Deterministic voi cung input + cung config + cung seed.
- Fail-fast theo stage: fail o dau dung o do, khong render tiep.
- Co the replay tung stage bang artifacts trung gian.

## Rule tich hop

- Input phai pass profile validation (`strict_contract_v1` hoac `legacy_member1`) va input invariants (xem `alignment-spec.md`).
- Timestamp bat buoc format `HH:MM:SS.mmm`.
- Neu fail bat ky gate nao, pipeline dung va tra ma loi chuan.
- Video summary phai cat/ghep tu video goc va giu audio goc.
- Script va manifest phai pass cross-file consistency checks.

## Handshake voi Perception-Extraction

Ky vong upstream (Module 1+2):

- Transcript sap xep tang dan theo `start`.
- Caption bat buoc sap xep tang dan theo `timestamp`.
- Text khong rong sau trim; neu rong thi can duoc danh dau ro.

Xu ly an toan o Module 3 (neu upstream chua dam bao):

- Luon sort stable transcript/caption truoc align.
- Luon trim text va danh dau empty text de fallback neutral.
- Gan id on dinh neu input chua co id.

## Error code convention

- `SCHEMA_*`: loi dinh dang payload, field, kieu du lieu.
- `TIME_*`: loi parse timestamp, start/end invalid, out-of-range.
- `ALIGN_*`: loi can chinh timeline, khong tao duoc context hop le.
- `LLM_*`: loi infer, loi parse output, loi grounding.
- `MANIFEST_*`: loi tham chieu script-manifest.
- `RENDER_*`: loi cat/ghep video, codec, audio.
- `QC_*`: loi quality gate sau render.

## KPI van hanh de xuat

- `parse_validity_rate >= 0.995`
- `timeline_consistency_score >= 0.90`
- `grounding_score >= 0.85`
- `manifest_consistency_pass = true`
- `render_success = true`
- `audio_present = true`
- `black_frame_ratio <= 0.02`

KPI hieu nang (nen theo doi them):

- `p95_align_latency_ms`
- `p95_summarize_latency_ms`
- `tokens_per_video`
- `retry_rate_by_stage`

## Operational notes

- Moi stage phai ghi log: `run_id`, `stage`, `status`, `error_code` (neu co), `duration_ms`.
- Khong cho phep output parse duoc nhung rong/noi dung vo nghia.
- Khong chen voice-over moi trong MVP.
- Neu phat hien `LLM_NEUTRAL_FALLBACK` trong quality flags thi fail run ngay.

## Huong dan chay pipeline

Yeu cau toi thieu:

- Co `ffmpeg` va `ffprobe` trong `PATH`.
- Co 3 input files: `audio_transcripts.json`, `visual_captions.json`, `raw_video.mp4`.

### 1) Chay full G1 -> G8

```bash
python -m reasoning_nlp.cli \
  --audio-transcripts Data/processed/video1/extraction/audio_transcripts.json \
  --visual-captions Data/processed/video1/extraction/visual_captions.json \
  --raw-video Data/raw/video1.mp4 \
  --stage g8 \
  --run-id run_demo_001
```

`source_duration_ms` duoc auto-probe tu `raw_video.mp4` o G1. `--source-duration-ms` chi dung khi can override debug.

Dual-mode LLM:

- `--summarize-backend {api,local,heuristic}` chon backend chinh.
- `--summarize-fallback-backend {api,local,heuristic}` cho phep fallback neu backend chinh fail.
- Env cho API mode: `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`.

QC threshold enforcement:

- Bat strict gate runtime bang `--qc-enforce-thresholds`.
- Co the dieu chinh threshold qua cac flag `--qc-min-*` / `--qc-max-*`.

Artifacts se duoc ghi vao:

- `artifacts/<run_id>/g2_align/alignment_result.json`
- `artifacts/<run_id>/g3_context/context_blocks.json`
- `artifacts/<run_id>/g4_summarize/summary_script.internal.json`
- `artifacts/<run_id>/g5_segment/summary_script.json`
- `artifacts/<run_id>/g5_segment/summary_video_manifest.json`
- `artifacts/<run_id>/g7_assemble/summary_video.mp4`
- `artifacts/<run_id>/g8_qc/quality_report.json`

### 2) Chay den stage cu the

- Den G3: `--stage g3`
- Den G5: `--stage g5`
- Full G8: `--stage g8`

### 3) Replay mode (skip stage da co artifact hop le)

```bash
python -m reasoning_nlp.cli \
  --audio-transcripts Data/processed/video1/extraction/audio_transcripts.json \
  --visual-captions Data/processed/video1/extraction/visual_captions.json \
  --raw-video Data/raw/video1.mp4 \
  --stage g8 \
  --run-id run_demo_001 \
  --replay
```

Luu y replay:

- Bat buoc co `--run-id` trung voi run cu.
- Replay skip theo stage dependency hash (khong chi hash tong): stage mismatch se invalidate stage do va downstream.

### 4) Validate artifacts sau khi chay

```bash
python docs/Reasoning-NLP/schema/validate_artifacts.py \
  --alignment artifacts/run_demo_001/g2_align/alignment_result.json \
  --script artifacts/run_demo_001/g5_segment/summary_script.json \
  --manifest artifacts/run_demo_001/g5_segment/summary_video_manifest.json \
  --report artifacts/run_demo_001/g8_qc/quality_report.json \
  --contracts-dir contracts/v1/template \
  --source-duration-ms 1900000
```

## Tai lieu bo sung

- Deliverable schema (single source): `contracts/v1/template/*.schema.json`.
- Internal schema Module 3: `docs/Reasoning-NLP/schema/*.schema.json`.
- Validator chuan: `docs/Reasoning-NLP/schema/validate_artifacts.py`.
- QA gates chuan: `docs/Reasoning-NLP/qa-acceptance-checklist.md`.
- Bang doi chieu tuong thich: `docs/Reasoning-NLP/compatibility-matrix.md`.
- So do luong pipeline + grounding text-video: `docs/Reasoning-NLP/pipeline-flow-and-grounding.md`.
