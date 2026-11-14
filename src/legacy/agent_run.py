"""Agent chạy thật trên vector store Day 6 (offline, không mock).

- Retriever: dense search trên src/day6_index.json (cùng hàm embed -> tương thích).
- Controller: heuristic minh bạch (search 1 lần rồi trích top-1 làm đáp án,
  abstain khi score thấp hoặc context rỗng). Đây là baseline agent để đo
  pipeline; khi có API key, thay HeuristicController bằng LLMController
  (gọi model thật) mà không đổi Retriever/trace format.
- Trace ra đúng schema cho starter/agent_metrics.py: query_id, status
  (answered/abstain/error), events (event=search), citations.

Chạy dev:
  python src/agent_run.py --chunks data/chunks.json --questions data/questions.json --index src/day6_index.json --split dev --output starter/results/agent-dev --top-k 3 --budget 800 --max-searches 2 --abstain-threshold 0.10
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "starter"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from baseline import pack_context  # noqa: E402
from day6_store import embed  # noqa: E402


class DenseRetriever:
    def __init__(self, chunks, vectors):
        self.chunks = chunks
        self.vectors = vectors

    def search(self, query, *, filters=None, top_k=3):
        qv = embed(query)
        scored = []
        for entry, chunk in zip(self.vectors, self.chunks):
            if filters:
                if any(chunk.get("metadata", {}).get(k) != v for k, v in filters.items()):
                    continue
            s = sum(a * b for a, b in zip(qv, entry["vector"]))
            if s > 0:
                scored.append({**chunk, "score": s, "strategy": "dense-agent"})
        return sorted(scored, key=lambda c: (-c["score"], c["id"]))[:top_k]


class HeuristicController:
    """Baseline minh bạch: search câu hỏi gốc, rồi trả lời từ top-1.

    Abstain khi top-1 score < threshold (không đủ bằng chứng) — ngưỡng này
    là 1 cấu hình được thử trên dev, không phải đoán từ gold.
    """

    def __init__(self, retriever, threshold=0.10, top_k=3, budget=800):
        self.retriever = retriever
        self.threshold = threshold
        self.top_k = top_k
        self.budget = budget

    def run(self, question, filters=None, max_searches=2):
        events = []
        candidates = []
        for _ in range(max_searches):
            results = self.retriever.search(question, filters=filters, top_k=self.top_k)
            candidates.extend(results)
            context, ids = pack_context(candidates, budget=self.budget)
            events.append({"event": "search", "query": question, "filter": filters,
                           "results": results, "context": context, "context_ids": ids})
            if not results:
                break
            top_score = results[0].get("score", 0)
            if top_score < self.threshold:
                break  # bằng chứng quá yếu -> dừng, abstain
            break  # baseline: 1 lượt search là đủ
        last = events[-1] if events else {"context": "", "context_ids": []}
        ids = last.get("context_ids", [])
        if not ids:
            return {"status": "abstain", "answer": "Không đủ bằng chứng để trả lời.",
                    "citations": [], "events": events}
        top_id = ids[0]
        top_score = 0
        for e in events:
            for r in e.get("results", []):
                if r["id"] == top_id:
                    top_score = max(top_score, r.get("score", 0))
        if top_score < self.threshold:
            return {"status": "abstain", "answer": "Không đủ bằng chứng để trả lời.",
                    "citations": [], "events": events + [{"event": "abstain_low_score",
                    "top_id": top_id, "top_score": round(top_score, 4),
                    "threshold": self.threshold}]}
        top_text = ""
        for e in events:
            for r in e.get("results", []):
                if r["id"] == top_id:
                    top_text = r.get("text", "")
        return {"status": "answered",
                "answer": f"{top_text} [{top_id}]",
                "citations": [top_id], "events": events}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True, type=Path)
    ap.add_argument("--questions", required=True, type=Path)
    ap.add_argument("--index", required=True, type=Path)
    ap.add_argument("--split", required=True, choices=("dev", "test"))
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--budget", type=int, default=800)
    ap.add_argument("--max-searches", type=int, default=2)
    ap.add_argument("--abstain-threshold", type=float, default=0.10)
    args = ap.parse_args()

    chunks = json.loads(args.chunks.read_text(encoding="utf-8"))
    questions = [q for q in json.loads(args.questions.read_text(encoding="utf-8")) if q.get("split") == args.split]
    index = json.loads(args.index.read_text(encoding="utf-8"))
    id2vec = {v["id"]: v for v in index["vectors"]}
    vectors = [id2vec[c["id"]] for c in chunks]
    retriever = DenseRetriever(chunks, vectors)

    traces = []
    for q in questions:
        t0 = time.perf_counter()
        try:
            controller = HeuristicController(retriever, threshold=args.abstain_threshold,
                                             top_k=args.top_k, budget=args.budget)
            res = controller.run(q["question"], filters=q.get("filter"),
                                 max_searches=args.max_searches)
            res["query_id"] = q["id"]
            res["elapsed_ms"] = (time.perf_counter() - t0) * 1000
            res["config"] = {"top_k": args.top_k, "budget": args.budget,
                             "max_searches": args.max_searches,
                             "threshold": args.abstain_threshold}
        except Exception as e:  # lỗi kết nối/vector store ghi riêng, không thay kết quả giả
            res = {"query_id": q["id"], "status": "error", "error": str(e),
                   "events": [], "citations": [], "elapsed_ms": (time.perf_counter() - t0) * 1000}
        traces.append(res)

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "traces.json").write_text(json.dumps(traces, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = sum(1 for t in traces if t["status"] == "answered")
    ab = sum(1 for t in traces if t["status"] == "abstain")
    er = sum(1 for t in traces if t["status"] == "error")
    print(json.dumps({"split": args.split, "n": len(traces), "answered": ok,
                      "abstain": ab, "error": er}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
