# Compatibility Matrix - Global Contract vs Internal Artifacts

Tai lieu nay tom tat nhanh de tranh nham lan giua:

- Deliverable I/O lien module (bat buoc theo global contract)
- Artifact noi bo Module 3 (phuc vu reasoning, QA, debug)

## Rule 0 (bat buoc)

- Contract-first: deliverable I/O phai theo `contracts/v1/`.
- Internal fields khong duoc chen vao deliverable neu schema global khong cho phep.

## Mapping bang nhanh

| Artifact | Loai | Schema nguon chuan | Co duoc chen field noi bo? | Ghi chu |
|---|---|---|---|---|
| `audio_transcripts.json` | Input lien module | `contracts/v1/audio_transcripts.schema.json` | Khong | Input tu Module 1 |
| `visual_captions.json` | Input lien module | `contracts/v1/visual_captions.schema.json` | Khong | Input tu Module 1 |
| `summary_script.json` | Deliverable lien module | `contracts/v1/summary_script.schema.json` | Khong | Output chinh de render |
| `summary_video_manifest.json` | Deliverable lien module | `contracts/v1/summary_video_manifest.schema.json` | Khong | Must keep `keep_original_audio=true` |
| `summary_video.mp4` | Deliverable cuoi | QC theo checklist | Khong ap dung | File media |
| `final_summary.json` | Internal optional | `contracts/v1/final_summary.schema.json` | Co | Dung cho debug/fine-tune |
| `alignment_result.json` | Internal | `docs/02-member-2-reasoning-nlp/schema/alignment_result.schema.json` | Co | Artifact align + confidence |
| `quality_report.json` | Internal | `docs/02-member-2-reasoning-nlp/schema/quality_report.schema.json` | Co | Artifact gate/metric |
| `summary_script.internal.json` | Internal (neu dung) | `docs/02-member-2-reasoning-nlp/schema/summary_script.internal.schema.json` | Co | Khong phai deliverable lien module |
| `summary_video_manifest.internal.json` | Internal (neu dung) | `docs/02-member-2-reasoning-nlp/schema/summary_video_manifest.internal.schema.json` | Co | Khong phai deliverable lien module |

## Internal fields thuong gap

Nhung field sau chi nen o artifact noi bo:

- `schema_version` (cho artifact noi bo)
- `evidence`
- `quality_flags`
- `generation_meta`
- `confidence`
- `role`

Khong chen cac field tren vao deliverable neu schema global v1 khong cho phep.

## Validation profile

- Global profile (mac dinh):
  - `summary_script` + `summary_video_manifest` validate theo `contracts/v1`.
  - `alignment_result` + `quality_report` validate theo local internal schema.
- Internal profile (tu chon):
  - Dung `--use-internal-summary-schemas` de validate summary/manifest theo schema internal.

## Lenh tham chieu

Xem lenh chi tiet tai `docs/02-member-2-reasoning-nlp/schema/README.md`.
