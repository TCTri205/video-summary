# Module 1 - Data Extraction

## Nhiem vu

1. Tach audio thanh `audio_16k.wav` (16kHz, mono).
2. Tach keyframes bang PySceneDetect.
3. Resize anh ve `448x448` hoac `336x336`.
4. Tao `scene_metadata.json` theo schema v1.

## Output
- `audio_16k.wav`
- `keyframes/`
- `scene_metadata.json`

## Quy uoc timestamp va ten file

- Timestamp: `HH:MM:SS.mmm`.
- Keyframe file: `keyframes/frame_HH_MM_SS_mmm.jpg`.
- Metadata map 1-1 giua timestamp va file_path.

## Goi y tuning scene detect cho hoat hinh

- Khoi tao:
  - `threshold`: 30-40
  - `min_scene_len`: 20-40 frame
- Neu keyframe qua nhieu: tang `threshold` hoac `min_scene_len`.
- Neu sot canh: giam nhe 2 tham so tren.

## Tieu chi ban giao Module 1

- `scene_metadata.json` pass schema.
- `total_keyframes` dung so luong thuc te.
- Anh da resize dong nhat kich thuoc.
