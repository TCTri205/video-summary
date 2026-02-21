# Contributing Guide

## Branching

- Lam viec tren feature branch, merge vao `main` qua pull request.
- Dat ten branch goi y:
  - `member1/<task-name>`
  - `member2/<task-name>`

## Contract discipline

- Khong doi key name trong JSON neu chua bump version contract.
- Mọi output phai pass schema trong `contracts/v1/` truoc khi ban giao.
- Timestamp phai dung `HH:MM:SS.mmm`.

## Commit messages

- Dung commit ro nghia, vi du:
  - `docs: standardize timestamp to HH:MM:SS.mmm`
  - `contracts: add v1 schemas and examples`

## Pull request checklist

- [ ] Khong pha vo contract v1.
- [ ] Cap nhat docs neu thay doi behavior.
- [ ] Co test/validation voi sample data.
