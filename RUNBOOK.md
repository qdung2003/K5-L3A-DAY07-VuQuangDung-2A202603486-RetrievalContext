# Chay bai Day 7

Python 3.11+, PowerShell hoac POSIX. Pipeline gom dev -> doc/cham -> select -> test.
Khong chay test de chon cau hinh. Ket qua nop da co trong `results/`.

## 1. Cai dat

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/prepare_day7.py
python scripts/setup_models.py --download
```

POSIX kich hoat bang `source .venv/bin/activate`. Model MiniLM duoc tai dung
revision, kiem SHA-256 va chay local CPU. Chroma khoi phuc tu vector Day 6 that
trong `src/day6_index.json`; khong can thu muc project Day 6 tren may nguoi cham.
Nguon, license, unit/offset: `data/SOURCES.md`. Cache nam trong `.cache/`, khong nop.

Dat `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL` trong `.env` theo mau.
`OPENAI_REASONING_EFFORT` tuy chon, mac dinh `low`. Environment process uu tien
hon file. Agent va AI audit dung cung cau hinh; co the truyen `--env-file <path>`.
Khong commit `.env`. Tham so retrieval nam trong `configs/experiments.json`;
model va reasoning thuc dung duoc luu trong `run.json` moi lan chay.

## 2. Kiem tra bai da nop, khong ton API

```powershell
python -m unittest discover -s tests -v
python scripts/verify_submission.py
python scripts/experiment.py dev --resume
python scripts/experiment.py select --resume
python scripts/cost_report.py
```

Hai lenh `dev/select --resume` kiem chung frozen artifacts va khong ghi de ket qua
hay goi model. `cost_report.py` tinh lai tu snapshot gia va usage, khong goi model.
Khong can tao lai `selection.json` da nop.

## 3. Chay mot thi nghiem moi trong thu muc rieng

Vi du dung `.runs/replay-01` (duoc Git ignore):

```powershell
python scripts/experiment.py dev --results-root .runs/replay-01 --resume
python scripts/audit_answers.py --split dev --results-root .runs/replay-01 --resume
python scripts/review_labels.py export --split dev --results-root .runs/replay-01 --file .runs/dev-review.json
```

Doc form cung trace va nguon goc. Dien `reviewer`, `reviewer_type` (`human` hoac
`ai`) dung thuc te; sua grade/support/ly do trong `decision`, chi dat `approved`
thanh true sau khi da doi chieu. Khong tu nhan human review cho nhan AI.
Form giu SHA-256 tung trace; importer tu choi nhan cu, trung hoac chua chap nhan.

```powershell
python scripts/review_labels.py import --split dev --results-root .runs/replay-01 --file .runs/dev-review.json
python scripts/experiment.py select --results-root .runs/replay-01
python scripts/experiment.py test --results-root .runs/replay-01 --resume
python scripts/audit_answers.py --split test --results-root .runs/replay-01 --resume
python scripts/review_labels.py export --split test --results-root .runs/replay-01 --file .runs/test-review.json
```

Doc/duyet test form nhu dev, sau do:

```powershell
python scripts/review_labels.py import --split test --results-root .runs/replay-01 --file .runs/test-review.json
python scripts/cost_report.py --results-root .runs/replay-01
python scripts/verify_submission.py --results-root .runs/replay-01
```

Ca 5 cau hinh cung corpus/model/dev; test chi baseline va cau hinh duoc chon.
Select luu hash dev, cam sua sau khi chot. Runner khong ghi de traces da co neu
thieu `--resume`; resume cung tu choi model/prompt/corpus/query thay doi.
Ket qua moi hoan toan tach `results/` cua bai nop. Thu muc thi nghiem co the di
chuyen sang may khac vi selection dung path tuong doi.

Day la tai lap tren benchmark da cong khai, khong phai mot test an doc lap moi.
Neu dung test de tinh chinh thi can benchmark test moi; khong sua frozen inputs
hoac tu nhan ket qua do la danh gia doc lap.

## 4. Chi phi

`results/costs.json` luu uoc tinh USD theo tung cau hinh/split cho agent va AI
audit, kem hash trace/nhan. Snapshot gia `data/pricing/modelapi-gpt-6.1-sol.json`
duoc lay tu bang gia cong khai ModelAPI, giu thoi diem, URL va bieu thuc billing.
Token cache duoc tinh rieng; nguong context ap dung tung request, khong ap tong batch.

```powershell
python scripts/cost_report.py
python scripts/cost_report.py --fetch-pricing --pricing .runs/pricing-today.json --results-root .runs/replay-01
```

Lenh thu hai chi tai gia cong khai tu host trong `.env`, khong gui key va khong goi
model. Tuy chon `--pricing <file>` cho phep dung rate card da kiem chung khac.
Model khac rate card se bi tu choi. Gia truoc he so nhom la uoc tinh; he so tai
khoan/khuyen mai/don gia lich su chua xac minh. Bang khong phai hoa don, khong
gom du moi probe/lan judge loi thieu usage. Summary/trace cu giu nguyen hash va
`cost_usd: null` lich su; chi phi bo sung nam trong `costs.json`.

## 5. Demo tren web

```powershell
.\.venv\Scripts\python.exe web/app.py
```

Mo <http://127.0.0.1:8765>. Chon **Saved trace** de demo cau tra loi, citation,
score va search da luu ma khong ton API. Chon **Live model** de nhap cau hoi moi;
che do nay dung `.env` va co the phat sinh chi phi. Nen demo `T02`, `T-U02` va `Q01`.

## 6. Bai nop

Code, nguon duoc phep chia se, vector export, config, benchmark, trace, nhan,
metrics, gia va bao cao nam trong repo. Bao cao:
`report/individual/2A202603486_VuQuangDung.md`.

Nhan da duoc AI judge ho tro va Codex doc doi chieu, ghi dung nguon nguoi/AI
cham. `results/author_review_pending.csv` la phieu tuy chon de tac gia ghi them
xac nhan, khong phai mau bat buoc rieng cua de; khong dien ho tac gia.
Khong tu nhan da nop link qua kenh lop hoac giang vien da duoc cap quyen.

PowerShell helper: `.\scripts\run.ps1 -Stage verify -ResultsRoot results`.
POSIX helper: `bash scripts/run_all.sh verify results`.
`starter/results/` va cac thu muc `legacy` la demo cu, khong dung de bao diem.
Phan nang cao 100 trang +15 diem la tuy chon va khong nam trong bai co ban nay.
