# JSON Schema Pack (Module 3)

Bo schema nay phuc vu artifact noi bo cho pipeline `Reasoning-NLP`.

Luu y contract-first:

- Deliverable I/O lien module phai validate bang schema global trong `contracts/v1/template/*.schema.json`.
- Bo schema trong thu muc nay KHONG thay the contract global trong `contracts/v1/`.

## Danh sach schema

- `alignment_result.schema.json`
- `quality_report.schema.json`
- `summary_script.internal.schema.json` (artifact noi bo)
- `summary_video_manifest.internal.schema.json` (artifact noi bo)

## Quy uoc

- Chuan schema: JSON Schema Draft 2020-12.
- `schema_version` noi bo hien tai: `1.1`.
- Timestamp video format: `HH:MM:SS.mmm`.

## Validation profiles

### 1) Production strict profile (khuyen nghi)

Muc dich: nghiem thu deliverable lien module truoc handoff.

- `summary_script.json` -> `contracts/v1/template/summary_script.schema.json`
- `summary_video_manifest.json` -> `contracts/v1/template/summary_video_manifest.schema.json`
- `alignment_result.json`, `quality_report.json` -> internal schemas
- Cross-file consistency + threshold gates: bat

### 2) Internal debug profile

Muc dich: debug reasoning lane voi artifact mo rong.

- `summary_script.internal.json` -> `summary_script.internal.schema.json`
- `summary_video_manifest.internal.json` -> `summary_video_manifest.internal.schema.json`
- Dung flag `--use-internal-summary-schemas`

## Cach dung

1. Validate artifact ngay sau moi stage.
2. Deliverable validate theo global contracts.
3. Internal artifacts validate theo local schemas.
4. Chay them cross-file checks va quality gates (xem `../qa-acceptance-checklist.md`).

## Error-to-action matrix (tom tat)

- `SCHEMA_*`: sai field/kieu -> sua payload mapper, validate lai.
- `TIME_*`: sai timestamp/range -> normalize timestamp, check sort/range.
- `ALIGN_*`: mismatch timeline -> check delta policy, tie-break, no_match_rate.
- `LLM_*`: parse fail/hallucination -> retry JSON repair, fallback neutral.
- `MANIFEST_*`: script-manifest lech -> dong bo `segment_id`, `script_ref`, timestamps.
- `RENDER_*`: render/codec/audio -> retry safe profile 1 lan, neu van fail thi stop.
- `QC_*`: fail gate cuoi -> triage theo metric fail trong `quality_report.metrics`.

## Single source of truth

- Contracts deliverable: `contracts/v1/template/*.schema.json`.
- Internal schemas: `docs/Reasoning-NLP/schema/*.schema.json`.
- QA policy: `docs/Reasoning-NLP/qa-acceptance-checklist.md`.
- Integration policy: `docs/Reasoning-NLP/compatibility-matrix.md`.

## Lenh mau cho QA

Happy-path (du kien pass, deliverable theo contracts):

```bash
python docs/Reasoning-NLP/schema/validate_artifacts.py \
  --alignment docs/Reasoning-NLP/schema/examples/alignment_result.valid.json \
  --script docs/Reasoning-NLP/schema/examples/summary_script.valid.json \
  --manifest docs/Reasoning-NLP/schema/examples/summary_video_manifest.valid.json \
  --report docs/Reasoning-NLP/schema/examples/quality_report.valid.json \
  --contracts-dir contracts/v1/template \
  --source-duration-ms 120000 \
  --enforce-thresholds
```

Fail-fast test (du kien fail):

```bash
python docs/Reasoning-NLP/schema/validate_artifacts.py \
  --alignment docs/Reasoning-NLP/schema/examples/invalid/alignment_result.invalid.json \
  --script docs/Reasoning-NLP/schema/examples/invalid/summary_script.invalid.json \
  --manifest docs/Reasoning-NLP/schema/examples/invalid/summary_video_manifest.invalid.json \
  --report docs/Reasoning-NLP/schema/examples/invalid/quality_report.invalid.json \
  --contracts-dir contracts/v1/template \
  --source-duration-ms 120000 \
  --enforce-thresholds
```

Internal debug profile:

```bash
python docs/Reasoning-NLP/schema/validate_artifacts.py \
  --alignment docs/Reasoning-NLP/schema/examples/alignment_result.valid.json \
  --script docs/Reasoning-NLP/schema/examples/internal/summary_script.internal.valid.json \
  --manifest docs/Reasoning-NLP/schema/examples/internal/summary_video_manifest.internal.valid.json \
  --report docs/Reasoning-NLP/schema/examples/quality_report.valid.json \
  --use-internal-summary-schemas \
  --source-duration-ms 120000
```
