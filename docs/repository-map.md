# Cây thư mục - Video Summary Project

Dự án video-summary là hệ thống AI tổng hợp video theo pipeline 3 module:
- **Module 1**: Trích xuất dữ liệu (extraction)
- **Module 2**: Nhận thức AI (perception)  
- **Module 3**: Hợp nhất và suy luận (fusion/reasoning)

Đầu vào: `raw_video.mp4`  
Đầu ra cuối cùng: `summary_video.mp4`, `summary_text.txt`

Cấu trúc thư mục được tổ chức như sau:

```
video-summary/
├── .github/
│   └── workflows/
│       └── ci.yml                              # Workflow CI tự động kiểm tra
├── Data/
│   ├── mock/
│   │   ├── audio_transcripts.json            # Dữ liệu giả transcript
│   │   └── visual_captions.json              # Dữ liệu giả caption
│   └── processed/                            # Dữ liệu sau xử lý của Module 1
│       └── <tên_video>/
│           └── extraction/
│               ├── audio/
│               ├── keyframes/                # Ảnh keyframe
│               └── scene_metadata.json       # Metadata cảnh
├── artifacts/                                # Kết quả trung gian của Module 3 (G1->G8)
│   └── <run_id>/
│       ├── g2_align/
│       │   └── alignment_result.json         # Kết quả đồng bộ thời gian
│       ├── g5_segment/
│       │   ├── summary_script.json          # Script tổng hợp công khai
│       │   └── summary_video_manifest.json  # Manifest chỉ thị ghép video
│       ├── g7_assemble/
│       │   └── summary_video.mp4            # Video tổng hợp
│       ├── g8_qc/
│       │   └── quality_report.json          # Báo cáo chất lượng
│       ├── g1_validate/                      # (debug/replay opt-in)
│       ├── g3_context/                       # (debug/replay opt-in)
│       ├── g4_summarize/                     # (debug/replay opt-in)
│       ├── g6_manifest/                      # (debug/replay opt-in)
│       └── run_meta.json                     # (debug/replay opt-in)
├── contracts/
│   └── v1/
│       ├── template/                        # Schema định nghĩa giao thức
│       │   ├── *.schema.json
│       │   └── *.json                       # Ví dụ hợp lệ
│       ├── valid/                           # Dữ liệu hợp lệ mẫu
│       ├── invalid/                         # Dữ liệu không hợp lệ mẫu
│       └── README.md                        # Quy tắc thời gian và versioning
├── deliverables/                            # Kết quả cuối cho người dùng
│   └── <run_id>/
│       ├── summary_video.mp4                # Video tổng hợp
│       └── summary_text.txt                 # Văn bản tóm tắt
├── docs/                                    # Tài liệu dự án
│   ├── Overview-Project/                    # Tổng quan dự án
│   ├── Perception-Extraction/               # Hướng dẫn Module 1&2
│   └── Reasoning-NLP/                       # Hướng dẫn Module 3
│       └── schema/                          # Schema nội bộ Module 3
├── extraction_perception/                   # Mã nguồn Module 1&2
│   ├── extraction/
│   │   ├── extraction.py                    # Trích xuất dữ liệu video
│   │   └── whisper_module.py                # ASR (speech-to-text)
│   └── perception/
│       └── caption.py                       # Sinh mô tả hình ảnh
├── notebooks/                               # Phiên bản Colab
│   ├── module1_extraction_colab.ipynb
│   ├── module2_perception_colab.ipynb
│   ├── module3_reasoning_colab.ipynb
│   └── full_pipeline_m1_m2_m3_colab.ipynb
├── reasoning_nlp/                           # Mã nguồn Module 3
│   ├── pipeline/                            # Orchestrator va runtime profile cho Module 3
│   ├── cli.py                               # Giao diện dòng lệnh
│   ├── config/                              # Defaults + shared config loader
│   ├── aligner/                             # Đồng bộ hóa audio/visual
│   ├── summarizer/                          # Tóm tắt bằng LLM
│   ├── segment_planner/                     # Lập kế hoạch phân đoạn theo budget
│   ├── assembler/                           # Ghép video
│   ├── qc/                                  # Kiểm tra chất lượng
│   ├── validators/                          # Xác thực dữ liệu
│   └── common/                              # Thư viện dùng chung
├── scripts/                                 # Tiện ích hỗ trợ
│   ├── kpi_batch.py                         # Báo cáo KPI hàng loạt
│   └── benchmark_optimizations.py           # Đo hiệu năng
├── tests/                                   # Bộ kiểm thử
│   ├── unit/                                # Kiểm thử đơn vị
│   └── integration/                         # Kiểm thử tích hợp
├── main.py                                  # Entrypoint chạy toàn bộ pipeline
├── README.md                                # Giới thiệu và hướng dẫn tổng thể
├── requirements-*.txt                       # Thư viện Python theo vai trò
├── .env.bak                                 # Mẫu biến môi trường
├── .gitignore                               # Danh sách file không commit
└── CONTRIBUTING.md                          # Quy tắc đóng góp
```

---

## Mô tả chi tiết các phần chính

### `.github/workflows/ci.yml`
- Workflow CI tự động chạy kiểm thử khi push/PR

### `Data/`
- `mock/` - Dữ liệu giả dùng cho Module 2 phát triển độc lập
- `processed/` - Dữ liệu sau xử lý của Module 1, theo cấu trúc: `processed/<tên_video>/extraction/` với `audio/`, `keyframes/`, `scene_metadata.json`

### `artifacts/`
- Chứa kết quả trung gian của Module 3 theo từng bước (G1-G8)
- Mặc định giữ artifact vận hành: `g2_align/alignment_result.json`, `g5_segment/*`, `g7_assemble/summary_video.mp4`, `g8_qc/quality_report.json`
- Artifact nội bộ (`g1_validate`, `g3_context`, `g4_summarize`, `g6_manifest`, `g7_assemble/render_meta.json`, `g8_qc/summary_text.internal.json`, `run_meta.json`) chỉ ghi khi bật debug artifacts/replay

#### Ma trận artifact theo stage (mặc định)
- `g3`: `g2_align/alignment_result.json`
- `g5`: `g5_segment/summary_script.json`, `g5_segment/summary_video_manifest.json`
- `g8`: `g5_segment/summary_script.json`, `g5_segment/summary_video_manifest.json`, `g7_assemble/summary_video.mp4`, `g8_qc/quality_report.json`

### `contracts/v1/`
- Giao thức giao tiếp giữa các module (data contracts)
- `template/*.schema.json` - schema định nghĩa đầu vào/ra
- `valid/`, `invalid/` - dữ liệu hợp lệ/không hợp lệ dùng để test
- Yêu cầu định dạng thời gian: `HH:MM:SS.mmm`

### `deliverables/`
- Kết quả cuối cùng dùng cho người dùng
- `summary_video.mp4` - Video tổng hợp
- `summary_text.txt` - Văn bản tóm tắt

### `extraction_perception/`
- **Module 1 & 2**: Trích xuất và nhận thức dữ liệu
- `extraction/` - Tách âm thanh, phát hiện cảnh, trích xuất keyframe, ASR
- `perception/` - Sinh mô tả hình ảnh từ keyframe

### `reasoning_nlp/`
- **Module 3**: Hợp nhất, suy luận, và ghép video
- `pipeline/` - Chua orchestrator va cac thanh phan dieu phoi Module 3
- `cli.py` - Giao diện dòng lệnh cho pipeline
- `config/` - Mặc định runtime + shared config loader cho CLI/root entrypoint
- `aligner/` - Đồng bộ hóa thời gian audio/visual
- `summarizer/` - Tóm tắt bằng LLM
- `segment_planner/` - Lập kế hoạch segment theo budget policy
- `assembler/` - Ghép video theo manifest
- `qc/` - Kiểm tra chất lượng đầu ra
- `validators/` - Kiểm tra dữ liệu đầu vào/output
- `common/` - Thư viện dùng chung (I/O, thời gian, lỗi)

### `docs/`
- `Overview-Project/` - Kiến trúc tổng thể, quy trình tích hợp
- `Perception-Extraction/` - Hướng dẫn Module 1&2
- `Reasoning-NLP/` - Hướng dẫn Module 3, sơ đồ pipeline
- `schema/` (trong Reasoning-NLP) - Schema nội bộ của Module 3

### `tests/`
- `unit/` - Kiểm thử đơn vị cho từng hàm
- `integration/` - Kiểm thử tích hợp pipeline và CLI

### `notebooks/`
- Phiên bản notebook cho chạy trên Google Colab
- Có 4 notebook chính: `module1`, `module2`, `module3`, `full_pipeline`

### File gốc tại root
- `main.py` - Entrypoint chạy toàn bộ pipeline (M1 -> M2 -> M3)
- `README.md` - Hướng dẫn chạy và kiến trúc tổng thể
- `requirements-*.txt` - Mô tả thư viện Python theo vai trò
- `.env.bak` - Mẫu biến môi trường
- `.gitignore` - Các file không đưa lên repo
- `CONTRIBUTING.md` - Quy tắc đóng góp
- `commit_output.txt`, `git_status_output.txt` - Log dùng trong CI

### `scripts/`
- `kpi_batch.py` - Báo cáo KPI hàng loạt
- `benchmark_optimizations.py` - Đo hiệu năng
