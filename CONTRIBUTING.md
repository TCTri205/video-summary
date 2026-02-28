# Contributing Guide

## Branching

- Lam viec tren feature branch, merge vao `main` qua pull request.
- Dat ten branch goi y:
  - `member1/<task-name>`
  - `member2/<task-name>`

## Contract discipline

- Khong doi key name trong JSON neu chua bump version contract.
- Deliverable lien module phai pass schema trong `contracts/v1/template/`; artifact noi bo phai pass schema trong `docs/Reasoning-NLP/schema/`.
- Timestamp phai dung `HH:MM:SS.mmm`.
- Deliverable publish cuoi bat buoc: `deliverables/<run_id>/summary_video.mp4` + `deliverables/<run_id>/summary_text.txt`.
- `summary_video.mp4` phai duoc cat/ghep tu video goc va giu audio goc theo manifest.

## Commit messages

- Dung commit ro nghia, vi du:
  - `docs: standardize timestamp to HH:MM:SS.mmm`
  - `contracts: add v1 schemas and examples`

## Pull request checklist

- [ ] Khong pha vo contract v1.
- [ ] Cap nhat docs neu thay doi behavior.
- [ ] Co test/validation voi sample data.
- [ ] `summary_script.json` va `summary_video_manifest.json` pass schema.
