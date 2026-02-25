# Release Runbook

Tai lieu nay mo ta checklist van hanh/release cho pipeline video summary G1->G8.

## 1) Preflight

- Xac nhan `ffmpeg` va `ffprobe` co trong PATH.
- Chay unit + integration + smoke G1->G8 + schema validate.
- Xac nhan env cho LLM API (neu dung backend api):
  - `OPENAI_BASE_URL`
  - `OPENAI_API_KEY`
  - `OPENAI_MODEL`

## 2) Quality Gates (must pass)

- `parse_validity_rate >= 0.995`
- `timeline_consistency_score >= 0.90`
- `grounding_score >= 0.85`
- `render_success = true`
- `audio_present = true`
- `black_frame_ratio <= 0.02`
- `no_match_rate <= 0.30`
- `median_confidence >= 0.60`
- `high_confidence_ratio >= 0.50`

## 3) Go/No-Go Decision

- GO khi tat ca gate pass va khong co blocker trong `errors`.
- NO-GO khi co bat ky gate fail hoac co stage fail.

## 4) Rollback Checklist

- Quay lai version release truoc do.
- Dung runbook triage theo nhom loi:
  - `SCHEMA_*`, `TIME_*`, `ALIGN_*`, `LLM_*`, `MANIFEST_*`, `RENDER_*`, `QC_*`.
- Luu artifact run fail de phan tich root-cause.

## 5) Post-release Monitoring

- Theo doi KPI batch hang ngay bang `scripts/kpi_batch.py`.
- Theo doi ty le fail theo stage.
- Neu grounding/black-frame giam duoi nguong, dung release tiep theo va dieu tra.
