# Data Contracts

Tai lieu nay dinh nghia format giao tiep giua cac module.
Nguon chuan machine-checkable nam tai `contracts/v1/*.schema.json`.

## Quy tac timestamp (bat buoc)

- Dinh dang: `HH:MM:SS.mmm`.
- Vi du hop le: `00:00:15.240`, `01:12:03.005`.
- Tat ca moc thoi gian (`timestamp`, `start`, `end`) phai dung chung dinh dang.

## scene_metadata.json

```json
{
  "total_keyframes": 2,
  "frames": [
    {
      "frame_id": 1,
      "timestamp": "00:00:15.240",
      "file_path": "keyframes/frame_00_00_15_240.jpg"
    },
    {
      "frame_id": 2,
      "timestamp": "00:01:20.100",
      "file_path": "keyframes/frame_00_01_20_100.jpg"
    }
  ]
}
```

Bat buoc:
- `total_keyframes` = `frames.length`.
- `frame_id` la so nguyen tang dan, bat dau tu 1.
- `file_path` la relative path.

## audio_transcripts.json

```json
[
  {
    "start": "00:00:10.000",
    "end": "00:00:18.500",
    "text": "Uoc gi minh co chiec dien thoai do."
  },
  {
    "start": "00:02:30.000",
    "end": "00:02:45.120",
    "text": "Con co biet tai sao cay tam gui lai chet khong?"
  }
]
```

Bat buoc:
- Danh sach duoc sap xep tang dan theo `start`.
- `start` <= `end`.
- `text` khong rong sau khi trim.

## visual_captions.json

```json
[
  {
    "timestamp": "00:00:15.240",
    "caption": "Cau be mat buon ba nhin qua cua kinh cua hang dien thoai."
  },
  {
    "timestamp": "00:02:40.010",
    "caption": "Nguoi cha chi tay vao mot nhanh cay kho heo bam tren than cay lon."
  }
]
```

Bat buoc:
- Moi phan tu co `timestamp` va `caption`.
- `caption` khong rong sau khi trim.

## summary_script.json

```json
{
  "title": "Bai hoc ve gia tri ben trong",
  "plot_summary": "Video ke ve mot cau be khao khat chiec dien thoai dat tien nhung sau chuyen di cung cha...",
  "moral_lesson": "Hanh phuc khong nam o vat chat phu phiem ben ngoai ma o gia tri ben trong.",
  "segments": [
    {
      "segment_id": 1,
      "source_start": "00:00:06.000",
      "source_end": "00:00:13.200",
      "script_text": "Cau be khao khat mot chiec dien thoai dat tien."
    }
  ]
}
```

Bat buoc:
- Co du 4 khoa: `title`, `plot_summary`, `moral_lesson`, `segments`.
- `segments` khong rong va moi segment co timestamp hop le.

## summary_video_manifest.json

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

Bat buoc:
- `keep_original_audio` phai la `true`.
- `segments` phai map duoc toi `summary_script.json` qua `script_ref`.

## final_summary.json (internal, optional)

File nay chi dung cho debug/fine-tune noi bo, khong phai deliverable cuoi.
