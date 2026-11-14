"""3 phương pháp retrieval: dense (vector store Day 6) + lexical (TF-IDF) + hybrid (RRF).

Chạy: python src/retrievers.py --chunks data/chunks.json --questions data/questions.json --split dev --output starter/results/dev-3methods
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "starter"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from baseline import TfidfIndex, hit, pack_context  # noqa: E402
from day6_store import embed  # noqa: E402


def dense_search(query, vectors, chunks, top_k=3):
    qv = embed(query)
    scored = []
    for entry, chunk in zip(vectors, chunks):
        s = sum(a * b for a, b in zip(qv, entry["vector"]))
        if s > 0:
            scored.append({**chunk, "score": s, "strategy": "dense"})
    return sorted(scored, key=lambda c: (-c["score"], c["id"]))[:top_k]


def rrf_fuse(dense_ranked, lex_ranked, k=60):
    ranks = {}
    for rank, c in enumerate(dense_ranked, 1):
        ranks.setdefault(c["id"], {"chunk": c, "s": 0.0})
        ranks[c["id"]]["s"] += 1.0 / (k + rank)
    for rank, c in enumerate(lex_ranked, 1):
        ranks.setdefault(c["id"], {"chunk": c, "s": 0.0})
        ranks[c["id"]]["s"] += 1.0 / (k + rank)
    out = [{**v["chunk"], "score": v["s"], "strategy": "hybrid-rrf"} for v in ranks.values()]
    return sorted(out, key=lambda c: (-c["score"], c["id"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True, type=Path)
    ap.add_argument("--questions", required=True, type=Path)
    ap.add_argument("--index", type=Path, default=Path("src/day6_index.json"))
    ap.add_argument("--split", required=True, choices=("dev", "test"))
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--budget", type=int, default=800)
    args = ap.parse_args()
    chunks = json.loads(args.chunks.read_text(encoding="utf-8"))
    questions = [q for q in json.loads(args.questions.read_text(encoding="utf-8")) if q.get("split") == args.split]
    index = json.loads(args.index.read_text(encoding="utf-8"))
    id2vec = {v["id"]: v for v in index["vectors"]}
    vectors = [id2vec[c["id"]] for c in chunks]
    tfidf = TfidfIndex(chunks)

    methods = {
        "dense": lambda q: dense_search(q, vectors, chunks, args.top_k),
        "lexical-tfidf": lambda q: tfidf.search(q, top_k=args.top_k),
        "hybrid-rrf": lambda q: rrf_fuse(dense_search(q, vectors, chunks, 10), tfidf.search(q, top_k=10))[:args.top_k],
    }
    report = {}
    for name, fn in methods.items():
        traces = []
        for q in questions:
            if not q.get("gold"):  # câu thiếu evidence: chỉ đo abstention, không vào Hit@k
                traces.append({"query_id": q["id"], "strategy": name, "skipped": "unanswerable"})
                continue
            t0 = time.perf_counter()
            results = fn(q["question"])
            ms = (time.perf_counter() - t0) * 1000
            marked = [{**c, "hit": hit(c, q["gold"])} for c in results]
            ctx, ids = pack_context(results, budget=args.budget)
            traces.append({"query_id": q["id"], "strategy": name, "results": marked,
                           "context_ids": ids, "elapsed_ms": ms,
                           "hit1": bool(marked and marked[0]["hit"]),
                           "hit3": any(c["hit"] for c in marked),
                           "context_hit": any(c["hit"] and c["id"] in ids for c in marked)})
        scored = [t for t in traces if "hit1" in t]
        report[name] = {"n": len(scored), "hit1": sum(t["hit1"] for t in scored),
                        "hit3": sum(t["hit3"] for t in scored),
                        "context_hit": sum(t["context_hit"] for t in scored)}
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / f"traces-{name}.json").write_text(json.dumps(traces, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "summary-3methods.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
