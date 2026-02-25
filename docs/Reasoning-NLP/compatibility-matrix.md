# Compatibility Matrix - Global Contract vs Internal Artifacts

Tai lieu nay tom tat nhanh de tranh nham lan giua:

- Deliverable I/O lien module (bat buoc theo global contract)
- Internal artifacts Module 3 (phuc vu reasoning, QA, debug)

## Rule 0 (bat buoc)

- Contract-first: deliverable I/O phai theo `contracts/v1/template/`.
- Internal fields khong duoc chen vao deliverable neu schema global khong cho phep.
- Global contracts trong repo hien tai nam o `contracts/v1/template/`.

## Thuat ngu thong nhat

- `global schema`: schema deliverable lien module trong `contracts/v1/template/`.
- `internal schema`: schema artifact noi bo trong `docs/Reasoning-NLP/schema/`.
- `deliverable`: file ban giao lien module (`summary_script.json`, `summary_video_manifest.json`, `summary_video.mp4`, va `final_summary.json` neu can xuat).
- `internal artifact`: file debug/QA/truy vet (`alignment_result.json`, `quality_report.json`, `*.internal.json`).

## Input profile policy (Module 3)

- Profile mac dinh: `strict_contract_v1`.
- Profile tuong thich tam thoi: `legacy_member1`.
- Sau normalize, pipeline noi bo chi lam viec voi 1 canonical format.

## Mapping bang nhanh

| Artifact | Loai | Schema nguon chuan | Co duoc chen field noi bo? | Ghi chu |
|---|---|---|---|---|
| `audio_transcripts.json` | Input lien module | `contracts/v1/template/audio_transcripts.schema.json` (strict profile) | Khong | Input tu Module 1+2 |
| `visual_captions.json` | Input lien module | `contracts/v1/template/visual_captions.schema.json` | Khong | Input tu Module 1+2 |
| `summary_script.json` | Deliverable lien module | `contracts/v1/template/summary_script.schema.json` | Khong | Output chinh de render |
| `summary_video_manifest.json` | Deliverable lien module | `contracts/v1/template/summary_video_manifest.schema.json` | Khong | Must keep `keep_original_audio=true` |
| `summary_video.mp4` | Deliverable cuoi | QC theo checklist | Khong ap dung | File media |
| `final_summary.json` | Deliverable (optional) | `contracts/v1/template/final_summary.schema.json` | Khong | Strict contract, khong chen field metadata noi bo |
| `alignment_result.json` | Internal | `docs/Reasoning-NLP/schema/alignment_result.schema.json` | Co | Artifact align + confidence |
| `quality_report.json` | Internal | `docs/Reasoning-NLP/schema/quality_report.schema.json` | Co | Artifact gate/metric |
| `summary_script.internal.json` | Internal | `docs/Reasoning-NLP/schema/summary_script.internal.schema.json` | Co | Noi luu `evidence`, `quality_flags`, `generation_meta` |
| `summary_video_manifest.internal.json` | Internal | `docs/Reasoning-NLP/schema/summary_video_manifest.internal.schema.json` | Co | Khong phai deliverable lien module |

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
  - `summary_script.json`, `summary_video_manifest.json`, `final_summary.json` validate theo `contracts/v1/template/`.
  - `alignment_result.json`, `quality_report.json` validate theo internal schema local.
- Internal profile (tu chon):
  - Dung `--use-internal-summary-schemas` de validate summary/manifest theo schema internal (`*.internal.json`).

## Single source of truth

- Deliverable contracts: `contracts/v1/template/*.schema.json`.
- Internal artifact schemas: `docs/Reasoning-NLP/schema/*.schema.json`.
- QA policy: `docs/Reasoning-NLP/qa-acceptance-checklist.md`.

## Lenh tham chieu

Xem lenh chi tiet tai `docs/Reasoning-NLP/schema/README.md`.
