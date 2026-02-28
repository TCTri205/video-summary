# Prompt Template cho Qwen2.5-3B-Instruct

## Muc tieu

Sinh tom tat cot truyen va bai hoc tu context merge, khong them chi tiet ngoai du lieu.

Luu y contract-first:

- Output LLM o buoc nay la artifact noi bo cho reasoning.
- Deliverable lien module `summary_script.json`, `summary_video_manifest.json` (va `final_summary.json` neu xuat bo sung) phai map ve schema trong `contracts/v1/template/`.
- Runtime hien tai publish deliverable cuoi cho nguoi dung la `summary_video.mp4` + `summary_text.txt` trong `deliverables/<run_id>/`.

## Nguyen tac prompting

- Grounded-only: chi duoc dung thong tin co trong context.
- Neutral fallback: neu context thieu, phat bieu trung tinh, khong suy dien.
- Deterministic style: van phong nhat quan, ngan gon, ro rang.
- Structured output: output bat buoc dung schema noi bo, khong text ngoai JSON.

## System prompt de xuat

"Ban la tro ly tom tat video ngan theo du lieu da can chinh timeline. Nhiem vu: viet tom tat cot truyen va rut ra bai hoc nhan van ngan gon, ro rang. CHI su dung thong tin co trong context; khong bia them. Neu thong tin thieu, tra loi trung tinh. Bat buoc output JSON hop le theo schema duoc cung cap, khong chen van ban ngoai JSON."

## User prompt de xuat

Input:

- Merged context theo thu tu thoi gian.
- Moi block co format:
  - `[Image @HH:MM:SS.mmm]: ...`
  - `[Dialogue]: ...`
- Metadata bo tro (neu co): `confidence`, `fallback_type`.

Output yeu cau (payload infer toi thieu truoc parse-repair):

```json
{
  "title": "string",
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

- `title` khong duoc rong sau trim.
- `plot_summary` va `moral_lesson` khong duoc rong sau trim.
- `quality_flags` co the rong, nhung neu co phai la danh sach string.
- `evidence.timestamps` phai tham chieu moc thoi gian ton tai trong context.
- Khong duoc chen key ngoai schema neu che do strict bat buoc.

Sau parse-repair, internal artifact can co them:

- `schema_version=1.1`
- `generation_meta` (`model`, `seed`, `temperature`, `backend`, `retry_count`, `latency_ms`, `token_count`)

## Canonical mapping toi artifacts

Internal artifacts (reasoning lane):

- `plot_summary`, `moral_lesson`, `evidence`, `quality_flags` -> `summary_script.internal.json`
- `generation_meta` (model, seed, temperature, infer params) -> `summary_script.internal.json`

Deliverables (contract lane):

- `plot_summary` -> `summary_script.json.plot_summary`
- `moral_lesson` -> `summary_script.json.moral_lesson`
- Segment text -> `summary_script.json.segments[].script_text`
- Video cut plan -> `summary_video_manifest.json`
- Neu xuat `final_summary.json`: chi gom field theo `contracts/v1/template/final_summary.schema.json`

Khong duoc dua cac field noi bo sau vao deliverable:

- `evidence`
- `quality_flags`
- `generation_meta`
- `confidence`
- `role`

## Long-context policy (runtime hien tai)

- Runtime dung prompt truncation theo `--summarize-prompt-max-chars`.
- Prompt builder uu tien giu coverage dau/giua/cuoi timeline va block confidence cao.
- Chua co chunking da pha trong code runtime hien tai.

## Retry va parse-repair policy

1. Lan 1: infer binh thuong (`temperature` thap hoac `do_sample=false`).
2. Lan 2: neu parse fail, goi prompt "JSON repair" voi output loi.
3. Lan 3: neu van fail, fallback output trung tinh hop internal schema va gan `quality_flags` canh bao.

## Inference defaults de xuat (MVP deterministic)

- `do_sample=false`
- `temperature=0.1` (neu backend yeu cau)
- `max_new_tokens`: theo budget he thong
- `seed`: co dinh trong moi run

Bat buoc log infer params vao `generation_meta` de dam bao replay.

## Gate check sau infer

- Internal JSON parse-valid.
- `evidence.timestamps` hop le voi context.
- Khong hallucination ro rang trong spot-check.
- Mapping sang deliverable khong vi pham global schemas.

## Luu y

- Neu context thieu thong tin, output trung tinh.
- Giu van phong nhat quan qua nhieu video.
- Khong trich dan timestamp khong ton tai trong context.
