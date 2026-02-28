# Implementation Plan - Module 3 (Reasoning-NLP)

## 1) Muc tieu

- Duy tri pipeline G1->G8 on dinh, deterministic, fail-fast, replayable.
- Dam bao contract-first: deliverable lane theo `contracts/v1/template/`, internal lane cho reasoning/QA/debug.
- Giam drift giua docs va runtime bang quy trinh doi chieu dinh ky.

## 2) As-built hien tai (doi chieu voi code runtime)

### 2.1 Stage map va artifact

- G1 `validate`: validate input profile + normalize canonical + auto probe `source_duration_ms`.
- G2 `align`: adaptive delta + matching deterministic + confidence.
- G3 `context_build`: tao merged context blocks.
- G4 `summarize`: infer (api/local) + parse repair + grounding check + gan internal segments (segment planning dong duoc tinh tai day).
- G5 `segment_plan`: map internal summary sang deliverable `summary_script.json` + `summary_video_manifest.json`.
- G6 `manifest`: cross-file consistency checks.
- G7 `assemble`: render ffmpeg + retry safe profile 1 lan + verify audio.
- G8 `qc`: tong hop metrics/gates + quality report + publish deliverables cuoi.

Artifacts lane:

- Deliverable lien module: `summary_script.json`, `summary_video_manifest.json`, `summary_video.mp4`.
- Internal artifacts: `alignment_result.json`, `context_blocks.json`, `summary_script.internal.json`, `quality_report.json`, `run_meta.json`.
- Publish deliverables cho nguoi dung (runtime mac dinh): `deliverables/<run_id>/summary_video.mp4`, `deliverables/<run_id>/summary_text.txt`.
- `final_summary.json` la contract optional artifact, khong phai output publish mac dinh cua runtime hien tai.

### 2.2 Cac diem da co trong runtime

- Stage dependency hash replay invalidation da co theo dependency graph stage.
- `source_duration_ms` auto probe tu `raw_video.mp4` da co trong G1.
- QC metrics that da co (khong con placeholder metric).
- CLI da tach rieng (`reasoning_nlp/cli.py`).
- Schema validation lane va cross-file checks da bat buoc trong luong chay.

### 2.3 Cac rang buoc runtime can ghi ro

- Fallback assemble hien tai la retry safe render profile; khong co auto-merge segment o stage G7.
- Neu `LLM_NEUTRAL_FALLBACK` xuat hien trong quality flags, run bi fail o gate QC.
- Backend summarize runtime ho tro: `api`, `local` (main va fallback).
- `heuristic` chi dung cho test/integration khi bat co test-only, khong phai runtime production option.

## 3) Backlog nang cap tiep theo (roadmap)

### P1 - Doc/runtime consistency hardening

- Bo sung bang traceability "Doc claim -> Code source" cho moi gate G1->G8.
- Them checklist review docs bat buoc trong PR thay doi runtime.

### P2 - Summarization va segment quality

- Nang cap long-context strategy theo chunking da pha (hien runtime moi truncation theo char budget).
- Nang cap scoring/selection segment theo domain videos phong phu hon.

### P3 - Integration va operations

- Hoan thien fixtures handoff chung voi Module 1+2.
- Chot alerting/retention policy production theo KPI gates.

## 4) Definition of Done cho pha dong bo docs

- Toan bo docs trong `docs/Reasoning-NLP/` khong con noi dung trai runtime hien tai.
- Cac references schema/contracts/artifacts nhat quan voi code va file that trong repo.
- QA checklist phan anh dung cac blocker gates that (dac biet `LLM_NEUTRAL_FALLBACK`).
- Cac command CLI trong docs khop voi options that cua `reasoning_nlp/cli.py`.

## 5) Quy trinh duy tri sau nay

- Moi thay doi runtime lien quan gate/artifact/schema phai cap nhat docs cung PR.
- Doi chieu nhanh bang script validate artifacts + grep drift truoc merge.
- Uu tien "as-built truth" trong docs, tach rieng "roadmap" de tranh nham lan.
