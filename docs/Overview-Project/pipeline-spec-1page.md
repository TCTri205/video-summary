# Pipeline Spec 1-Page (Chot scope)

## 1) Muc tieu he thong

Xay dung he thong tom tat video theo pipeline 3 module, tach biet trach nhiem, ghep noi bang data contract, chay on dinh voi mock data va data that.

- System input: `raw_video.mp4`
- System output chinh:
  - `deliverables/<run_id>/summary_video.mp4`
  - `deliverables/<run_id>/summary_text.txt`
- Artifact ky thuat lien module:
  - `summary_script.json`
  - `summary_video_manifest.json`
  - `summary_video.mp4` (trong `artifacts/<run_id>/g7_assemble/`)
- Optional contract artifact:
  - `final_summary.json` (neu xuat bo sung)

## 2) Y tuong tong quat

1. Tach video goc thanh 2 luong thong tin: audio va hinh anh.
2. Dung AI de chuyen audio -> transcript text, image -> visual caption text.
3. Merge 2 luong text theo timeline de tao context da phuong thuc.
4. Dung AI tao script tom tat co cau truc.
5. Cat/ghep nhieu doan tu video goc de tao video tom tat cuoi, giu audio goc.

## 3) Pham vi va nhiem vu theo module

### Module 1 - Data Extraction

- Input:
  - `raw_video.mp4`
- Output:
  - `audio_16k.wav`
  - `keyframes/*.jpg`
  - `scene_metadata.json`
- Nhiem vu:
  - Tach audio 16kHz mono.
  - Detect scene, cat keyframe theo moc thoi gian.
  - Resize keyframe theo quy uoc runtime.
  - Ghi metadata map 1-1 giua timestamp va file keyframe.

### Module 2 - Perception AI

- Input:
  - `audio_16k.wav`
  - `keyframes/*.jpg`
  - `scene_metadata.json`
- Output:
  - `audio_transcripts.json`
  - `visual_captions.json`
- Nhiem vu:
  - Chay speech-to-text tren audio.
  - Chay visual captioning tren keyframe.
  - Chuan hoa timestamp + sap xep + lam sach text.

### Module 3 - Fusion, Reasoning, Video Assembly

- Input:
  - `audio_transcripts.json`
  - `visual_captions.json`
  - `raw_video.mp4`
- Output:
  - `summary_script.json`
  - `summary_video_manifest.json`
  - `summary_video.mp4`
- Nhiem vu:
  - Align transcript + caption tren cung truc timeline.
  - Tao context hop nhat de LLM sinh script tom tat.
  - Tao manifest cat/ghep tu danh sach segment.
  - Render video tom tat tu video goc theo manifest.

## 4) Data contract va nguyen tac tich hop

- Tat ca JSON phai pass schema trong `contracts/v1/template/*.schema.json`.
- Timestamp chuan bat buoc: `HH:MM:SS.mmm`.
- Relative path trong JSON dung theo workspace root.
- Key name theo schema, khong doi tuy y.
- Fail-fast: sai schema hoac sai timestamp thi dung pipeline ngay.

## 5) Quy tac output cuoi

- `summary_script.json` phai co day du:
  - `title`
  - `plot_summary`
  - `moral_lesson`
  - `segments[]`
- `summary_video_manifest.json` phai map duoc 1-1 voi `segments` trong script.
- `summary_video.mp4`:
  - Duoc cat/ghep tu `raw_video.mp4`.
  - `keep_original_audio` bat buoc = `true`.
  - Phat duoc, co audio, noi dung khop script segment.

## 6) Definition of Done (MVP)

1. Chay thong luong end-to-end voi 1 video mau.
2. 100% file giao tiep pass schema v1.
3. Thay mock data bang data that khong can sua logic merge.
4. Tao duoc 2 deliverable cuoi:
   - `deliverables/<run_id>/summary_video.mp4`
   - `deliverables/<run_id>/summary_text.txt`
