# Reasoning-NLP: Cách tính score segment, chọn đoạn cắt video, và tạo summary text cuối

Tài liệu này mô tả chi tiết luồng thực thi trong `reasoning_nlp/` để trả lời 3 câu hỏi:

1. Score cho từng context block/segment được tính như thế nào
2. Các block nào được chọn để cắt và ghép thành video tóm tắt
3. Đoạn văn tóm tắt cuối cùng (`summary_text.txt`) được tạo ra sao

Nội dung dưới đây được đối chiếu trực tiếp từ source code hiện tại.

---

## 1) Tổng quan pipeline liên quan đến scoring và segment selection

Pipeline chạy theo chuỗi stage:

- G1 `validate`: chuẩn hóa input + đo thời lượng video gốc
- G2 `align`: canh caption với transcript, tính `fallback_type`, `distance_ms`, `confidence`
- G3 `context_build`: tạo `context_blocks`
- G4 `summarize`: gọi LLM tạo `summary_internal` (title/plot/moral/evidence), sau đó planner chọn segment
- G5 `segment_plan`: xuất 2 artifact deliverable (`summary_script.json`, `summary_video_manifest.json`)
- G6 `manifest`: cross-check consistency script/manifest
- G7 `assemble`: ffmpeg cat/concat tạo `summary_video.mp4`
- G8 `qc`: tính metric và xuất deliverable cuối (`summary_video.mp4`, `summary_text.txt`)

File chính:

- `reasoning_nlp/pipeline/stages/g2_align.py`
- `reasoning_nlp/aligner/matcher.py`
- `reasoning_nlp/aligner/confidence.py`
- `reasoning_nlp/aligner/context_builder.py`
- `reasoning_nlp/segment_planner/planner.py`
- `reasoning_nlp/segment_planner/content_scoring.py`
- `reasoning_nlp/pipeline/stages/g4_summarize.py`
- `reasoning_nlp/pipeline/stages/g5_segment.py`
- `reasoning_nlp/assembler/ffmpeg_runner.py`
- `reasoning_nlp/pipeline/orchestrator.py`

---

## 2) Dữ liệu đầu vào cho planner: `context_blocks`

Sau G2 và G3, mỗi block có các trường cốt lõi:

- `timestamp`: mốc canh (caption time)
- `image_text`: text caption hình
- `dialogue_text`: lời thoại transcript được match
- `fallback_type`: `containment` | `nearest` | `no_match`
- `confidence`: điểm [0..1] từ alignment

`context_blocks` là "đơn vị" được chấm điểm và chọn.

Lưu ý quan trọng: planner chấm điểm trên `context_block`, không chấm điểm trực tiếp trên output text do LLM viết.

---

## 3) Cách tính `confidence` ở alignment (upstream của planner)

Tại `reasoning_nlp/aligner/matcher.py`:

- Caption được tìm transcript candidate trong cửa sổ `delta_ms`
- Nếu timestamp nằm trong [start, end] transcript -> `fallback_type = containment`
- Nếu không nằm trong span nhưng gần trong `delta_ms` -> `fallback_type = nearest`
- Nếu không tìm thấy -> `fallback_type = no_match`

Tại `reasoning_nlp/aligner/confidence.py`, công thức:

```text
if delta_ms <= 0: confidence = 0

containment_bonus = 0.45 nếu fallback_type == "containment", ngược lại = 0
distance_score = max(0, 1 - distance_ms/delta_ms) * 0.45

score = containment_bonus + distance_score
nếu fallback_type == "no_match" -> score = 0

confidence = clamp(round(score, 6), 0, 1)
```

Ý nghĩa:

- Match đúng trong khoảng transcript -> điểm cao hơn
- Khoảng cách timestamp càng gần -> điểm càng cao
- `no_match` -> confidence = 0

---

## 4) Cách tính score cho từng block trong planner

Planner dùng 2 lớp điểm:

1. `base_score`
2. `lexical_salience_score`

Sau đó trộn thành `composite_score`.

### 4.1) `base_score`

Tại `reasoning_nlp/segment_planner/planner.py` (`_score_block`):

```text
score = confidence

fallback_type adjustments:
- exact       => +0.10
- containment => +0.05
- nearest     => -0.10
- no_match    => -0.30

nếu text có CTA (like/comment/subscribe/đăng ký/đăng kí) => -0.50
nếu text rỗng hoặc "(không có)"                          => -0.20
```

Ghi chú:

- Nhánh `exact` có trong logic score, nhưng matcher hiện tại chủ yếu sinh `containment/nearest/no_match`.
- Penalty CTA rất mạnh để tránh đoạn boilerplate.

### 4.2) `lexical_salience_score`

Tại `reasoning_nlp/segment_planner/content_scoring.py` (`compute_lexical_salience_scores`):

Quy trình:

1. Gộp text: `dialogue_text + image_text`
2. Tokenize (`\b\w+\b`), lowercase
3. Bỏ token ngắn hơn `min_token_len`, bỏ số
4. `ascii_fold` bỏ dấu tiếng Việt (để so stopword)
5. Bỏ CTA tokens và bỏ stopwords profile `vi`
6. Tính tf theo block, df toàn bộ blocks
7. Tính score thô:

```text
score_raw(block) = sum_{token in block} tf(token,block) * idf(token)

idf(token) = log((1 + total_docs)/(1 + df(token))) + 1   (nếu lexical_use_idf=True)
idf(token) = 1                                            (nếu lexical_use_idf=False)
```

8. Min-max normalize toàn bộ block về [0,1]

Nếu không đủ điều kiện (tắt feature, không có block, stopwords profile không phải `vi`, không có token hợp lệ) -> toàn bộ lexical score = 0.

### 4.3) Trộn điểm: `composite_score`

Tại `_composite_score` trong `planner.py`:

```text
composite = base_score + effective_lexical_weight * lexical_score
```

Trong đó `lexical_score` đã được clamp [0,1].

`effective_lexical_weight` có thể bị giảm về 0 nếu block không an toàn/không hữu ích:

- text rỗng hoặc `(không có)` -> 0
- text có prompt leakage marker -> 0
- text có CTA -> 0
- `fallback_type == no_match` -> 0
- `fallback_type == nearest` -> còn `weight * 0.25`
- các trường hợp còn lại -> dùng full weight

Mặc định config (`reasoning_nlp/config/defaults.py`):

- `lexical_enabled = True`
- `lexical_weight = 0.18`
- `lexical_min_df = 1`
- `lexical_min_token_len = 2`
- `lexical_use_idf = True`
- `lexical_stopwords_profile = "vi"`

---

## 5) Cách planner chọn block để tạo segment

Hàm chính: `plan_segments_from_context(...)` trong `planner.py`.

### 5.1) Tính budget tổng thời lượng mục tiêu

`_compute_target_total_ms`:

- floor/cap theo budget (`min_total_duration_ms`, `max_total_duration_ms`), mặc định 3000..180000 ms
- nếu có độ dài video gốc:
- nếu có `target_ratio` -> `derived = source_duration * target_ratio`
- mặc định runtime hiện tại: `target_ratio = 0.10` (10%), nên nhánh fallback 3.5% chỉ dùng khi `target_ratio` bị unset thủ công
- target tổng = clamp(derived, floor, cap)

Nếu không có độ dài video gốc -> default target quanh 9000 ms trong [floor, cap].

### 5.2) Tính thời lượng segment ưu tiên và số segment mục tiêu

`_compute_preferred_segment_ms`:

- cơ sở 4000 ms
- nếu video > 15 phút -> 6000 ms
- clamp theo min/max segment duration

`_compute_target_count`:

```text
raw = round(target_total_ms / preferred_segment_ms)
target_count = clamp(raw, 1, min(total_blocks, 15))
```

### 5.3) Chọn index block (`_pick_block_indexes`)

Bước chọn có tính đến cả score và độ phủ timeline:

1. Tính `scores` cho tất cả block (base + lexical)
2. Chia dãy block thành `target` bucket theo vị trí thời gian
3. Mỗi bucket chọn 1 candidate tốt nhất với penalty nếu quá gần segment đã chọn (`diversity`)
4. Nếu chưa đủ số lượng:
   - fill bổ sung từ global top score, ưu tiên không quá gần
   - nếu vẫn thiếu thì bỏ qua ràng buộc gap để đủ số lượng
5. Hậu xử lý giảm CTA (`_reduce_cta_candidates`):
   - tìm selected nào là CTA
   - nếu có non-CTA trong pool và score cao hơn thì thay
6. Sort tăng dần theo index để giữ thứ tự thời gian

`min_gap` mặc định:

- target <= 3 -> 1
- ngược lại -> `max(1, total_blocks // (target * 3))`

Ý nghĩa:

- không chỉ lấy top điểm, mà ép có độ phủ đầu-giữa-cuối
- tránh đoạn quá sát nhau
- giảm khả năng lọt CTA vào kết quả

---

## 6) Chuyển block được chọn thành segment video cụ thể

Sau khi có `picks`, planner tạo `PlannedSegment`:

1. Lấy `anchor_ms` từ `block.timestamp`
2. Tính budget còn lại và slots còn lại để ra `dynamic_target_ms`
3. Clamp duration segment trong [min_segment_duration_ms, max_segment_duration_ms]
4. Đặt `start_ms = max(anchor_ms, prev_end_ms)` để tránh overlap
5. Đặt `end_ms = start_ms + target_segment_ms`
6. Nếu có `source_duration_ms`, tiếp tục clamp để không vượt cuối video và vẫn có độ dài tối thiểu
7. Nếu segment không đạt range hợp lệ -> bỏ qua

Mỗi segment tạo ra gồm:

- `segment_id` (1..N)
- `source_start`, `source_end`
- `script_text`
- `confidence` (copy từ block, clamp [0,1])
- `role`

### 6.1) `script_text` được lấy theo ưu tiên

`_script_text_from_block`:

1. `dialogue_text` nếu có và an toàn
2. nếu không, `image_text` nếu có và an toàn
3. nếu vẫn không được, fallback `summary_plot`

### 6.2) Gán role narrative

`assign_role(index,total)`:

- segment đầu -> `setup`
- segment cuối -> `resolution`
- giữa -> `development`

Nếu có từ 3 segment mà thiếu role nào -> fail `BUDGET_ROLE_COVERAGE`.

---

## 7) Tạo artifact để cắt video và script

Stage G5 (`g5_segment.py`) tạo:

1. `summary_script.json`
   - title, plot_summary, moral_lesson
   - danh sách segment với `segment_id`, `source_start`, `source_end`, `script_text`

2. `summary_video_manifest.json`
   - `source_video_path`, `output_video_path`, `keep_original_audio`
   - danh sách segment với `source_start`, `source_end`, `script_ref`, `transition="cut"`

Sau đó validate schema cho cả 2 artifact.

---

## 8) Cách ghép thành video tóm tắt

Stage G7 gọi `render_summary_video` (`assembler/ffmpeg_runner.py`):

- Mỗi segment được cắt video bằng `trim`
- Mỗi segment được cắt audio bằng `atrim`
- Reset timestamp từng đoạn (`setpts`/`asetpts`)
- Concat tất cả đoạn theo thứ tự
- Encode H.264 + AAC, giữ audio gốc

Sau render:

- probe độ dài video output
- check có audio stream
- tính `duration_match_score` với tổng độ dài segments mong đợi

Nếu fail profile chính, có retry profile an toàn hơn trước khi báo `RENDER_FATAL`.

---

## 9) Cách tạo `summary_text.txt` cuối cùng

Phần này nằm trong `pipeline/orchestrator.py`.

### 9.1) Tạo `summary_text_internal` từ script segments

`_build_summary_text_internal(script_payload)`:

1. Lấy danh sách segment hợp lệ và "safe"
   - bỏ segment thiếu field
   - bỏ text có hard prompt leakage
   - bỏ text giống CTA
2. Gom segment thành nhóm:
   - `n <= 3`: mỗi segment 1 nhóm
   - `4 <= n <= 6`: 2 nhóm
   - `n > 6`: 3 nhóm
3. Mỗi nhóm tạo 1 câu bằng `_build_group_sentence`:
   - lấy tối đa 2 `script_text`
   - gán lead tương đối theo vị trí nhóm (`Mở đầu`, `Tiếp theo`, `Cuối cùng`)
4. Mỗi câu giữ metadata grounding:
   - `support_segment_ids`
   - `support_timestamps`
5. Thêm thông tin coverage ids

Nếu không có câu hợp lệ -> dùng câu fallback trung tính.

### 9.2) Build chuỗi text cuối

`_build_summary_text(summary_internal_payload, script_payload, summary_text_internal)`:

- Lấy các câu từ `summary_text_internal.sentences`
- Lấy thêm `plot_summary` (nếu có)
- Lấy thêm `moral_lesson` vào mẫu câu:

```text
Nhìn từ câu chuyện này, điều đọng lại là {moral_lesson}
```

- Nối tất cả thành 1 đoạn
- Nếu quá ngắn thì bổ sung 1 câu để đạt độ dài tối thiểu
- Nếu có hard prompt leakage -> fail

Kết quả được ghi vào `deliverables/<run_id>/summary_text.txt`.

---

## 10) Các ràng buộc consistency và quality liên quan

### 10.1) Script/Manifest consistency

`validators/cross_file_checks.py` kiểm tra:

- `segment_id` tăng dần, không trùng
- timeline non-decreasing, không overlap
- `script_ref` trong manifest phải tồn tại trong script
- timestamp script và manifest phải khớp
- nếu có `source_duration_ms`, segment phải nằm trong range video gốc

### 10.2) QC metric liên quan text-video

`qc/metrics.py` tính:

- `text_sentence_grounded_ratio`
- `text_segment_coverage_ratio`
- `text_temporal_order_score`
- `text_video_keyword_overlap`
- `text_cta_leak_ratio`

Những metric này dùng để đánh giá chất lượng liên kết giữa văn bản tóm tắt và segment video đã chọn.

---

## 11) Tóm tắt công thức/logic cốt lõi

### 11.1) Score block

```text
base_score
= confidence
+ bonus/penalty theo fallback_type
- penalty CTA
- penalty empty

lexical_score = normalize( sum(tf * idf) )

composite_score = base_score + effective_lexical_weight * lexical_score
```

### 11.2) Chọn block

```text
target_total_ms -> preferred_segment_ms -> target_count

bucketized selection + diversity penalty + refill + CTA reduction

sort theo thứ tự thời gian
```

### 11.3) Tạo output

```text
segments đã chọn -> summary_script.json + summary_video_manifest.json
manifest -> ffmpeg trim/atrim/concat -> summary_video.mp4
script + plot + moral -> summary_text.txt
```

---

## 12) Nhận xét kỹ thuật quan trọng để đọc đúng hệ thống

1. Segment selection chủ yếu là deterministic và dựa trên alignment + lexical scoring, không phụ thuộc hoàn toàn vào LLM.
2. Planner ưu tiên cân bằng 2 mục tiêu: block chất lượng cao và độ phủ timeline.
3. CTA được penalty ở nhiều lớp (scoring, lexical gating, thay thế candidate, text safety).
4. `summary_text.txt` là dạng hybrid:
   - phần timeline được tổng hợp từ script segment đã chọn
   - phần plot/moral đến từ `summary_internal` (LLM output đã qua repair/check)

Tài liệu kết thúc.
