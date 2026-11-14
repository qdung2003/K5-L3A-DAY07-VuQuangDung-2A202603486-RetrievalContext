# Code

Pipeline Day 7 dung model that va vector store Day 6:

- `day6_store.py`: MiniLM 384 chieu va xac minh snapshot Chroma Day 6.
- `retrievers.py`: dense Chroma, lexical TF-IDF, hybrid RRF; Hit@1/Hit@3/context.
- `agent_run.py`: model goi search, context budget, citation, abstention va trace.
- `evaluation.py`: tong hop nhan da doi chieu, context 0/1/2, token/thoi gian/loi.
- `legacy/`: code demo hash/heuristic cu; khong dung cho ket qua nop.

Lenh chay va quy trinh dev -> chot -> test: [RUNBOOK](../RUNBOOK.md).
