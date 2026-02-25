# Implementation Plan - Module 3 (Reasoning-NLP)

## 1) Muc tieu implementation

- Hoan thien pipeline Module 3 theo gate G1 -> G8 o muc production-ready, khong chi dung o MVP deterministic.
- Dam bao contract-first: deliverable lane tuan thu `contracts/v1/template/`, internal lane cho reasoning/QA/debug.
- Fail-fast, deterministic, replayable theo `run_id`, co invalidation dung theo dependency tung stage.
- Dong bo voi Module 1+2 qua fixtures chung va CI gates bat buoc.

## 2) Current status (as-is) va gap can dong

Da co:

- Kien truc stage-based day du: aligner, summarizer, segment_planner, assembler, qc, validators, common, config.
- Pipeline G1->G8 chay duoc end-to-end, co replay mode theo `run_id`.
- Schema validation cho artifacts + cross-file consistency checks.
- Render video that bang `ffmpeg` va probe output co audio/duration.
- Test suite unit + integration co ban dang pass.

Chua dat (gap uu tien cao):

- G4 summarizer chua dung LLM that (van heuristic/fallback deterministic).
- G5 segment planning chua toi uu theo content/budget thuc te, merge/fallback policy chua day du.
- G8 QC metric chua "that" hoan toan (`grounding_score`, `black_frame_ratio` dang placeholder).
- `source_duration_ms` chua auto probe o duong chay chinh.
- Replay invalidation chua theo stage dependency graph (moi o config hash tong).
- CLI chua tach khoi `pipeline_runner.py`; error catalog chua chuan hoa thanh nguon trung tam.
- Chua co CI bat buoc cho test + smoke E2E + schema validate artifacts.

## 3) Nguyen tac thiet ke

- Contract-first, schema-first.
- Stage isolation: moi stage co input/output ro rang, replay doc lap duoc.
- Deterministic by default (`seed` co dinh, infer params duoc log va hash).
- Fail-fast on blocker, warning cho phep tiep tuc khi policy cho phep.
- Khong chen internal fields vao deliverable lane.
- Observable-by-default: moi stage ghi metric + log co `run_id`.

## 4) Kien truc module muc tieu (updated)

```
reasoning_nlp/
  __init__.py
  cli.py
  pipeline_runner.py
  config/
    defaults.py
  common/
    errors.py
    error_catalog.py
    io_json.py
    logging.py
    metrics.py
    timecode.py
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
    scoring.py
  assembler/
    manifest_builder.py
    ffmpeg_runner.py
    audio_policy.py
    video_probe.py
  qc/
    metrics.py
    report_builder.py
```

## 5) Mapping gate -> component

- G1 `validate`: `validators.input_validator` + `assembler.video_probe` (source duration)
- G2 `align`: `aligner.normalize` + `aligner.matcher` + `aligner.confidence`
- G3 `context_build`: `aligner.context_builder`
- G4 `summarize`: `summarizer.*` (LLM client + retry/repair + grounding)
- G5 `segment_plan`: `segment_planner.*` (content scoring + budget optimizer)
- G6 `manifest`: `validators.cross_file_checks` + `validators.artifact_validator`
- G7 `assemble`: `assembler.*`
- G8 `qc`: `qc.metrics` + `qc.report_builder` + `pipeline_runner`

## 6) Interface hop dong giua cac stage

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
  - `run_meta.json` (bat buoc cho replay)
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

Ma tran gate -> input/artifact toi thieu:

- G1 `validate`: 2 JSON input + `raw_video.mp4`; probe `source_duration_ms` bang ffprobe.
- G2 `align`: input da normalize tu G1, output `alignment_result.json`.
- G3 `context_build`: `alignment_result.json`, output `context_blocks.json`.
- G4 `summarize`: `context_blocks.json`, output `summary_script.internal.json`.
- G5 `segment_plan`: `summary_script.internal.json`, output `summary_script.json` + `summary_video_manifest.json`.
- G6 `manifest`: `summary_script.json` + `summary_video_manifest.json`.
- G7 `assemble`: `raw_video.mp4` + `summary_video_manifest.json`, output `summary_video.mp4` + `render_meta.json`.
- G8 `qc`: tong hop artifacts G1->G7, output `quality_report.json`.

## 7) Luong xu ly chi tiet (chi tiet hoan thien)

### G1 - Input validation + source probe

- Validate profile `strict_contract_v1` hoac `legacy_member1`.
- Normalize canonical format noi bo (`HH:MM:SS.mmm`, stable ids, trimmed text).
- Probe `source_duration_ms` bang ffprobe tu `raw_video.mp4`.
- Neu probe fail: fail-fast `TIME_SOURCE_VIDEO_INVALID` (khong tiep tuc stage sau).

### G2 - Alignment

- Sort stable transcripts/captions.
- Two-pointer matching + adaptive `delta`.
- Tie-break deterministic: match type -> distance -> start som hon -> stable order.
- Enforce invariant artifact:
  - `schema_version=1.1`
  - moi caption phai co 1 block ket qua
  - neu `fallback_type=no_match` -> `dialogue_text="(khong co)"` va `matched_transcript_ids=[]`

### G3 - Context build

- Build merged context block format `[Image @HH:MM:SS.mmm]` + `[Dialogue]`.
- Luu metadata `fallback_type`, `confidence`, trace ids.

### G4 - Summarization (LLM that)

- Prompt builder theo `prompt-template.md` + chunking neu vuot token budget.
- LLM provider abstraction (`transformers`/`vllm`), timeout va retry backoff.
- Retry policy 3 tang:
  1) infer structured JSON,
  2) parse repair theo schema-aware fixer,
  3) constrained regeneration; neu van fail -> neutral fallback co flag.
- Grounding checks bat buoc:
  - `evidence.timestamps` phai ton tai trong context.
  - claim unsupported phai duoc gan `LLM_GROUNDING_*`.
- `generation_meta` bat buoc co: model, tokenizer, seed, temperature, retry_count, latency_ms, token_count.

### G5 - Segment planning (nang cap chat luong)

- Scoring segment candidate theo:
  - confidence,
  - dialogue/image signal,
  - novelty,
  - temporal spread.
- Enforce duration policy:
  - min 1200ms, max 15000ms,
  - tong duration theo budget (`min/max` + ratio/tolerance neu bat).
- Merge/fallback policy:
  - overflow -> merge/trim theo priority,
  - underflow -> expand voi context block tiep can,
  - overlap -> resolve truoc khi map deliverable.
- Dam bao role coverage (`setup`, `development`, `resolution`) khi du context.

### G6 - Manifest consistency

- Schema validation lane deliverable.
- Cross-file checks:
  - unique + strict increasing segment ids,
  - script_ref ton tai,
  - timestamp script/manifest khop,
  - non-overlap timeline,
  - range trong `source_duration_ms` da probe.

### G7 - Video assembly

- Cat/ghep theo manifest, giu audio goc.
- Retry 1 lan voi safe render profile neu loi.
- Neu fallback merge segment: cap nhat script+manifest, validate lai truoc render tiep.

### G8 - QC report (metric that)

- Tong hop stage results + errors/warnings.
- Compute metric that:
  - `no_match_rate`, `median_confidence`, `high_confidence_ratio` tu alignment,
  - `grounding_score` tu evidence coverage/claim support,
  - `duration_match_score` tu output duration vs expected,
  - `black_frame_ratio` tu frame sampling (ffmpeg/ffprobe pipeline),
  - `timeline_consistency_score`, `compression_ratio`, render/audio/decode metrics.
- Enforce thresholds khi bat strict QA.
- `overall_status` phai khop stage failures.

### Final summary (optional deliverable)

- Sinh `final_summary.json` sau G8 chi khi `emit_final_summary=true`.
- Validate theo `contracts/v1/template/final_summary.schema.json`.

## 8) Replayability va invalidation policy

- Moi run co `run_id` duy nhat + `run_meta.json`.
- Dung stage dependency hash (khong chi 1 hash tong):
  - doi input/checksum -> invalidate G1+
  - doi align config -> invalidate G2+
  - doi model/tokenizer/seed/temperature -> invalidate G4+
  - doi budget -> invalidate G5+
  - doi QC thresholds -> invalidate G8
- Replay chi skip stage khi:
  - artifact ton tai,
  - schema pass,
  - stage hash khop,
  - dependency artifacts hop le.

## 9) Error code & handling

- `SCHEMA_*`: payload/schema errors
- `TIME_*`: timestamp/range/order/probe errors
- `ALIGN_*`: matching/grounding alignment errors
- `LLM_*`: infer/parse/repair/grounding errors
- `MANIFEST_*`: script-manifest consistency errors
- `BUDGET_*`: underflow/overflow duration budget
- `RENDER_*`: ffmpeg/codec/audio errors
- `QC_*`: threshold/consistency errors

Yeu cau maintainability:

- Tap trung hoa error catalog (`common/error_catalog.py` hoac tai lieu map code -> mo ta -> remediation).
- Khong hardcode metric placeholder trong pipeline runtime.

## 10) Config can expose

- Alignment: `k`, `min_delta`, `max_delta`
- Summarization: `seed`, `do_sample` (default `false`), `temperature`, `max_new_tokens`, `model_version`, `tokenizer_version`, `timeout_ms`, `max_retries`
- Chunking: `max_blocks_per_chunk`, `chunk_overlap_blocks`, `low_confidence_prune_threshold`
- Segment budget: `min_segment_duration_ms`, `max_segment_duration_ms`, `min_total_duration_ms`, `max_total_duration_ms`, `target_ratio`, `target_ratio_tolerance`
- QC: `enforce_thresholds`, `metric_tolerance`, `black_frame_sample_fps`
- Runtime controls: `run_id`, `artifacts_root`, `emit_internal_artifacts`, `emit_final_summary`, `replay_mode`

## 11) CLI va maintainability refactor

- Tach CLI parser/router tu `pipeline_runner.py` sang `reasoning_nlp/cli.py`.
- `pipeline_runner.py` chi giu orchestration logic va pure functions.
- Tang typing: dataclass config ro rang, helper return types day du.
- Chuan hoa exception handling va thong diep loi cho CLI.

## 12) Test strategy (muc tieu production)

### Unit tests

- `timecode.py`: parse/format/roundtrip + invalid cases
- `matcher.py`: containment/nearest/tie-break determinism
- `budget_policy.py`: underflow/overflow/ratio tolerance
- `cross_file_checks.py`: overlap, id order, ref mismatch
- `summarizer/*`: retry/repair/grounding negative cases
- `qc/metrics.py`: grounding/duration/black-frame metric cases

### Integration tests

- Happy path strict contract lane pass full G1->G8.
- Replay happy path + replay mismatch matrix:
  - input checksum change,
  - model/tokenizer change,
  - seed/temperature change,
  - budget change,
  - qc threshold change.
- Auto source-duration probe path (khong truyen tay `source_duration_ms`).

### Smoke E2E

- 1 testcase video ngan chay G1->G8 trong CI.
- Sau khi run, bat buoc validate artifacts bang `docs/Reasoning-NLP/schema/validate_artifacts.py`.

### Regression tests

- Replay run voi cung seed/config cho output on dinh.
- Verify khong leak internal fields vao deliverable.
- Verify CLI route (`python -m reasoning_nlp.cli`) cho stage g3/g5/g8.

## 13) CI/CD gates bat buoc

Workflow bat buoc cho moi PR:

1. Unit tests.
2. Integration tests.
3. Smoke E2E G1->G8 (sample video ngan).
4. Artifact schema + cross-file validation script.

Neu bat ky gate fail -> PR khong duoc merge.

## 13.1) Colab notebook strategy (Module 1, 2, 3, full system)

Muc tieu:

- Sau khi hoan thien du an, co bo `.ipynb` de chay rieng tung module va chay full pipeline 3 module tren Google Colab de tan dung phan cung GPU.

Danh sach notebook bat buoc:

- `notebooks/module1_extraction_colab.ipynb`
- `notebooks/module2_perception_colab.ipynb`
- `notebooks/module3_reasoning_colab.ipynb`
- `notebooks/full_pipeline_m1_m2_m3_colab.ipynb`

Yeu cau chung cho moi notebook:

- Co cell setup moi truong (Python deps, ffmpeg, model deps neu can).
- Co cell mount Google Drive va khai bao bien duong dan input/output.
- Co cell run pipeline chinh + log `run_id`.
- Co cell validate schema artifacts (contracts + internal schema tuy lane).
- Co cell preview ket qua (JSON summary + playable video neu co).
- Co cell cleanup artifact tam va huong dan download output.

I/O mapping tren Colab:

- Module 1 notebook:
  - Input: `raw_video.mp4`
  - Output: `audio_16k.wav`, `keyframes/`, `scene_metadata.json`
- Module 2 notebook:
  - Input: output Module 1
  - Output: `audio_transcripts.json`, `visual_captions.json`
- Module 3 notebook:
  - Input: output Module 2 + `raw_video.mp4`
  - Output: `summary_script.json`, `summary_video_manifest.json`, `summary_video.mp4`, `quality_report.json`
- Full system notebook:
  - Input: `raw_video.mp4`
  - Output: full artifacts Module 1->2->3 theo `run_id`

Colab hardware policy:

- Ho tro CPU, T4/L4/A100 (neu co).
- Tu dong detect GPU (`torch.cuda.is_available()`), chon backend phu hop.
- Co fallback CPU mode neu khong co GPU.
- Ghi ro expected runtime theo hardware profile.

Notebook QA gate:

- Moi notebook phai chay thanh cong end-to-end tren 1 sample video ngan.
- Bat buoc co buoc `validate_artifacts.py` cho outputs Module 3.
- Neu schema fail hoac gate fail thi notebook phai dung voi error ro rang.

CI/doc integration:

- Them muc trong README de tro den 4 notebooks.
- Them smoke check toi thieu cho notebook command-equivalent (khong bat buoc execute full notebook trong CI).
- Dong bo command CLI va notebook parameters de tranh drift.

## 14) Tich hop lien module (Module 1+2+3)

- Tao fixtures chung contract lane cho handoff:
  - happy fixture,
  - overlap fixture,
  - out-of-range fixture,
  - no_match consistency fixture.
- Dung chung bo fixtures trong test cua Module 2 va Module 3 de khoa contract.
- Rule: sai schema/contract => fail ngay tai CI.

## 15) SLO/KPI cho implementation va van hanh

Functional baseline:

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

Runtime/ops baseline:

- `p95_align_latency_ms`
- `p95_summarize_latency_ms`
- `p95_total_pipeline_latency_ms`
- `retry_rate_by_stage`
- `render_success_rate`

## 16) Vanh hanh production

- Structured logging theo `run_id`, `stage`, `status`, `error_code`, `duration_ms`.
- Metrics export (json/csv) theo run va aggregate theo ngay.
- Artifact retention policy:
  - giu full artifact cho run fail,
  - run pass giu theo TTL.
- Alerting khi gate fail hoac metric duoi threshold.

## 17) Ke hoach trien khai theo phase (P0 -> P3)

### P0 - Correctness hardening (uu tien cao nhat)

- Thay G4 heuristic bang LLM that + retry/repair/grounding.
- Auto probe `source_duration_ms`.
- Thay metric placeholder o G8 bang compute that.

Output can dat:

- Khong con metric placeholder.
- Test moi cho G4/G8 pass.

### P1 - Replay + refactor maintainability

- Stage dependency hash + replay invalidation matrix.
- Tach CLI sang `reasoning_nlp/cli.py`.
- Chuan hoa error catalog.

Output can dat:

- Replay mismatch tests pass.
- Pipeline runner gon hon, typed ro hon.

### P2 - CI + cross-module integration

- Them workflow CI bat buoc.
- Them smoke E2E + schema validation gate.
- Them fixtures chung lien module.

Output can dat:

- PR gate day du xanh.
- Contract handoff duoc khoa bang test.

### P3 - KPI + release readiness

- Batch evaluate KPI tren dataset.
- Hoan thien runbook, troubleshooting, deployment checklist, rollback checklist.
- Chot alerting + retention policy.

Output can dat:

- Co bao cao KPI that.
- San sang release theo checklist.

## 18) Dinh nghia hoan tat (Definition of Done)

- Full G1->G8 pass tren happy-path dataset.
- Tat ca negative fixtures fail dung error group.
- Deliverables pass global contracts, khong leak internal fields.
- `quality_report` metric khop artifact recompute trong tolerance.
- Replay mismatch matrix pass day du.
- CI gates (unit + integration + smoke E2E + schema validate) deu pass.
- Co tai lieu van hanh/release/rollback day du.

## 19) Traceability matrix toi thieu (gate -> check)

- G1: parse + schema + timestamp invariant + source probe -> `SCHEMA_*`, `TIME_*`.
- G2: alignment deterministic + schema `alignment_result` + quality triggers -> `ALIGN_*`.
- G3: context format/order + traceability -> `ALIGN_*`/`QC_*`.
- G4: JSON-only infer + retry/repair + grounding + internal schema pass -> `LLM_*`, `ALIGN_*`.
- G5: content-aware planning + budget/coverage/ratio + deliverable mapping -> `BUDGET_*`.
- G6: cross-file consistency + contract schemas -> `MANIFEST_*`.
- G7: render + audio policy + fallback profile -> `RENDER_*`.
- G8: metric that + threshold enforcement + overall_status -> `QC_*`.
