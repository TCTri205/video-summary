# Alignment Spec (Merge Timeline)

## Bai toan

Ghep transcript (`start`, `end`) voi visual captions (`timestamp`) tren cung truc thoi gian.

## Chuan hoa truoc khi merge

- Parse tat ca timestamp `HH:MM:SS.mmm` thanh milliseconds.
- Sap xep transcript theo `start` tang dan.
- Sap xep captions theo `timestamp` tang dan.

## Luat ghep de xuat

Voi moi caption tai moc `t`:
1. Tim transcript co `start <= t <= end`.
2. Neu khong co, tim segment gan nhat trong cua so `delta` (de xuat 5000 ms).
3. Neu van khong co, danh dau `Loi thoai lien quan: (khong co)`.

## Format context merge

Moi block theo timestamp:
- `[Image @HH:MM:SS.mmm]: <caption>`
- `[Dialogue]: <text hoac (khong co)>`

Noi cac block theo thu tu tang dan theo thoi gian.

## Edge cases

- Nhieu transcripts cung phu hop 1 caption: noi ngan gon theo thu tu bat dau.
- Timestamp trung nhau: giu thu tu xuat hien trong file.
