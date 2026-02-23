# QA Checklist

## A. Contract validation

- [ ] `scene_metadata.json` pass `contracts/v1/scene_metadata.schema.json`.
- [ ] `audio_transcripts.json` pass `contracts/v1/audio_transcripts.schema.json`.
- [ ] `visual_captions.json` pass `contracts/v1/visual_captions.schema.json`.
- [ ] `summary_script.json` pass `contracts/v1/summary_script.schema.json`.
- [ ] `summary_video_manifest.json` pass `contracts/v1/summary_video_manifest.schema.json`.

## B. Timestamp quality

- [ ] Tat ca timestamp dung `HH:MM:SS.mmm`.
- [ ] Khong co timestamp thieu milliseconds.
- [ ] `start <= end` cho moi transcript segment.
- [ ] Du lieu transcript sap xep tang dan theo `start`.

## C. Alignment quality

- [ ] Caption duoc map voi transcript phu hop theo timeline.
- [ ] Khong vo merge khi gap khoang trong khong co thoai.
- [ ] Context merge giu dung thu tu thoi gian.

## D. Output quality

- [ ] `summary_script.json` co du title, plot_summary, moral_lesson, segments.
- [ ] `summary_video.mp4` phat duoc va co audio goc.
- [ ] Noi dung video tom tat khop voi script segments.

## E. Member 2 deep checklist

- [ ] Da chay checklist chi tiet cua Module 3 tai `docs/02-member-2-reasoning-nlp/qa-acceptance-checklist.md`.
- [ ] Deliverable I/O (`summary_script.json`, `summary_video_manifest.json`) duoc validate bang `contracts/v1/*.schema.json`.
- [ ] Artifact noi bo (neu co) duoc tach rieng, khong chen vao deliverable I/O.
