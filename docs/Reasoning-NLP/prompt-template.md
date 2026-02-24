# Prompt Template cho Qwen2.5-3B-Instruct

## Muc tieu

Sinh tom tat cot truyen va bai hoc tu context merge, khong them chi tiet ngoai du lieu.

## System prompt de xuat

"Ban la tro ly tom tat video ngan. Hay tao tom tat cot truyen ro rang va rut ra bai hoc nhan van, ngan gon, de hieu. Khong bịa them tinh tiet ngoai context."

## User prompt de xuat

Input:
- Toan bo context merge theo thu tu thoi gian
- Moi block dung format `[Image @HH:MM:SS.mmm]` va `[Dialogue]`

Output yeu cau:
- JSON object gom 2 khoa:
  - `plot_summary`
  - `moral_lesson`

## Luu y

- Neu context thieu thong tin, output trung tinh.
- Giu van phong nhat quan qua nhieu video.
