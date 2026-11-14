"""Verify frozen inputs, provenance, actual-vector export and evaluation completeness."""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agent_run import digest
from costs import estimate_calls
from day6_store import DIM, MODEL, REVISION, corpus_hash
from evaluation import summarize
from retrievers import evidence_hit
from run_paths import artifact_path, results_directory


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs-only", action="store_true")
    parser.add_argument("--results-root", type=Path)
    args = parser.parse_args()
    results_root = results_directory(args.results_root)
    freeze = load(ROOT / "data/benchmark_freeze.json")
    for rel, expected in freeze["sha256"].items():
        if hashlib.sha256((ROOT / rel.replace('\\', '/')).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen input changed: {rel}")
    chunks, questions = load(ROOT / "data/chunks.json"), load(ROOT / "data/questions.json")
    manifest = load(ROOT / "data/day6_manifest.json")
    source_units = {}
    for source in manifest["sources"]:
        raw = ROOT / source["local_path"]
        if hashlib.sha256(raw.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("Raw source checksum mismatch")
        text = (ROOT / source["normalized_path"]).read_text(encoding="utf-8")
        for page in source["pages"]:
            source_units[(source["source_id"], page["page"])] = text[page["start_char"]:page["end_char"]]
    for c in chunks:
        unit = source_units[(c["source_id"], c["page"])]
        if c["text"] != unit[c["metadata"]["start_char"]:c["metadata"]["end_char"]]:
            raise ValueError(f"Chunk source offsets differ: {c['id']}")
    if len({c["id"] for c in chunks}) != len(chunks):
        raise ValueError("Duplicate chunk IDs")
    for q in questions:
        if q["answerable"] and not any(evidence_hit(c, q["gold"]) for c in chunks):
            raise ValueError(f"Missing gold evidence: {q['id']}")
        if not q["answerable"] and not q.get("absence_reason"):
            raise ValueError("Unanswerable case needs absence verification")
    for split, yes, no in (("dev", 15, 2), ("test", 5, 2)):
        rows = [q for q in questions if q["split"] == split]
        if sum(q["answerable"] for q in rows) < yes or sum(not q["answerable"] for q in rows) < no:
            raise ValueError("Insufficient benchmark cases")
    index = load(ROOT / "src/day6_index.json")
    if (index["embedding_model"], index["revision"], index["dim"], index["corpus_sha256"]) != (
            MODEL, REVISION, DIM, corpus_hash(chunks)):
        raise ValueError("Model/index provenance mismatch")
    if {v["id"] for v in index["vectors"]} != {c["id"] for c in chunks}:
        raise ValueError("Vector IDs differ from corpus")
    import math
    if any(len(v["vector"]) != DIM or not all(math.isfinite(x) for x in v["vector"]) or
           abs(sum(x*x for x in v["vector"]) - 1) > 0.001 for v in index["vectors"]):
        raise ValueError("Non-normalized, invalid or wrong-dimension vectors")
    if args.inputs_only:
        print(f"Verified {len(chunks)} real chunks, {len(source_units)} source units, {len(questions)} questions and {DIM}-dimensional vectors.")
        return
    selection = load(results_root / "selection.json")
    if selection["benchmark_freeze_sha256"] != digest(freeze) or selection["test_queries_run"] != 0:
        raise ValueError("Invalid selection provenance")
    for rel, expected in selection["dev_artifact_sha256"].items():
        if hashlib.sha256(artifact_path(results_root, rel).read_bytes()).hexdigest() != expected:
            raise ValueError("Dev artifacts changed after selection")
    author_rows = []
    folders = sorted(results_root.glob("*/*/traces.json"))
    verified = []
    all_human_reviewed = True
    for path in folders:
        if path.parent.parent.name == "retrieval":
            continue
        split = path.parent.name
        subset = [q for q in questions if q["split"] == split]
        traces, reviews = load(path), load(path.parent / "reviews.json")
        all_human_reviewed = all_human_reviewed and bool(reviews) and all(r.get("human_reviewed") is True for r in reviews)
        if {t["query_id"] for t in traces} != {q["id"] for q in subset}:
            raise ValueError("Incomplete trace coverage")
        by_id = {t["query_id"]: t for t in traces}
        for r in reviews:
            if (r["trace_sha256"] != digest(by_id[r["query_id"]])
                    or not (r.get("codex_verified") or r.get("review_status") == "reviewed")):
                raise ValueError("Label is stale or has not been inspected by a named reviewer")
            author_rows.append({"configuration": path.parent.parent.name, "split": split,
                "query_id": r["query_id"], "ai_answer_grade": r.get("answer_grade", ""),
                "ai_context_grade": r.get("context_grade", ""), "author_name": "",
                "author_agrees": "", "author_reason": "", "reviewed_at": ""})
        computed = summarize(subset, traces, reviews)
        if computed != load(path.parent / "summary.json"):
            raise ValueError("Summary differs from trace/labels")
        verified.append(path.parent.relative_to(results_root).as_posix())
    required = {f"{c['name']}/test" for c in (selection["baseline"], selection["selected"])}
    if not required.issubset({p.replace('\\', '/') for p in verified}):
        raise ValueError("Missing baseline or selected agent on test")
    cost_path = results_root / "costs.json"
    if cost_path.exists():
        costs = load(cost_path)
        if costs.get("kind") != "estimate" or costs.get("account_invoice_verified") is not False:
            raise ValueError("Public-rate estimates must not claim a verified account invoice")
        for entry in costs["runs"]:
            folder = results_root / entry["configuration"] / entry["split"]
            trace_path, review_path = folder / "traces.json", folder / "reviews.json"
            if (hashlib.sha256(trace_path.read_bytes()).hexdigest() != entry["trace_sha256"] or
                    hashlib.sha256(review_path.read_bytes()).hexdigest() != entry["reviews_sha256"]):
                raise ValueError("Cost estimate is stale relative to traces/reviews")
            usages = [e["usage"] for t in load(trace_path) for e in t.get("events", []) if e["event"] == "model"]
            if estimate_calls(usages, costs["pricing"]) != entry["agent_estimate_usd_before_group"]:
                raise ValueError("Cost estimate does not match recorded model usage")
    pending = results_root / "author_review_pending.csv"
    if not pending.exists():
        with pending.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(author_rows[0]))
            writer.writeheader()
            writer.writerows(author_rows)
    result = {"status": "passed", "chunks": len(chunks), "source_units": len(source_units),
              "questions": len(questions), "verified_runs": verified,
              "embedding": MODEL, "dimensions": DIM, "human_review_complete": all_human_reviewed}
    (results_root / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
