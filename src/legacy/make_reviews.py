"""Sinh reviews nháp từ traces để chạy agent_metrics.py không lỗi.

Quy trình đúng: chạy agent_run -> sinh nháp -> BẠN ĐỌC và sửa nhãn thủ công -> chạy agent_metrics.
Nháp này đoán grade bằng cách đối chiếu citation với gold (heuristic), bạn BẮT BUỘC
mở file ra kiểm tra từng câu: citation có thực sự hỗ trợ câu trả lời không.

Chạy: python src/make_reviews.py --traces starter/results/agent-dev/traces.json --questions data/questions_answerable.json --cases data/cases.json --split dev --output data/reviews-dev.json
"""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--traces", required=True, type=Path)
    ap.add_argument("--questions", required=True, type=Path)
    ap.add_argument("--cases", required=True, type=Path)
    ap.add_argument("--split", required=True, choices=("dev", "test"))
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    traces = {t["query_id"]: t for t in json.loads(args.traces.read_text(encoding="utf-8"))}
    questions = {q["id"]: q for q in json.loads(args.questions.read_text(encoding="utf-8"))}
    # câu thiếu evidence nằm ở questions.json gốc
    full_q = {}
    for p in [args.questions, Path("data/questions.json")]:
        try:
            for q in json.loads(p.read_text(encoding="utf-8")):
                full_q.setdefault(q["id"], q)
        except FileNotFoundError:
            pass
    cases = [c for c in json.loads(args.cases.read_text(encoding="utf-8")) if c.get("split") == args.split]

    reviews = []
    for c in cases:
        cid = c["id"]
        t = traces.get(cid)
        if t is None:
            print(f"CẢNH BÁO: thiếu trace {cid}, bỏ qua")
            continue
        cits = t.get("citations", [])
        q = full_q.get(cid, {})
        gold = q.get("gold", [])
        if c["answerable"]:
            # nháp: citation đúng nếu id chunk chứa evidence gold
            support = []
            # cần map id->text: đọc chunks
            chunks = {x["id"]: x for x in json.loads(Path("data/chunks.json").read_text(encoding="utf-8"))}
            for cit in cits:
                ch = chunks.get(cit, {})
                ok = any(ch.get("source_id") == g.get("source_id") and ch.get("page") == g.get("page")
                         and g.get("evidence", "") in ch.get("text", "") for g in gold)
                support.append(ok)
            grade = 2 if (t.get("status") == "answered" and all(support) and support) else 0
            reviews.append({"query_id": cid, "answer_grade": grade, "citation_support": support,
                            "note": "NHÁP - bạn phải đọc trace và sửa grade/support thủ công"})
        else:
            correct = t.get("status") == "abstain"
            reviews.append({"query_id": cid, "abstention_correct": correct,
                            "citation_support": [False] * len(cits),
                            "note": "NHÁP - bạn phải đọc trace và sửa abstention_correct thủ công"})

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(reviews, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã sinh {len(reviews)} nhãn nháp -> {args.output}. MỞ FILE RA KIỂM TRA THỦ CÔNG trước khi chạy agent_metrics.")


if __name__ == "__main__":
    main()
