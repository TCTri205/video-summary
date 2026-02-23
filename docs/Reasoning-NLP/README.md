# Thanh vien 2 - Reasoning and NLP Lead

Ban phu trach Module 3 va chien luoc QLoRA.

## Pham vi module

- Nhan du lieu tu Member 1, can chinh timeline audio-visual, tao tom tat, lap script/manifest, va render video summary.
- Muc tieu: output co tinh dung su kien, khong bia them, on dinh format, de van hanh production.

## Input nhan tu Thanh vien 1

- `audio_transcripts.json`
- `visual_captions.json`

## Output ban giao

- `summary_script.json`
- `summary_video_manifest.json`
- `summary_video.mp4`
- `alignment_result.json` (artifact trung gian)
- `quality_report.json` (artifact danh gia)
- (Giai doan fine-tune) LoRA adapter weights

## Kien truc pipeline (bat buoc theo thu tu)

1. Validate input schema va time invariants.
2. Align transcript + caption tren cung truc thoi gian.
3. Build merged context co confidence metadata.
4. Summarize bang LLM voi structured output.
5. Segment planning theo budget va coverage.
6. Tao `summary_script.json` + `summary_video_manifest.json`.
7. Video assembly tu `raw_video.mp4` voi `keep_original_audio = true`.
8. Chay quality gates va xuat `quality_report.json`.

## Runtime guarantees

- Deterministic voi cung input + cung config + cung seed.
- Fail-fast theo stage: fail o dau dung o do, khong render tiep.
- Co the replay tung stage bang artifact trung gian.

## Rule tich hop

- Input phai pass schema v1 trong `contracts/v1/` va input invariants (xem `alignment-spec.md`).
- Timestamp bat buoc su dung format `HH:MM:SS.mmm`.
- Neu fail bat ky gate nao, pipeline dung va tra ma loi chuan.
- Video summary phai duoc cat/ghep tu video goc va giu audio goc.
- Script va manifest phai pass cross-file consistency checks.

## Error code convention

- `SCHEMA_*`: loi dinh dang payload, field, kieu du lieu.
- `TIME_*`: loi parse timestamp, start/end invalid, out-of-range.
- `ALIGN_*`: loi can chinh timeline, khong tao duoc context hop le.
- `LLM_*`: loi infer, loi parse output, loi grounding.
- `MANIFEST_*`: loi tham chieu script-manifest.
- `RENDER_*`: loi cat/ghep video, codec, audio.
- `QC_*`: loi quality gate sau render.

## Operational notes

- Moi stage phai ghi log co `run_id`, `stage`, `status`, `error_code` (neu co), va thoi gian xu ly.
- Khong cho phep output parse duoc nhung rong/noi dung vo nghia.
- Khong chen voice-over moi trong MVP.

## Tai lieu bo sung

- JSON Schema chinh thuc cho deliverable I/O nam trong `contracts/v1/` (contract-first).
- Schema trong `docs/02-member-2-reasoning-nlp/schema/` chi dung cho artifact noi bo cua Module 3.
- Checklist nghiem thu QA theo gate nam trong `docs/02-member-2-reasoning-nlp/qa-acceptance-checklist.md`.
- Bang doi chieu tuong thich global/internal nam trong `docs/02-member-2-reasoning-nlp/compatibility-matrix.md`.
