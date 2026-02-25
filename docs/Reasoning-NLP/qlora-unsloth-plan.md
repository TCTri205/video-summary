# QLoRA Unsloth Plan

## Muc tieu

Fine-tune Qwen2.5 de tao output tom tat on dinh theo van phong mong muon, tang grounding, giam hallucination, va giu parse-validity cao.

## Data source policy (dong bo voi contract lane)

- Deliverable lane (`summary_script.json`, `summary_video_manifest.json`, `final_summary.json`) chi dung cho nghiem thu lien module.
- Training target mo rong (`evidence`, `quality_flags`, `generation_meta`) lay tu internal lane:
  - `summary_script.internal.json`
  - `alignment_result.json`
  - `quality_report.json`
- Khong dung `final_summary.json` de chua field mo rong ngoai global schema.

## Du lieu huan luyen de xuat

Moi sample:

- `instruction`: yeu cau tom tat va rut bai hoc
- `input`: merged context da align (`full_combined_context_used`)
- `output`: `plot_summary` + `moral_lesson` + `evidence` (+ `quality_flags` neu can)
- `metadata`: `source_video_id`, `schema_version`, `quality_label`, `run_id`

## Data governance (bat buoc)

- Version dataset theo release (`dataset_version`).
- Deduplicate sample trung/lien quan cao (near-duplicate).
- Kiem tra leakage train/validation/test theo `source_video_id`.
- Chia split theo video id (khong split theo doan random trong cung 1 video).
- Loai bo sample parse fail, grounding thap, hoac quality flag nghiem trong.

## Quy trinh

1. Thu thap output chat luong tu pipeline that (uu tien run pass full QA gate).
2. Human QA spot-check va gan `quality_label`.
3. Lam sach, dedup, va loai bo sample kem chat luong.
4. Chia train/validation/test theo video id, seed co dinh.
5. Train bang Unsloth (QLoRA).
6. Danh gia theo benchmark co dinh:
   - Do dung cot truyen
   - Do ro rang bai hoc
   - Do nhat quan van phong
   - Grounding va parse-validity

## Eval protocol

- Luon so voi baseline model truoc khi fine-tune.
- Chay metric tu dong + human spot-check co checklist thong nhat.
- Bao cao theo tung domain video de tranh overfit cuc bo.

## Release gate

Chi promote adapter neu dong thoi dat:

- Parse-validity khong giam so voi baseline.
- Grounding score tang hoac bang baseline.
- Quality trung binh (human rating) tang co y nghia.
- Khong phat sinh regression nghiem trong trong bo test hoi quy.

## Reproducibility

- Luu day du: `seed`, `lr`, `epoch`, `max_seq_len`, `batch_size`, `lora_rank`, `lora_alpha`.
- Luu hash artifact model + config train/infer.
- Co script tai lap infer tren benchmark co dinh.

## Dau ra huan luyen

- LoRA adapter weights
- Cau hinh train va infer
- Ghi chu thong so va hash artifact
- Bao cao benchmark truoc/sau fine-tune
