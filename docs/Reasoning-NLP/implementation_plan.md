# Implementation Plan - Module 3 (Reasoning-NLP)

## 1) Muc tieu implementation

- Implement pipeline Module 3 theo dung gate G1 -> G8 trong `qa-acceptance-checklist.md`.
- Dam bao contract-first: deliverable lane tuan thu `contracts/v1/template/`, internal lane cho reasoning/QA/debug.
- Fail-fast, deterministic, replayable theo `run_id` va artifacts tung stage.

## 2) Nguyen tac thiet ke

- Contract-first, schema-first.
- Stage isolation: moi stage co input/output ro rang, co the replay doc lap.
- Deterministic by default (`seed` co dinh, infer params duoc log).
- Fail-fast on blocker, warning cho phep tiep tuc khi policy cho phep.
- Khong chen internal fields vao deliverable lane.

## 3) Kien truc module de xuat

```
module3/
  __init__.py
  config/
    defaults.py
  common/
    errors.py
    timecode.py
    io_json.py
    logging.py
    types.py
  validators/
    input_validator.py
    artifact_validator.py
    cross_file_checks.py
  aligner/
    normalize.py
    matcher.py
    confidence.py
    context_builder.py
  summarizer/
    prompt_builder.py
    llm_client.py
    parse_repair.py
    grounding_checks.py
  segment_planner/
    planner.py
    budget_policy.py
    role_coverage.py
  assembler/
    manifest_builder.py
    ffmpeg_runner.py
    audio_policy.py
  qc/
    metrics.py
    report_builder.py
  pipeline_runner.py
```

## 4) Mapping gate -> component

- G1 `validate`: `validators.input_validator`
- G2 `align`: `aligner.normalize` + `aligner.matcher` + `aligner.confidence`
- G3 `context_build`: `aligner.context_builder`
- G4 `summarize`: `summarizer.*`
- G5 `segment_plan`: `segment_planner.*`
- G6 `manifest`: `validators.cross_file_checks` + `validators.artifact_validator`
- G7 `assemble`: `assembler.*`
- G8 `qc`: `qc.metrics` + `qc.report_builder` + `pipeline_runner`

## 5) Interface hop dong giua cac stage

- Input lane:
  - `audio_transcripts.json`
  - `visual_captions.json`
  - `raw_video.mp4`
- Internal artifacts:
  - `context_blocks.json`
  - `alignment_result.json`
  - `summary_script.internal.json`
  - `summary_video_manifest.internal.json` (optional)
  - `quality_report.json`
- Deliverable lane:
  - `summary_script.json`
  - `summary_video_manifest.json`
  - `summary_video.mp4`
  - `final_summary.json` (optional)

Rang buoc schema bat buoc:

- `alignment_result.json` -> `docs/Reasoning-NLP/schema/alignment_result.schema.json`.
- `summary_script.internal.json` -> `docs/Reasoning-NLP/schema/summary_script.internal.schema.json`.
- `summary_video_manifest.internal.json` (neu co) -> `docs/Reasoning-NLP/schema/summary_video_manifest.internal.schema.json`.
- `quality_report.json` -> `docs/Reasoning-NLP/schema/quality_report.schema.json`.
- Deliverable lane validate theo `contracts/v1/template/*.schema.json`.
- `raw_video.mp4` bat buoc ton tai, doc duoc, va co `duration_ms > 0` truoc khi vao G7.

Ma tran gate -> input/artifact toi thieu:

- G1 `validate`: `audio_transcripts.json`, `visual_captions.json`, `raw_video.mp4`.
- G2 `align`: input da normalize tu G1, output `alignment_result.json`.
- G3 `context_build`: `alignment_result.json`, output `context_blocks.json`.
- G4 `summarize`: `context_blocks.json`, output `summary_script.internal.json`.
- G5 `segment_plan`: `summary_script.internal.json`, output `summary_script.json` + `summary_video_manifest.json`.
- G6 `manifest`: `summary_script.json` + `summary_video_manifest.json`.
- G7 `assemble`: `raw_video.mp4` + `summary_video_manifest.json`, output `summary_video.mp4`.
- G8 `qc`: tong hop artifacts G1->G7, output `quality_report.json`.

`quality_report.json` toi thieu phai co:

- `schema_version=1.1`, `run_id`, `input_profile`, `overall_status`.
- `stage_results` day du 8 stage (`validate` -> `qc`) voi `status`, `duration_ms`, `error_code` (neu fail).
- `metrics` day du theo schema (bao gom alignment + render + consistency).
- `warnings`, `errors`.

## 6) Luong xu ly chi tiet

### G1 - Input validation

- Validate profile `strict_contract_v1` hoac `legacy_member1`.
- Normalize ve canonical format noi bo (`HH:MM:SS.mmm`, stable ids, trimmed text).
- Fail voi `SCHEMA_*`, `TIME_*` neu sai.

### G2 - Alignment

- Sort stable transcripts/captions.
- Two-pointer matching + adaptive `delta`.
- Tie-break deterministic: match type -> distance -> start som hon -> stable order.
- Tinh confidence bucket va warning triggers.
- Enforce invariant artifact:
  - `schema_version=1.1`
  - moi caption phai co 1 block ket qua
  - neu `fallback_type=no_match` -> `dialogue_text="(khong co)"` va `matched_transcript_ids=[]`
- Output `alignment_result.json`.

### G3 - Context build

- Build merged context block:
  - `[Image @HH:MM:SS.mmm]: ...`
  - `[Dialogue]: ...`
- Luu metadata `fallback_type`, `confidence`, trace ids.
- Output `context_blocks.json`.

### G4 - Summarization

- Prompt builder theo `prompt-template.md`.
- Long-context chunking neu vuot token budget.
- Retry policy 3 lan: infer -> JSON repair -> neutral fallback.
- Validate internal output schema + grounding checks.
- Deterministic default:
  - `do_sample=false`
  - `seed` co dinh theo run config
  - log `model_version` + `tokenizer_version` trong `generation_meta`.

### G5 - Segment planning

- Tao segments theo role (`setup`, `development`, `resolution`) cho internal lane.
- Enforce duration policy:
  - min 1200ms, max 15000ms
  - tong duration theo budget config (`min/max` va ratio neu bat)
- Mapping sang deliverable script/manifest.

### G6 - Manifest consistency

- Schema validation (contract lane by default).
- Cross-file checks:
  - unique + strict increasing segment ids
  - script_ref ton tai
  - timestamp script/manifest khop
  - non-overlap timeline
  - range trong source duration

### G7 - Video assembly

- Cat/ghep theo manifest, giu audio goc.
- Retry 1 lan voi safe render profile neu loi.
- Neu fallback merge segment: cap nhat lai script+manifest, validate lai truoc khi render tiep.

### G8 - QC report

- Tong hop stage results + errors/warnings.
- Compute/recompute metrics alignment de doi chieu report.
- Enforce thresholds khi bat strict QA.
- Output `quality_report.json`.
- Rule fail-fast cho `overall_status`:
  - Neu bat ky gate fail => `overall_status=fail`
  - Neu khong fail gate blocker => `overall_status=pass`.

### Final summary (optional deliverable)

- Sinh `final_summary.json` sau G8 chi khi `emit_final_summary=true`.
- Nguon du lieu:
  - `plot_summary`, `moral_lesson` lay tu deliverable `summary_script.json`
  - `full_combined_context_used` lay tu context da dung o G4.
- Validate theo `contracts/v1/template/final_summary.schema.json`.

## 7) Error code & handling

- `SCHEMA_*`: payload/schema errors
- `TIME_*`: timestamp/range/order errors
- `ALIGN_*`: matching/grounding alignment errors
- `LLM_*`: infer/parse/repair errors
- `MANIFEST_*`: script-manifest consistency errors
- `BUDGET_*`: underflow/overflow duration budget
- `RENDER_*`: ffmpeg/codec/audio errors
- `QC_*`: threshold/consistency errors

## 8) Config can expose

- Alignment: `k`, `min_delta`, `max_delta`
- Summarization: `seed`, `do_sample` (default `false`), `temperature`, `max_new_tokens`, `model_version`, `tokenizer_version`
- Chunking: `max_blocks_per_chunk`, `chunk_overlap_blocks`, `low_confidence_prune_threshold`
- Segment budget: `min_segment_duration_ms`, `max_segment_duration_ms`, `min_total_duration_ms`, `max_total_duration_ms`, `target_ratio`, `target_ratio_tolerance`
- QC: `enforce_thresholds`, `metric_tolerance`
- Runtime controls: `run_id`, `artifacts_root`, `emit_internal_artifacts`, `emit_final_summary`

## 9) Test strategy

### Unit tests

- `timecode.py`: parse/format/roundtrip + invalid cases
- `matcher.py`: containment/nearest/tie-break determinism
- `budget_policy.py`: underflow/overflow/ratio tolerance
- `cross_file_checks.py`: overlap, id order, ref mismatch

### Integration tests

- Happy path: strict contract lane pass full G1->G8
- Internal debug lane pass
- Negative fixtures:
  - overlap
  - budget overflow
  - no_match consistency
  - metric mismatch

### Regression tests

- Replay run voi cung seed/config cho output on dinh.
- Verify khong leak internal fields vao deliverable.

## 10) SLO/KPI cho implementation

- Functional:
  - `parse_validity_rate >= 0.995`
  - `timeline_consistency_score >= 0.90`
  - `grounding_score >= 0.85`
  - `manifest_consistency_pass = true`
  - `render_success = true`
  - `audio_present = true`
  - `black_frame_ratio <= 0.02`
  - `no_match_rate <= 0.30`
  - `median_confidence >= 0.60`
  - `high_confidence_ratio >= 0.50`
- Runtime (baseline theo doi trong giai doan dau):
  - `p95_align_latency_ms`
  - `p95_summarize_latency_ms`
  - `tokens_per_video`
  - `retry_rate_by_stage`
- Memory (bo sung gate van hanh):
  - `peak_rss_mb_by_video_bucket` (1-3, 3-10, 10+ phut)

## 11) Replayability va artifact layout

- Moi run phai co `run_id` duy nhat (uuid/ts + hash config).
- Artifact layout de xuat:
  - `artifacts/<run_id>/g1_validate/*`
  - `artifacts/<run_id>/g2_align/alignment_result.json`
  - `artifacts/<run_id>/g3_context/context_blocks.json`
  - `artifacts/<run_id>/g4_summarize/summary_script.internal.json`
  - `artifacts/<run_id>/g5_segment/{summary_script.json,summary_video_manifest.json}`
  - `artifacts/<run_id>/g7_assemble/summary_video.mp4`
  - `artifacts/<run_id>/g8_qc/quality_report.json`
- Replay mode:
  - Cho phep skip stage da co artifact hop le (verify checksum + schema).
  - Khi config/seed/model thay doi, bat buoc invalid cache stage phu thuoc.

## 12) Ke hoach trien khai theo phase

### Phase A - Core correctness

- Build `common`, `validators`, `aligner`.
- Sinh `alignment_result.json` + context.

### Phase B - LLM + segment planning

- Build `summarizer`, `segment_planner`.
- Sinh `summary_script.internal.json` + mapping sang `summary_script.json` + `summary_video_manifest.json`.

### Phase C - Assembly + QC

- Build `assembler`, `qc`, `pipeline_runner`.
- End-to-end run + `quality_report.json` (schema-pass) + optional `final_summary.json`.

### Phase D - Hardening

- Add negative matrix tests va CI checks.
- Tune perf/memory baselines.

## 13) Dinh nghia hoan tat (Definition of Done)

- Full G1->G8 pass tren happy-path dataset.
- Tat ca negative fixtures fail dung error group.
- Deliverables pass global contracts, khong leak internal fields.
- Quality report khop artifact metrics trong tolerance.
- Co command CI de chay validation matrix va tra exit code dung.

## 14) Traceability matrix toi thieu (gate -> check)

- G1: parse + schema + timestamp invariant -> `SCHEMA_*`, `TIME_*`.
- G2: alignment deterministic + schema `alignment_result` + quality triggers -> `ALIGN_*`.
- G3: context format/order + traceability -> `ALIGN_*`/`QC_*`.
- G4: JSON-only infer + grounding + internal schema pass -> `LLM_*`, `ALIGN_*`.
- G5: budget/coverage/ratio policy + deliverable mapping -> `BUDGET_*`.
- G6: cross-file consistency + contract schemas -> `MANIFEST_*`.
- G7: render + audio policy + fallback profile -> `RENDER_*`.
- G8: recompute metrics + threshold enforcement + overall_status -> `QC_*`.
