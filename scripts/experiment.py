"""Separate dev execution, independent audits, config selection and held-out test."""
import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agent_run import client_from_env, digest, run_batch, save
from day6_store import encoder
from evaluation import summarize
from model_config import settings_from_env
from retrievers import Retriever, evaluate
from run_paths import artifact_path, results_directory


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_freeze():
    freeze = load(ROOT / "data/benchmark_freeze.json")
    for rel, expected in freeze["sha256"].items():
        if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Frozen input changed: {rel}")
    return freeze


def verify_selection(results_root, selection, freeze):
    if selection["benchmark_freeze_sha256"] != digest(freeze):
        raise ValueError("Benchmark freeze differs from selection")
    for rel, expected in selection["dev_artifact_sha256"].items():
        if hashlib.sha256(artifact_path(results_root, rel).read_bytes()).hexdigest() != expected:
            raise ValueError("Dev artifacts changed after selection")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("dev", "select", "test"))
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--results-root", type=Path, help="Independent experiment directory (default: results)")
    args = parser.parse_args()
    results_root = results_directory(args.results_root)
    settings = settings_from_env(args.env_file)
    freeze = verify_freeze()
    chunks = load(ROOT / "data/chunks.json")
    all_questions = load(ROOT / "data/questions.json")
    configs = [settings.apply(c) for c in load(ROOT / "configs/experiments.json")]
    selection_path = results_root / "selection.json"
    if args.stage == "select":
        if selection_path.exists():
            selection = load(selection_path)
            verify_selection(results_root, selection, freeze)
            if not args.resume:
                raise ValueError("Selection already frozen; use --resume to verify it or --results-root for another run")
            if any(settings.apply(c) != c for c in (selection["baseline"], selection["selected"])):
                raise ValueError("Current .env differs from the frozen model/reasoning")
            print("Existing selection verified:", selection["selected"]["name"])
            return
        if any((results_root / c["name"] / "test/traces.json").exists() for c in configs):
            raise ValueError("Test was already run; cannot claim selection before test")
        scored = []
        hashes = {}
        for priority, c in enumerate(configs):
            folder = results_root / c["name"] / "dev"
            actual = load(folder / "run.json")["config"]
            if any(actual.get(key) != value for key, value in c.items()):
                raise ValueError("Current .env/config differs from the recorded dev run; evaluate the new configuration on dev first")
            reviews = load(folder / "reviews.json")
            summary = load(folder / "summary.json")
            dev_questions = [q for q in all_questions if q["split"] == "dev"]
            traces = load(folder / "traces.json")
            by_id = {t["query_id"]: t for t in traces}
            if ({r["query_id"] for r in reviews} != {q["id"] for q in dev_questions}
                    or any(not (r.get("codex_verified") or r.get("review_status") == "reviewed")
                           or not r.get("reviewed_by") or not r.get("note")
                           or r.get("trace_sha256") != digest(by_id.get(r["query_id"])) for r in reviews)):
                raise ValueError("Every dev label needs a reviewer and a concrete evidence-based reason")
            if summary["provider_errors"]:
                raise ValueError("Resolve dev infrastructure errors before selection")
            if summary != summarize(dev_questions, traces, reviews):
                raise ValueError("Dev summary is stale; aggregate the inspected labels before selection")
            g = summary["grounded_answer"]["mean"]
            a = summary["abstention"]["n"]
            f = summary["false_abstention"]["n"]
            tokens = summary["usage"]["input_tokens"] + summary["usage"]["output_tokens"]
            scored.append(((g, a, -f, -tokens, -priority), c))
            for name in ("traces.json", "reviews.json", "summary.json"):
                p = folder / name
                hashes[p.relative_to(results_root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        selected = max(scored, key=lambda pair: pair[0])[1]
        save(selection_path, {"selected_at": datetime.now(UTC).isoformat(),
             "rule": freeze["selection_rule"], "selected": selected, "baseline": configs[0],
             "test_queries_run": 0, "dev_artifact_sha256": hashes,
             "benchmark_freeze_sha256": digest(freeze)})
        print("Selected on dev:", selected["name"])
        return
    split = args.stage
    questions = [q for q in all_questions if q["split"] == split]
    if split == "dev" and selection_path.exists():
        verify_selection(results_root, load(selection_path), freeze)
        if not args.resume:
            raise ValueError("Dev is frozen; use --results-root for a new experiment")
        for c in configs:
            actual = load(results_root / c["name"] / "dev/run.json")["config"]
            if any(actual.get(key) != value for key, value in c.items()):
                raise ValueError("Current configuration differs from frozen dev; use another --results-root")
        print("Frozen dev artifacts verified; no files or model requests changed.")
        return
    if split == "test":
        selection = load(selection_path)
        verify_selection(results_root, selection, freeze)
        unique = {c["name"]: c for c in (selection["baseline"], selection["selected"])}
        configs = list(unique.values())
        if any(settings.apply(c) != c for c in configs):
            raise ValueError("The .env model/reasoning differs from the frozen selection; evaluate and select on dev before running test")
    encoder()  # Warm once before concurrent runs; all queries share the pinned CPU model.
    retrieval = {}
    for method in ("dense", "lexical", "hybrid"):
        rows, summary = evaluate(Retriever(chunks, method), questions, top_k=3, budget=3200)
        path = results_root / "retrieval" / split / f"traces-{method}.json"
        if not (args.resume and path.exists()):
            save(path, rows)
        retrieval[method] = summary
    summary_path = results_root / "retrieval" / split / "summary.json"
    if not (args.resume and summary_path.exists()):
        save(summary_path, retrieval)
    client = client_from_env(settings=settings)
    def run(config):
        return run_batch(questions, chunks, config, results_root / config["name"] / split,
                         client, args.resume)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(run, config) for config in configs]
        for future in futures:
            future.result()
    print(f"Finished {split}; inspect traces and label before continuing.")


if __name__ == "__main__":
    main()
