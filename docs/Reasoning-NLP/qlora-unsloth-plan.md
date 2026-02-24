# QLoRA Unsloth Plan

## Muc tieu

Fine-tune Qwen2.5 de tao output tom tat on dinh theo van phong mong muon.

## Du lieu huan luyen de xuat

Moi sample:
- `instruction`: yeu cau tom tat va rut bai hoc
- `input`: `full_combined_context_used`
- `output`: `plot_summary` + `moral_lesson`

## Quy trinh

1. Thu thap output chat luong tu pipeline that.
2. Lam sach va loai bo sample kem chat luong.
3. Chia train/validation.
4. Train bang Unsloth (QLoRA).
5. Danh gia theo:
   - Do dung cot truyen
   - Do ro rang bai hoc
   - Do nhat quan van phong

## Dau ra huan luyen

- LoRA adapter weights
- Cau hinh train va infer
- Ghi chu thong so (seed, lr, epoch, max_seq_len)
