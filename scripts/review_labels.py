"""Export trace-bound review forms and import explicitly approved decisions."""
import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agent_run import digest, save
from evaluation import summarize
from run_paths import results_directory


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def export_form(results_root, split, output):
    questions = {q["id"]: q for q in load(ROOT / "data/questions.json") if q["split"] == split}
    forms = []
    for path in sorted(results_root.glob(f"*/{split}/reviews.json")):
        traces = {t["query_id"]: t for t in load(path.parent / "traces.json")}
        for r in load(path):
            t = traces[r["query_id"]]
            search = [e for e in t["events"] if e["event"] == "search"]
            forms.append({"configuration": path.parent.parent.name, "query_id": r["query_id"],
                "trace_sha256": digest(t), "approved": False, "question": questions[r["query_id"]],
                "answer": t["answer"], "citations": t["citations"],
                "final_context": search[-1]["context"] if search else "",
                "decision": {k: r[k] for k in ("answer_grade", "context_grade", "citation_support",
                             "abstention_correct", "note", "context_reason") if k in r}})
    if output.exists():
        raise ValueError("Review form already exists; choose another --file to preserve edits")
    save(output, {"reviewer": "", "reviewer_type": "human", "split": split, "decisions": forms})
    print(f"Exported {len(forms)} unapproved decisions to {output}")


def import_form(results_root, split, source):
    if split == "dev" and (results_root / "selection.json").exists():
        raise ValueError("Dev labels are frozen; review in a new experiment before selection")
    form = load(source)
    if (not isinstance(form.get("reviewer"), str) or not form["reviewer"].strip()
            or form.get("reviewer_type") not in ("human", "ai") or form.get("split") != split):
        raise ValueError("Provide a named human or AI reviewer and the correct split")
    decisions = form["decisions"]
    keys = [(d["configuration"], d["query_id"]) for d in decisions]
    if len(keys) != len(set(keys)) or any(d.get("approved") is not True for d in decisions):
        raise ValueError("Every decision must be unique and explicitly approved after inspection")
    by_key = dict(zip(keys, decisions))
    questions = [q for q in load(ROOT / "data/questions.json") if q["split"] == split]
    plans = []
    for path in sorted(results_root.glob(f"*/{split}/reviews.json")):
        reviews = load(path)
        traces = load(path.parent / "traces.json")
        by_id = {t["query_id"]: t for t in traces}
        for r in reviews:
            key = (path.parent.parent.name, r["query_id"])
            decision = by_key.pop(key, None)
            if not decision or decision["trace_sha256"] != digest(by_id[r["query_id"]]):
                raise ValueError("Missing decision or stale trace fingerprint")
            label = decision["decision"]
            allowed = {"answer_grade", "context_grade", "citation_support", "abstention_correct", "note", "context_reason"}
            if set(label) - allowed:
                raise ValueError("Review decisions may change labels/reasons only, not trace identity or reviewer metadata")
            if not label.get("note") or not label.get("context_reason"):
                raise ValueError("Each approval requires source-based answer and context reasons")
            r.update(label, reviewed_by=form["reviewer"], human_reviewed=form["reviewer_type"] == "human",
                     review_status="reviewed", reviewed_at=datetime.now(UTC).isoformat())
            r.pop("codex_verified", None)
        report = summarize(questions, traces, reviews)
        plans.append((path, reviews, report))
    if by_key or not plans:
        raise ValueError("Unknown review decisions or no complete review files")
    for path, reviews, report in plans:
        save(path, reviews)
        save(path.parent / "summary.json", report)
    print(f"Imported approved {form['reviewer_type']} decisions; reviewer identity is recorded explicitly.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("export", "import"))
    parser.add_argument("--results-root", type=Path)
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--file", type=Path, required=True)
    args = parser.parse_args()
    root = results_directory(args.results_root)
    (export_form if args.action == "export" else import_form)(root, args.split, args.file)


if __name__ == "__main__":
    main()
