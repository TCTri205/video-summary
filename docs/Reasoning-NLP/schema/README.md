# JSON Schema Pack (Module 3)

Bo schema nay phuc vu artifact noi bo cho pipeline `02-member-2-reasoning-nlp`.

Luu y contract-first:

- Deliverable I/O lien module phai validate bang `contracts/v1/*.schema.json`.
- Bo schema trong thu muc nay KHONG thay the contract global trong `contracts/v1/`.

## Danh sach schema

- `alignment_result.schema.json`
- `quality_report.schema.json`
- `summary_script.internal.schema.json` (artifact noi bo)
- `summary_video_manifest.internal.schema.json` (artifact noi bo)

## Examples

- `examples/*.valid.json`: mau hop le de test happy-path.
- `examples/invalid/*.invalid.json`: mau sai co chu dich de test fail-fast.

## Quy uoc

- Chuan schema: JSON Schema Draft 2020-12.
- `schema_version` hien tai: `1.1`.
- Timestamp video format: `HH:MM:SS.mmm`.

## Cach dung

1. Validate artifact ngay sau moi stage.
2. Neu la deliverable (`summary_script.json`, `summary_video_manifest.json`), validate bang schema trong `contracts/v1/`.
3. Neu la artifact noi bo (`alignment_result.json`, `quality_report.json`), validate bang schema local trong thu muc nay.
4. Chay them cross-file checks va quality gates (xem `../qa-acceptance-checklist.md`).

## Lenh mau cho QA

Happy-path (du kien pass, deliverable theo contracts/v1):

```bash
python docs/02-member-2-reasoning-nlp/schema/validate_artifacts.py \
  --alignment docs/02-member-2-reasoning-nlp/schema/examples/alignment_result.valid.json \
  --script docs/02-member-2-reasoning-nlp/schema/examples/summary_script.valid.json \
  --manifest docs/02-member-2-reasoning-nlp/schema/examples/summary_video_manifest.valid.json \
  --report docs/02-member-2-reasoning-nlp/schema/examples/quality_report.valid.json \
  --contracts-dir contracts/v1 \
  --source-duration-ms 120000 \
  --enforce-thresholds
```

Fail-fast test (du kien fail):

```bash
python docs/02-member-2-reasoning-nlp/schema/validate_artifacts.py \
  --alignment docs/02-member-2-reasoning-nlp/schema/examples/invalid/alignment_result.invalid.json \
  --script docs/02-member-2-reasoning-nlp/schema/examples/invalid/summary_script.invalid.json \
  --manifest docs/02-member-2-reasoning-nlp/schema/examples/invalid/summary_video_manifest.invalid.json \
  --report docs/02-member-2-reasoning-nlp/schema/examples/invalid/quality_report.invalid.json \
  --contracts-dir contracts/v1 \
  --source-duration-ms 120000 \
  --enforce-thresholds
```

Internal-only profile (neu can test schema noi bo cho summary/manifest):

```bash
python docs/02-member-2-reasoning-nlp/schema/validate_artifacts.py \
  --alignment docs/02-member-2-reasoning-nlp/schema/examples/alignment_result.valid.json \
  --script docs/02-member-2-reasoning-nlp/schema/examples/internal/summary_script.internal.valid.json \
  --manifest docs/02-member-2-reasoning-nlp/schema/examples/internal/summary_video_manifest.internal.valid.json \
  --report docs/02-member-2-reasoning-nlp/schema/examples/quality_report.valid.json \
  --use-internal-summary-schemas \
  --source-duration-ms 120000
```
