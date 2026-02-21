# Summarization Output Spec

## Dinh dang output

`final_summary.json`:

```json
{
  "plot_summary": "...",
  "moral_lesson": "...",
  "full_combined_context_used": "..."
}
```

## Rule chat luong

- `plot_summary`: dung trinh tu su kien, ngan gon, co lien ket.
- `moral_lesson`: ro rang, lien quan truc tiep den noi dung.
- `full_combined_context_used`: luu nguyen van context merge de debug va fine-tune.

## Rule ky thuat

- File parse JSON hop le.
- Co du 3 key bat buoc.
- Gia tri khong rong sau khi trim.
