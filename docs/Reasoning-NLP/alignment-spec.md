# Alignment Spec (Merge Timeline)

## Bai toan

Ghep transcript (`start`, `end`) voi visual captions (`timestamp`) tren cung truc thoi gian, tao merged context co confidence de dung cho summarization.

## Input invariants (bat buoc)

- Tat ca timestamp phai parse duoc theo `HH:MM:SS.mmm`.
- Transcript bat buoc co `start < end`, gia tri khong am.
- Caption bat buoc co `timestamp` hop le.
- Text transcript/caption sau khi trim khong rong; neu rong thi gan co `is_empty_text=true` de xu ly fallback.
- Payload fail bat ky invariant nao thi dung stage voi `TIME_*`/`SCHEMA_*`.

## Input profile (de tich hop voi du lieu hien tai)

- `strict_contract_v1`:
  - `audio_transcripts.json` theo `contracts/v1/template/audio_transcripts.schema.json`.
  - `visual_captions.json` theo `contracts/v1/template/visual_captions.schema.json`.
- `legacy_member1`:
  - Transcript dang object `{language, duration, segments[]}`.
  - `segments[].start/end` co the la float giay.
- Ca 2 profile deu phai normalize ve canonical format noi bo truoc khi merge.

## Chuan hoa truoc khi merge

- Parse tat ca timestamp thanh milliseconds.
- Neu transcript dang float giay, chuyen thanh timestamp string `HH:MM:SS.mmm` roi parse ms.
- Sap xep transcript theo `start` tang dan (stable sort).
- Sap xep captions theo `timestamp` tang dan (stable sort).
- Gan `transcript_id`, `caption_id` neu input chua co id.
- Optional de giam token/noise:
  - Gop transcript lien tiep rat ngan neu cung nguoi noi va khoang cach nho.
  - Dedup caption gan nhau neu caption text trung nghia va timestamp sat nhau.

## Delta policy (adaptive, thay cho fixed delta)

- Muc dich: giam mismatch khi pace video thay doi.
- Cong thuc de xuat:
  - `median_transcript_duration_ms = median(end - start)`
  - `delta_raw = k * median_transcript_duration_ms`
  - `delta = clamp(delta_raw, min_delta, max_delta)`
- Mac dinh:
  - `k = 1.2`
  - `min_delta = 1500`
  - `max_delta = 6000`

## Luat ghep (deterministic)

Voi moi caption tai moc `t`:

1. **Containment match**: tim transcript thoa `start <= t <= end`.
2. Neu khong co containment, **nearest-time match** trong cua so `|t - boundary| <= delta`.
   - `boundary`: khoang cach nho nhat den 2 bien transcript, `distance_ms = min(|t-start|, |t-end|)`.
3. Neu van khong co, gan dialogue la `(khong co)` va `fallback_type = no_match`.

### Tie-break rule khi co nhieu transcript hop le

Uu tien theo thu tu:

1. Candidate co `match_type` manh hon (`containment` > `nearest`).
2. Khoang cach thoi gian den `t` nho nhat.
3. `start` som hon.
4. Thu tu xuat hien trong file (stable).

## Implementation note (hieu nang)

- Khuyen nghi thuc thi bang two-pointer tren 2 mang da sort (`transcripts`, `captions`).
- Muc tieu complexity:
  - Typical: `O(N + M)`
  - Worst-case co tie-break scan bo sung: van can gioi han cua so tim kiem theo `delta` de tranh `O(N*M)`.

## Confidence scoring

Moi ket qua match can co `confidence` trong [0,1]:

- `containment_bonus`: +0.45 neu containment.
- `distance_score`: `max(0, 1 - (distance_ms / delta)) * 0.45`.
- Runtime hien tai khong dung `lexical_bonus`.
- Neu `fallback_type=no_match` thi `confidence=0`.
- Chuan hoa score ve [0,1].

Ghi chu roadmap: co the bo sung `lexical_bonus` trong tuong lai neu bo keyword/tokenizer duoc khoa version de giu deterministic.

Confidence buckets:

- `high`: `>= 0.75`
- `medium`: `0.45 - 0.74`
- `low`: `< 0.45`

## Format context merge

Moi block theo timestamp:

- `[Image @HH:MM:SS.mmm]: <caption>`
- `[Dialogue]: <text hoac (khong co)>`

Metadata block (khong bat buoc dua vao prompt, nhung bat buoc luu artifact):

- `caption_id`
- `matched_transcript_ids`
- `fallback_type` (`containment`, `nearest`, `no_match`)
- `confidence`

Noi cac block theo thu tu tang dan theo thoi gian.

## Output artifact alignment

Tao `alignment_result.json` theo schema toi thieu:

```json
{
  "schema_version": "1.1",
  "delta_ms": 3200,
  "blocks": [
    {
      "caption_id": "c_001",
      "timestamp": "00:00:06.000",
      "image_text": "...",
      "dialogue_text": "...",
      "matched_transcript_ids": ["t_005"],
      "fallback_type": "containment",
      "confidence": 0.91
    }
  ]
}
```

## Quality triggers sau alignment

- Neu `no_match_rate > 0.30`: gan warning `ALIGN_LOW_MATCH_COVERAGE`, kich hoat summarize mode bao thu (neutral style + confidence-aware context truncation).
- Neu `median_confidence < 0.60`: gan warning `ALIGN_LOW_CONFIDENCE`.
- Neu `high_confidence_ratio < 0.50`: gan warning `ALIGN_WEAK_GROUNDING_SIGNAL`.

## Chuyen tu alignment sang script/video

- Sau khi merge context, truyen context + metadata sang summarization.
- Segment planning phai dua tren timeline da align, khong chon segment ngoai input.
- Tao `summary_script.json` va `summary_video_manifest.json` dong bo segment.
- Render `summary_video.mp4` bang cach cat/ghep tu `raw_video.mp4`, giu audio goc (`keep_original_audio: true`).

## Edge cases

- Nhieu transcript cung phu hop 1 caption: ap dung tie-break rule; neu can noi, gioi han toi da 240 ky tu, uu tien cau hoan chinh.
- Timestamp trung nhau: giu thu tu xuat hien trong file (stable).
- Caption rong text: van tao block, `image_text = "(khong co)"`, confidence giam.
- Transcript overlap bat thuong: ghi `ALIGN_OVERLAP_WARNING` trong quality report.
