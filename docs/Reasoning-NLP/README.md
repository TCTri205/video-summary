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

Deliverable lien module (global contract):

- `summary_script.json`
- `summary_video_manifest.json`
- `summary_video.mp4`

Internal artifacts (khong phai deliverable lien module):

- `alignment_result.json`
- `quality_report.json`
- `summary_script.internal.json` (khuyen nghi dung de luu `evidence`, `quality_flags`, `generation_meta`)
- `summary_video_manifest.internal.json` (neu can debug)

Luu y quan trong:

- `final_summary.json` neu duoc xuat thi phai strict theo `contracts/v1/template/final_summary.schema.json`.
- Khong chen `evidence`, `quality_flags`, `generation_meta`, `confidence`, `role` vao `final_summary.json`.

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

## Tai lieu bo sung

- Deliverable schema (single source): `contracts/v1/template/*.schema.json`.
- Internal schema Module 3: `docs/Reasoning-NLP/schema/*.schema.json`.
- Validator chuan: `docs/Reasoning-NLP/schema/validate_artifacts.py`.
- QA gates chuan: `docs/Reasoning-NLP/qa-acceptance-checklist.md`.
- Bang doi chieu tuong thich: `docs/Reasoning-NLP/compatibility-matrix.md`.
