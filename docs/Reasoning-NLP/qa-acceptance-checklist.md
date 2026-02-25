# QA Acceptance Checklist - Module 3 (Reasoning + NLP)

Tai lieu nay la checklist nghiem thu theo tung gate cho pipeline trong `docs/Reasoning-NLP/`.

## Huong dan su dung

- QA chay theo thu tu gate tu G1 den G8.
- Gate fail thi dung pipeline, ghi `error_code`, khong bo qua.
- Moi gate can luu bang chung (artifact, log, screenshot neu can).

## Gate map

- G1: Input validation (`validate`)
- G2: Alignment (`align`)
- G3: Context build (`context_build`)
- G4: LLM summarization (`summarize`)
- G5: Segment planning (`segment_plan`)
- G6: Manifest consistency (`manifest`)
- G7: Video assembly (`assemble`)
- G8: Final quality report (`qc`)

## Severity policy

- Blocker: fail gate va dung pipeline.
- Warning: cho phep tiep tuc, nhung phai ghi vao `quality_report.warnings`.
- Info: chi log, khong tac dong pass/fail.

## G1 - Input validation

Muc tieu: xac nhan input hop le truoc khi xu ly.

Checklist:

- [ ] `audio_transcripts.json` parse JSON thanh cong.
- [ ] `visual_captions.json` parse JSON thanh cong.
- [ ] `raw_video.mp4` ton tai, doc duoc, va co duration hop le (>0).
- [ ] Timestamp dung format `HH:MM:SS.mmm`.
- [ ] Transcript co `start < end`, khong am.
- [ ] Text field bat buoc khong rong sau trim (neu rong phai danh dau theo policy).
- [ ] Input fail dung voi ma loi dung nhom (`SCHEMA_*`, `TIME_*`).

Pass criteria:

- 100% input fields bat buoc hop le.
- Neu fail, error code + field path ro rang.

## G2 - Alignment

Muc tieu: can chinh audio-visual dung rule deterministic.

Checklist:

- [ ] Parse va sort timeline stable.
- [ ] Delta duoc tinh theo adaptive policy, nam trong `[min_delta, max_delta]`.
- [ ] Moi caption co block ket qua voi `fallback_type` hop le.
- [ ] `confidence` moi block nam trong [0,1].
- [ ] Tie-break duoc ap dung dung thu tu uu tien.
- [ ] `alignment_result.json` pass schema `schema/alignment_result.schema.json`.
- [ ] Theo doi metric alignment: `no_match_rate`, `median_confidence`, `high_confidence_ratio`.
- [ ] Block alignment tang dan theo `timestamp` va consistency fallback (`no_match` -> `dialogue_text="(khong co)"`, `matched_transcript_ids=[]`).

Pass criteria:

- Khong co caption bi mat block.
- Artifact alignment parse duoc, dung schema, co `schema_version=1.1`.

## G3 - Context build

Muc tieu: tao merged context dung format cho infer.

Checklist:

- [ ] Block format dung: `[Image @HH:MM:SS.mmm]` + `[Dialogue]`.
- [ ] Thu tu block tang dan theo timestamp.
- [ ] Cac block `no_match` duoc gan `(khong co)` dung quy uoc.
- [ ] Metadata confidence/fallback luu du trong artifact.

Pass criteria:

- Context khong hong thu tu.
- Co the truy vet tu context sang alignment block.

## G4 - LLM summarization

Muc tieu: sinh tom tat grounded, parse-safe.

Checklist:

- [ ] Output internal chi la JSON, khong chen text ngoai.
- [ ] Internal output co day du key: `plot_summary`, `moral_lesson`, `quality_flags`, `evidence`.
- [ ] `plot_summary` va `moral_lesson` khong rong sau trim.
- [ ] `evidence.timestamps` ton tai trong context.
- [ ] Retry/repair policy duoc ap dung neu parse fail.
- [ ] Internal artifact (`summary_script.internal.json` neu xuat) pass `docs/Reasoning-NLP/schema/summary_script.internal.schema.json`.

Pass criteria:

- Parse-validity >= 99.5% tren bo test nghiem thu.
- Khong co hallucination ro rang trong mau spot-check.

## G5 - Segment planning

Muc tieu: chon segment hop ly, co budget va coverage.

Checklist:

- [ ] Segment sap theo `segment_id` tang dan.
- [ ] Moi segment thoa min/max duration policy.
- [ ] Tong duration nam trong budget he thong.
- [ ] Segment timeline khong overlap bat thuong.
- [ ] Coverage su kien (mo dau, dien bien, ket) duoc dam bao trong noi dung segment.
- [ ] `summary_script.json` pass `contracts/v1/template/summary_script.schema.json`.

Pass criteria:

- Khong co segment duration am/0.
- Co du cover nhung moc noi dung trong tam cua video.

## G6 - Manifest consistency

Muc tieu: dam bao script-manifest dong bo truoc render.

Checklist:

- [ ] `summary_video_manifest.json` pass `contracts/v1/template/summary_video_manifest.schema.json`.
- [ ] Moi `script_ref` ton tai trong `summary_script.segments.segment_id`.
- [ ] `source_start/source_end` giua script va manifest khop theo segment.
- [ ] `segment_id` unique trong moi file.
- [ ] `segment_id` tang dan nghiem ngat trong moi file.
- [ ] Tat ca timestamps nam trong range video nguon.
- [ ] Timeline script/manifest khong overlap segment.

Pass criteria:

- `manifest_consistency_pass = true`.
- Khong co `MANIFEST_*` error.

## G7 - Video assembly

Muc tieu: render video summary thanh cong voi audio goc.

Checklist:

- [ ] Cat/ghep dung thu tu segment.
- [ ] `source_video_path` trong `summary_video_manifest.json` tro den file nguon hop le (`raw_video.mp4` hoac duong dan da config).
- [ ] `keep_original_audio=true` va audio co mat trong output.
- [ ] Retry render/fallback duoc kich hoat dung rule neu loi.
- [ ] Output `summary_video.mp4` playable.
- [ ] Khong co decode error nghiem trong.

Pass criteria:

- `render_success = true`.
- `audio_present = true`.
- `decode_error_count = 0` (hoac <= nguong he thong).

## G8 - Final quality report

Muc tieu: tong hop ket qua va metric de go/no-go.

Checklist:

- [ ] `quality_report.json` pass schema `schema/quality_report.schema.json`.
- [ ] Co du `stage_results`, `metrics`, `warnings`, `errors`.
- [ ] `overall_status` phu hop voi ket qua cac gate.
- [ ] Metric bat buoc co gia tri hop le.
- [ ] Co metric alignment bo sung (`no_match_rate`, `median_confidence`, `high_confidence_ratio`).
- [ ] Co metric consistency check: metric trong `quality_report.metrics` khop voi metric recompute tu artifact (trong tolerance he thong).

Pass criteria:

- Gate nao fail thi `overall_status=fail`.
- Khong co sai lech giua log stage va quality report.

## Rule cross-check voi contract global

- [ ] Deliverable I/O (`summary_script.json`, `summary_video_manifest.json`, `final_summary.json` neu xuat) validate theo `contracts/v1/template/`.
- [ ] Khong chen metadata noi bo (`quality_flags`, `evidence`, `confidence`, `role`, `generation_meta`) vao deliverable neu schema global khong cho phep.

## KPI gate de xuat (release baseline)

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

## Mau ket luan QA

- Ket qua: `PASS` hoac `FAIL`
- Run id:
- Gate fail (neu co):
- Error codes:
- Khuyen nghi hanh dong tiep theo:
