# Pipeline Flow and Grounding

Tai lieu nay mo ta luong du lieu thuc te trong runtime G1->G8, cach he thong tom tat video, va cach sinh van ban tom tat co grounded provenance.

## 1) End-to-end flow

```mermaid
flowchart TD
    A[audio_transcripts.json\nvisual_captions.json\nraw_video.mp4] --> B[G1 validate]
    B --> C[G2 align\nmatch caption-transcript\nconfidence+fallback]
    C --> D[G3 context_build\ncontext_blocks.json]
    D --> E[G4 summarize\nsummary_script.internal.json]
    D --> F[G5 segment_plan\nsummary_script.json\nsummary_video_manifest.json]
    E --> F
    F --> G[G7 assemble\nsummary_video.mp4]
    F --> H[Build summary_text.internal.json\nfrom selected segments]
    H --> I[Build summary_text.txt\nfrom grounded sentences]
    G --> J[G8 QC\nquality_report.json]
    I --> J
    J --> K[deliverables/<run_id>/\nsummary_video.mp4\nsummary_text.txt]
```

## 2) Logic view (video vs text)

```text
INPUTS
  |- transcripts
  |- captions
  |- raw_video

ALIGN + CONTEXT
  |- context_blocks[timestamp, image_text, dialogue_text, confidence, fallback_type]

VIDEO SUMMARY LANE
  |- planner scores context blocks
  |- planner computes dynamic target_count and segment durations
  |- summary_script.json + summary_video_manifest.json
  |- ffmpeg render -> summary_video.mp4

TEXT SUMMARY LANE (grounded)
  |- read selected segments from summary_script.json
  |- build summary_text.internal.json
  |    |- sentences[].text
  |    |- sentences[].support_segment_ids
  |    |- sentences[].support_timestamps
  |- build summary_text.txt from sentences[]

QC LANE
  |- classic metrics: parse/timeline/grounding/compression/audio/render
  |- consistency metrics: grounded_ratio/coverage/order/overlap/cta_leak
```

## 3) Grounding contract for summary text

- Muc tieu: text cuoi phai bam vao segment da render video, khong drift.
- Nguon su that cuoi: `summary_script.json` (segments da chon).
- Moi cau trong `summary_text.internal.json` phai co provenance:
  - `support_segment_ids`
  - `support_timestamps`
- `summary_text.txt` duoc sinh tu `summary_text.internal.json`, khong sinh truc tiep tu `plot_summary/moral_lesson`.

## 4) Dynamic segment planning (runtime behavior)

- Planner tinh `target_total_ms` tu budget + duration video (neu co ratio thi uu tien ratio).
- Planner suy ra `target_count` dong, khong hard-cap 3.
- Planner chon anchor theo bucket coverage mem + diversity penalty.
- Duration moi segment duoc chia theo remaining budget va clamp trong min/max duration.
- CTA/noise/prompt leakage duoc phat hien va giam uu tien.

## 5) Consistency metrics in quality_report

Ngoai cac metric co san, report co them:

- `text_sentence_grounded_ratio`
- `text_segment_coverage_ratio`
- `text_temporal_order_score`
- `text_video_keyword_overlap`
- `text_cta_leak_ratio`

Nhung metric nay dung de bat mismatch giua video summary va summary text.

## 6) Sequence diagram (runtime call flow)

```mermaid
sequenceDiagram
    participant CLI as reasoning_nlp.cli
    participant Runner as pipeline_runner
    participant Align as aligner/*
    participant Summ as summarizer/*
    participant Planner as segment_planner/planner.py
    participant Asm as assembler/*
    participant QC as qc/*

    CLI->>Runner: run_pipeline_g1_g8(config)
    Runner->>Runner: G1 validate + normalize input
    Runner->>Align: G2 match captions/transcripts + confidence
    Align-->>Runner: alignment_result + blocks
    Runner->>Align: G3 build_context_blocks
    Align-->>Runner: context_blocks
    Runner->>Summ: G4 generate_internal_summary
    Summ-->>Runner: summary_script.internal.json
    Runner->>Planner: G5 plan_segments_from_context
    Planner-->>Runner: summary_script.json + manifest
    Runner->>Asm: G7 render_summary_video(ffmpeg)
    Asm-->>Runner: summary_video.mp4 + render_meta
    Runner->>Runner: build summary_text.internal.json from selected segments
    Runner->>Runner: build summary_text.txt from grounded sentences
    Runner->>QC: G8 compute metrics + enforce thresholds
    QC-->>Runner: quality_report.json
    Runner-->>CLI: deliverables + artifact paths
```
