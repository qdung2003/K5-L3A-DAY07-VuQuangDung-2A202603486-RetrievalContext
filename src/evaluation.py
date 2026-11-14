"""Aggregate inspected labels, tool use, context, timing, token and error counts."""
import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "starter"))
from agent_metrics import aggregate

from retrievers import evidence_hit


def summarize(questions, traces, reviews):
    cases = [{k: q[k] for k in ("id", "answerable")} for q in questions]
    report = aggregate(cases, traces, reviews)
    by_id = {r["query_id"]: r for r in reviews}
    answerable = {q["id"]: q for q in questions if q["answerable"]}
    hist = Counter()
    context_grades = Counter()
    context_hits = 0
    for t in traces:
        if t["status"] == "error":
            continue
        searches = [e for e in t["events"] if e["event"] == "search"]
        hist[str(len(searches))] += 1
        if t["query_id"] in answerable:
            review = by_id[t["query_id"]]
            if (type(review.get("context_grade")) is not int or review["context_grade"] not in (0, 1, 2)
                    or not review.get("context_reason")):
                raise ValueError("Context needs an inspected 0/1/2 grade and reason")
            context_grades[str(review["context_grade"])] += 1
            last = searches[-1] if searches else {"context_ids": []}
            rows = {r["id"]: r for e in searches for r in e["results"]}
            context_hits += any(evidence_hit(rows[cid], answerable[t["query_id"]]["gold"])
                                for cid in last["context_ids"] if cid in rows)
    report["context_grades"] = {str(i): context_grades[str(i)] for i in range(3)}
    report["context_evidence_rate"] = {"n": context_hits, "N": len(answerable)}
    report["search_call_distribution"] = dict(hist)
    report["mean_elapsed_ms"] = statistics.mean(t["elapsed_ms"] for t in traces)
    report["usage"] = {k: sum(t.get("usage", {}).get(k, 0) for t in traces)
                       for k in ("input_tokens", "output_tokens", "cached_input_tokens")}
    report["cost_usd"] = None
    report["cost_note"] = "Actual tokens recorded. Provider/account price unavailable; no fabricated dollar estimate."
    report["reviewers"] = sorted({r["reviewed_by"] for r in reviews})
    report["human_review_complete"] = bool(reviews) and all(r.get("human_reviewed") is True for r in reviews)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    args = parser.parse_args()
    def load(path):
        return json.loads(path.read_text(encoding="utf-8"))
    questions = [q for q in load(ROOT / "data/questions.json") if q["split"] == args.split]
    report = summarize(questions, load(args.folder / "traces.json"), load(args.folder / "reviews.json"))
    (args.folder / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
