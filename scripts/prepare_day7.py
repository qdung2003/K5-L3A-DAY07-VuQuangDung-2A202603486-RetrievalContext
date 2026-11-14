"""Import the actual Day 6 snapshot and freeze a fresh Day 7 benchmark."""
import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize(value):
    return " ".join(value.split())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--day6", type=Path, help="Optional Day 6 root for importing missing local caches")
    args = parser.parse_args()
    if args.day6:
        for source, dest in [(".cache/all-MiniLM-L6-v2", ".cache/all-MiniLM-L6-v2"),
                             ("starter/vector_store", ".cache/day6_store")]:
            target = ROOT / dest
            if not target.exists():
                shutil.copytree(args.day6 / source, target)
    questions_path = ROOT / "data/questions.json"
    freeze_path = ROOT / "data/benchmark_freeze.json"
    if freeze_path.exists():
        freeze = load(freeze_path)
        for rel, digest in freeze["sha256"].items():
            if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Frozen input changed: {rel}")
        print("Existing benchmark freeze verified; no inputs overwritten.")
        return
    chunks = []
    for line in (ROOT / "data/day6_chunks_B.jsonl").read_text(encoding="utf-8").splitlines():
        chunk = json.loads(line)
        chunks.append({"id": chunk["chunk_id"], "source_id": chunk["document_id"],
                       **{key: chunk[key] for key in ("text", "source", "page", "metadata")}})
    questions = []
    for q in load(ROOT / "data/day6_questions.json"):
        if q["split"] != "dev":
            continue  # Day 6 test was already observed; it is not a Day 7 holdout.
        alternatives = [{"source_id": q["gold_source_id"], "page": q["gold_page"],
                         "evidence": q["evidence_quote"]}, *q.get("alternative_gold", [])]
        questions.append({"id": q["id"], "split": "dev", "question": q["question"],
                          "expected_answer": q["expected_answer"], "gold": alternatives,
                          "filter": q.get("filter"), "answerable": True})
    questions.extend(load(ROOT / "data/day7_additions.json"))
    for q in questions:
        q.setdefault("answerable", bool(q.get("gold")))
        for g in q.get("gold", []):
            matches = [c for c in chunks if c["source_id"] == g["source_id"] and
                       c["page"] == g["page"] and normalize(g["evidence"]) in normalize(c["text"])]
            if not matches:
                raise ValueError(f"Evidence missing from Day 6 chunks: {q['id']}")
    save(ROOT / "data/chunks.json", chunks)
    save(questions_path, questions)
    save(ROOT / "data/questions_answerable.json", [q for q in questions if q["answerable"]])
    save(ROOT / "data/cases.json", [{k: q[k] for k in ("id", "split", "answerable")} for q in questions])
    paths = ["data/chunks.json", "data/questions.json", "data/cases.json", "data/day7_additions.json"]
    save(freeze_path, {"created_at": datetime.now(UTC).isoformat(),
         "policy": "Reuse Day 6 dev only. New Day 7 test topics differ from Day 6 test. Freeze before any Day 7 neural retrieval or agent evaluation. Never tune on test.",
         "selection_rule": "Maximize dev grounded-answer mean, then correct abstention, then fewer false refusals, then fewer model tokens. If tied prefer baseline, dense-wide, hybrid, hybrid-wide in that order.",
         "sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}})
    print(f"Frozen {len(chunks)} Day 6 chunks and {len(questions)} Day 7 cases.")


if __name__ == "__main__":
    main()
