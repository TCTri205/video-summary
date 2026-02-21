# QA Checklist

## A. Contract validation

- [ ] `scene_metadata.json` pass `contracts/v1/scene_metadata.schema.json`.
- [ ] `audio_transcripts.json` pass `contracts/v1/audio_transcripts.schema.json`.
- [ ] `visual_captions.json` pass `contracts/v1/visual_captions.schema.json`.
- [ ] `final_summary.json` pass `contracts/v1/final_summary.schema.json`.

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

- [ ] `final_summary.json` co du 3 truong bat buoc.
- [ ] Plot summary dung trinh tu su kien.
- [ ] Moral lesson ro rang va lien quan noi dung.
