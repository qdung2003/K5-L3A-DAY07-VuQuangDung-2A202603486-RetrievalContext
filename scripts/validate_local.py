"""Offline validation in the project environment, including a rebuilt real store."""
import argparse
import importlib.metadata
import json
import math
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agent_run import save
from day6_store import embed, open_collection
from retrievers import Retriever


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=Path, required=True)
    args = parser.parse_args()
    chunks = json.loads((ROOT / "data/chunks.json").read_text(encoding="utf-8"))
    exported = json.loads((ROOT / "src/day6_index.json").read_text(encoding="utf-8"))
    vectors = {r["id"]: r["vector"] for r in exported["vectors"]}
    collection = open_collection(args.store)
    if collection.count() != len(chunks):
        raise ValueError("Rebuilt store count differs from the corpus")
    actual = embed(chunks[0]["text"])
    delta = max(abs(a - b) for a, b in zip(actual, vectors[chunks[0]["id"]]))
    if delta > 1e-5:
        raise ValueError("Local neural encoder differs from exported Day 6 embeddings")
    retriever = Retriever(chunks, "dense", args.store)
    hits = retriever.search("How do you create an empty set?", top_k=3)
    if not hits or not all(math.isfinite(h["score"]) and h["source"] and h["page"] for h in hits):
        raise ValueError("Real retrieval smoke check failed")
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise RuntimeError("Project tests failed")
    packages = {}
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        if "==" in line and not line.startswith("#"):
            name, expected = line.split("==", 1)
            actual_version = importlib.metadata.version(name)
            if expected != actual_version:
                raise ValueError(f"Installed version differs from requirements: {name}")
            packages[name] = actual_version
    save(ROOT / "results/current_validation.json", {
        "validated_at": datetime.now(UTC).isoformat(), "status": "passed",
        "python": sys.version.split()[0], "environment": "Project .venv; host heavy libraries reused, no Day 6 venv import path",
        "packages": packages, "rebuilt_store_count": collection.count(),
        "neural_vector_max_abs_difference": delta, "tests_run": result.testsRun,
        "tests_passed": result.testsRun, "model_api_requests_sent": 0,
        "retrieval_smoke": [{k: h[k] for k in ("id", "source", "page", "score")} for h in hits],
        "scope": "Rebuilt from tracked real-vector export, checked pinned local encoder and real retrieval; no new generation benchmark or hidden-test claim."})
    print(f"Offline validation passed: {result.testsRun} tests, {collection.count()} real vectors, max encoder delta={delta:.3g}")


if __name__ == "__main__":
    main()
