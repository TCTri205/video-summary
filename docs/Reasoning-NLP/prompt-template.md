# Prompt Template cho Qwen2.5-3B-Instruct

## Muc tieu

Sinh tom tat cot truyen va bai hoc tu context merge, khong them chi tiet ngoai du lieu.

Luu y contract-first:

- Output LLM o buoc nay la artifact noi bo cho reasoning.
- Deliverable cuoi `summary_script.json` va `summary_video_manifest.json` phai map ve schema trong `contracts/v1/`.

## Nguyen tac prompting

- Grounded-only: chi duoc dung thong tin co trong context.
- Neutral fallback: neu context thieu, phat bieu trung tinh, khong suy dien.
- Deterministic style: van phong nhat quan, ngan gon, ro rang.
- Structured output: output bat buoc dung schema, khong text ngoai JSON.

## System prompt de xuat

"Ban la tro ly tom tat video ngan theo du lieu da can chinh timeline. Nhiem vu: viet tom tat cot truyen va rut ra bai hoc nhan van ngan gon, ro rang. CHI su dung thong tin co trong context; khong bia them. Neu thong tin thieu, tra loi trung tinh. Bat buoc output JSON hop le theo schema duoc cung cap, khong chen van ban ngoai JSON."

## User prompt de xuat

Input:

- Merged context theo thu tu thoi gian.
- Moi block co format:
  - `[Image @HH:MM:SS.mmm]: ...`
  - `[Dialogue]: ...`
- Metadata bo tro (neu co): `confidence`, `fallback_type`.

Output yeu cau (schema toi thieu):

```json
{
  "plot_summary": "string",
  "moral_lesson": "string",
  "quality_flags": [],
  "evidence": [
    {
      "claim": "string",
      "timestamps": ["HH:MM:SS.mmm"]
    }
  ]
}
```

Rang buoc:

- `plot_summary` va `moral_lesson` khong duoc rong sau trim.
- `quality_flags` co the rong, nhung neu co phai la danh sach string.
- `evidence` phai tham chieu moc thoi gian ton tai trong context.
- Khong duoc chen key ngoai schema neu che do strict bat buoc.

## Mapping sang deliverable contract v1

- `plot_summary` -> `summary_script.plot_summary`
- `moral_lesson` -> `summary_script.moral_lesson`
- `evidence` va `quality_flags` luu trong artifact noi bo (`final_summary.json`/`quality_report.json`), khong chen vao `summary_script.json` deliverable.

## Long-context policy

- Neu context vuot token budget:
  1. Chia chunk theo timeline (co overlap nho).
  2. Tom tat tung chunk theo cung schema.
  3. Tong hop global summary tu cac chunk summaries.
- Uu tien block confidence cao khi can rut gon.

## Retry va parse repair policy

1. Lan 1: infer binh thuong (`temperature` thap).
2. Lan 2: neu parse fail, goi prompt "JSON repair" voi output loi.
3. Lan 3: neu van fail, fallback output trung tinh hop schema va gan `quality_flags` canh bao.

## Inference defaults de xuat

- `temperature`: 0.1
- `top_p`: 0.9
- `max_new_tokens`: theo budget he thong
- `seed`: co dinh trong moi run de dam bao reproducibility

## Luu y

- Neu context thieu thong tin, output trung tinh.
- Giu van phong nhat quan qua nhieu video.
- Khong trich dan timestamp khong ton tai trong context.
