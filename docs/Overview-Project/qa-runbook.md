# QA Runbook (Member 1 -> Member 2)

Tai lieu nay la ban chay nhanh de 2 thanh vien dung chung mot quy trinh QA toi thieu, co the copy/paste command.

## 1) Member 1 - Truoc handoff

Muc tieu: dam bao input cho Module 3 hop le truoc khi ban giao.

Chuan bi 2 file:

- `audio_transcripts.json`
- `visual_captions.json`

Command check semantic timestamp/timeline:

```bash
python -c "import json,re,sys,pathlib; ts=re.compile(r'^\d{2}:[0-5]\d:[0-5]\d\.\d{3}$');
def to_ms(s):
 h,m,rest=s.split(':'); sec,ms=rest.split('.'); return ((int(h)*60+int(m))*60+int(sec))*1000+int(ms)
ok=True
a=json.loads(pathlib.Path('audio_transcripts.json').read_text(encoding='utf-8'))
prev=-1
for i,x in enumerate(a,1):
 s,e=x.get('start',''),x.get('end','')
 if not ts.match(s) or not ts.match(e): print(f'FAIL TIME_FORMAT audio[{i}]'); ok=False; continue
 sm,em=to_ms(s),to_ms(e)
 if sm>em: print(f'FAIL TIME_ORDER audio[{i}]'); ok=False
 if sm<prev: print(f'FAIL TIME_SORT audio[{i}]'); ok=False
 prev=sm
v=json.loads(pathlib.Path('visual_captions.json').read_text(encoding='utf-8'))
prev=-1
for i,x in enumerate(v,1):
 t=x.get('timestamp','')
 if not ts.match(t): print(f'FAIL TIME_FORMAT visual[{i}]'); ok=False; continue
 tm=to_ms(t)
 if tm<prev: print(f'WARN TIME_SORT visual[{i}]')
 prev=tm
print('PASS handoff semantic checks' if ok else 'FAIL handoff semantic checks')
sys.exit(0 if ok else 1)"
```

Dieu kien handoff:

- Exit code `0`.
- Khong co dong `FAIL`.

## 2) Member 2 - Sau handoff

Muc tieu: validate deliverable theo global contract + cross-file + quality gates.

Can co artifact toi thieu:

- `alignment_result.json`
- `summary_script.json`
- `summary_video_manifest.json`
- `quality_report.json`

Command validate tong hop:

```bash
python docs/Reasoning-NLP/schema/validate_artifacts.py \
  --alignment alignment_result.json \
  --script summary_script.json \
  --manifest summary_video_manifest.json \
  --report quality_report.json \
  --contracts-dir contracts/v1/template \
  --source-duration-ms <SOURCE_DURATION_MS> \
  --enforce-thresholds
```

Dieu kien pass:

- In ra `Validation passed: schema + cross-file + quality checks`.
- Exit code `0`.

## 3) Ket luan run

Mau ghi ket qua:

- Ket qua: `PASS` hoac `FAIL`
- Run id:
- Nguoi chay:
- Gate fail (neu co):
- Error codes:
- Artifact evidence:

## 4) Rule fail-fast

- Bat ky gate nao fail thi dung pipeline va sua dung nhom loi (`SCHEMA_*`, `TIME_*`, `MANIFEST_*`, `QC_*`) truoc khi chay lai.
