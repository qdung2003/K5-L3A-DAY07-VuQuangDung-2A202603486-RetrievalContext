"""Day 6 Chroma dense, TF-IDF lexical, and reciprocal-rank fusion."""
import argparse
import json
import statistics
import sys
import time
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "starter"))
from baseline import TfidfIndex, pack_context

from day6_store import ROOT, corpus_hash, embed, open_collection


def normalized(text):
    return " ".join(text.split())


def evidence_hit(chunk, gold):
    return any(chunk["source_id"] == g["source_id"] and chunk["page"] == g["page"]
               and normalized(g["evidence"]) in normalized(chunk["text"]) for g in gold)


def rrf_fuse(*rankings, k=60):
    scores, chunks = {}, {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking, 1):
            cid = chunk["id"]
            chunks[cid] = chunk
            scores[cid] = scores.get(cid, 0) + 1 / (k + rank)
    return [{**chunks[cid], "score": scores[cid], "strategy": "hybrid-rrf"}
            for cid in sorted(scores, key=lambda cid: (-scores[cid], cid))]


def measure(results, gold, context_ids):
    return {"hit1": bool(results and evidence_hit(results[0], gold)),
            "hit3": any(evidence_hit(c, gold) for c in results[:3]),
            "context_hit": any(c["id"] in context_ids and evidence_hit(c, gold) for c in results)}


class Retriever:
    def __init__(self, chunks, method="dense", store=ROOT / ".cache/day6_store"):
        if method not in ("dense", "lexical", "hybrid"):
            raise ValueError("Unknown retrieval method")
        self.chunks, self.method = chunks, method
        self.lexical = TfidfIndex(chunks)
        self.collection = open_collection(store) if method != "lexical" else None
        if self.collection is not None and set(self.collection.get(include=[])["ids"]) != {c["id"] for c in chunks}:
            raise ValueError("Store IDs differ from corpus; rebuild before running")

    @staticmethod
    @lru_cache(maxsize=1024)
    def query_vector(query):
        return embed(query)

    def search(self, query, *, filters=None, top_k=3):
        if top_k < 1 or not isinstance(query, str) or not query.strip():
            raise ValueError("Positive top_k and nonempty query required")
        if filters and (set(filters) - {"section", "version", "language"} or
                        any(not isinstance(v, str) for v in filters.values())):
            raise ValueError("Unsupported metadata filter")
        limit = max(10, top_k) if self.method == "hybrid" else top_k
        lexical = []
        if self.method != "dense":
            rows = self.lexical.search(query, top_k=len(self.chunks))
            lexical = [c for c in rows if not filters or
                       all(c["metadata"].get(k) == v for k, v in filters.items())][:limit]
        if self.method == "lexical":
            return lexical[:top_k]
        clauses = [{k: {"$eq": v}} for k, v in (filters or {}).items()]
        where = (clauses[0] if len(clauses) == 1 else {"$and": clauses}) if clauses else None
        data = self.collection.query(query_embeddings=[self.query_vector(query)], where=where,
            n_results=min(limit, len(self.chunks)), include=["documents", "metadatas", "distances"])
        dense = [{"id": cid, "text": text, "source_id": meta["document_id"],
                  "source": meta["source"], "page": meta["page"], "metadata": meta,
                  "score": 1 - float(distance), "strategy": "dense-chroma"}
                 for cid, text, meta, distance in zip(data["ids"][0], data["documents"][0],
                     data["metadatas"][0], data["distances"][0])]
        return (rrf_fuse(dense, lexical) if self.method == "hybrid" else dense)[:top_k]


def evaluate(retriever, questions, *, top_k, budget):
    traces = []
    for q in questions:
        if not q.get("gold"):
            continue
        start = time.perf_counter()
        results = retriever.search(q["question"], filters=q.get("filter"), top_k=max(3, top_k))
        context, ids = pack_context(results[:top_k], budget)
        traces.append({"query_id": q["id"], "question": q["question"], "filter": q.get("filter"),
            "results": results, "context": context, "context_ids": ids,
            "elapsed_ms": (time.perf_counter() - start) * 1000, **measure(results, q["gold"], ids)})
    summary = {key: {"n": sum(t[key] for t in traces), "N": len(traces)}
               for key in ("hit1", "hit3", "context_hit")}
    summary["mean_ms"] = statistics.mean(t["elapsed_ms"] for t in traces) if traces else None
    return traces, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", type=Path, default=ROOT / "data/chunks.json")
    parser.add_argument("--questions", type=Path, default=ROOT / "data/questions.json")
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--budget", type=int, default=3200)
    args = parser.parse_args()
    chunks = json.loads(args.chunks.read_text(encoding="utf-8"))
    questions = [q for q in json.loads(args.questions.read_text(encoding="utf-8")) if q["split"] == args.split]
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"corpus_sha256": corpus_hash(chunks), "split": args.split}
    for method in ("dense", "lexical", "hybrid"):
        traces, summary = evaluate(Retriever(chunks, method), questions, top_k=args.top_k, budget=args.budget)
        report[method] = summary
        (args.output / f"traces-{method}.json").write_text(json.dumps(traces, indent=2) + "\n", encoding="utf-8")
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
