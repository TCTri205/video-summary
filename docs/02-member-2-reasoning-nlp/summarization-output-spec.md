# Summarization Output Spec

## Dinh dang output

`summary_script.json`:

```json
{
  "title": "...",
  "plot_summary": "...",
  "moral_lesson": "...",
  "segments": [
    {
      "segment_id": 1,
      "source_start": "00:00:06.000",
      "source_end": "00:00:13.200",
      "script_text": "..."
    }
  ]
}
```

`summary_video_manifest.json`:

```json
{
  "source_video_path": "raw_video.mp4",
  "output_video_path": "summary_video.mp4",
  "keep_original_audio": true,
  "segments": [
    {
      "segment_id": 1,
      "source_start": "00:00:06.000",
      "source_end": "00:00:13.200",
      "script_ref": 1,
      "transition": "cut"
    }
  ]
}
```

## Rule chat luong

- `plot_summary`: dung trinh tu su kien, ngan gon, co lien ket.
- `moral_lesson`: ro rang, lien quan truc tiep den noi dung.
- `segments`: duoc sap theo timeline, map duoc vao video goc.
- `summary_video.mp4`: duoc cat/ghep tu video goc va giu audio goc.

## Rule ky thuat

- File parse JSON hop le.
- Co du key bat buoc theo schema `summary_script` va `summary_video_manifest`.
- Gia tri khong rong sau khi trim.
