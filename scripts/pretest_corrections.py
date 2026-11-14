"""Recorded pre-test corrections discovered while inspecting dev outputs."""
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agent_run import all_citations, save


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    if any((ROOT / "results").glob("*/test/traces.json")) or (ROOT / "results/selection.json").exists():
        raise ValueError("Corrections are only allowed before selection and before test")
    freeze_path = ROOT / "data/benchmark_freeze.json"
    old = load(freeze_path)
    archive = ROOT / "data/benchmark_freeze_v1.json"
    if not archive.exists():
        save(archive, old)
    questions_path = ROOT / "data/questions.json"
    questions = load(questions_path)
    replacement = next(q for q in load(ROOT / "data/day7_additions.json") if q["id"] == "T03")
    replacement["answerable"] = True
    questions = [replacement if q["id"] == "T03" else q for q in questions]
    save(questions_path, questions)
    save(ROOT / "data/questions_answerable.json", [q for q in questions if q["answerable"]])
    old["pretest_amendment"] = {"at": datetime.now(UTC).isoformat(),
        "reason": "T03 overlapped dev Q11. Replaced before any Day 7 test execution with import-search-order question; dev inputs and selection rule unchanged. Original freeze retained as benchmark_freeze_v1.json.",
        "test_queries_run": 0}
    for rel in old["sha256"]:
        old["sha256"][rel] = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    save(freeze_path, old)
    repairs = []
    for path in sorted((ROOT / "results").glob("*/dev/traces.json")):
        traces = load(path)
        for trace in traces:
            if trace["status"] == "abstain":
                citations = all_citations(trace["answer"], trace["citations"])
                if citations != trace["citations"]:
                    repairs.append({"configuration": path.parent.parent.name,
                                    "query_id": trace["query_id"], "before": trace["citations"], "after": citations})
                    trace["citations"] = citations
        save(path, traces)
    save(ROOT / "results/pretest_corrections.json", {"at": datetime.now(UTC).isoformat(),
         "reason": "Count inline citations on abstention without altering original model answers or outputs.",
         "repairs": repairs, "test_queries_run": 0})
    print(f"Replaced overlapping T03 before test; corrected {len(repairs)} inline citation lists.")


if __name__ == "__main__":
    main()
