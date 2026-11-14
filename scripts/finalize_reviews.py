"""Record Codex's direct trace inspection and explicit corrections to AI labels."""
import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agent_run import digest, save
from evaluation import summarize

BASE_REASONS = {
    "Q02": "Read controlflow:003: break, return and raised exception all skip loop else; answer includes all three.",
    "Q03": "Read controlflow:011 definition-time evaluation, shared mutable default example, and None alternative; answer matches all claims.",
    "Q04": "Read controlflow:013: slash separator, position order, and no keyword arguments; all requested conditions present.",
    "Q05": "Read datastructures:003: deque and fast appends/pops at both ends; list beginning shifts are also explicitly described.",
    "Q06": "Read datastructures:007: one-item tuple requires trailing comma and parentheses alone are insufficient.",
    "Q07": "Read datastructures:007: set() makes empty set and {} makes empty dictionary; both parts answered.",
    "Q08": "Read datastructures:009: list(d) preserves insertion order and sorted(d) sorts keys; both parts answered.",
    "Q09": "Read modules:003 import-star paragraph: underscore-prefixed names excluded.",
    "Q10": "Read modules:003: once-per-session import, importlib.reload and restart alternative explicitly support answer.",
    "Q12": "Read inputoutput:007: with closes the file even on exception and is shorter than try/finally.",
    "Q13": "Read inputoutput:007: omitted/negative size reads entire contents, text/bytes modes and memory warning support answer.",
    "Q14": "Read inputoutput:010: JSON text must use UTF-8 for both reading and writing.",
    "Q15": "Read errors:005: else follows except handlers, runs only on no exception, and avoids catching unrelated exceptions.",
    "D-U01": "Read queue/deque passages and full-corpus absence check: qualitative efficiency only, no Core i7 millisecond benchmark. Abstention adds no numeric claim; cited deque description is supported.",
    "D-U02": "Read JSON passages and full-corpus absence check: json.load example and encoding guidance, no guaranteed MB limit. Abstention does not invent a limit; citation supports the qualitative explanation."
}

INSPECTED_DEV_TRACES = {
    "baseline": "2cfa82a0fbff3a4ad6d0140391918bebd28fa6983ba0d9ecdb3a1da190027c9a",
    "dense-wide": "4d2bf2eca841187ee1663628a5eec0fef0bcc611b5a098c100c3c46054c00551",
    "hybrid": "4ef2d1d0bebf3360c8bf90259c2f90f8b36e0851cfd53c5336e2cb3255431a3b",
    "hybrid-wide": "b16941bf78c86c57c86e61cf49792411a3c3deda7932d2533d8f3f7d650467c5",
    "lexical": "e40194509a349f7691a3667017db07e1e3bbfbeb88a7919a87a10fa0cf7359e9"
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--decisions", type=Path, help="Explicit per-run test inspection decisions")
    args = parser.parse_args()
    if args.split == "dev" and (ROOT / "results/selection.json").exists():
        raise ValueError("Dev labels are frozen after selection")
    def load(path):
        return json.loads(path.read_text(encoding="utf-8"))
    questions = [q for q in load(ROOT / "data/questions.json") if q["split"] == args.split]
    decisions = load(args.decisions) if args.decisions else {}
    changes = []
    for path in sorted((ROOT / "results").glob(f"*/{args.split}/reviews.json")):
        if path.parent.parent.name == "retrieval":
            continue
        name = path.parent.parent.name
        expected = INSPECTED_DEV_TRACES.get(name) if args.split == "dev" else decisions.get(name, {}).get("_trace_sha256")
        if not expected or hashlib.sha256((path.parent / "traces.json").read_bytes()).hexdigest() != expected:
            raise ValueError("These traces were not the outputs directly inspected by Codex; perform a new review")
        traces = load(path.parent / "traces.json")
        by_id = {t["query_id"]: t for t in traces}
        reviews = load(path)
        for r in reviews:
            qid = r["query_id"]
            if r["trace_sha256"] != digest(by_id[qid]):
                raise ValueError("Review/trace mismatch")
            original = {k: r[k] for k in ("answer_grade", "context_grade", "citation_support", "note", "context_reason")}
            if args.split == "dev":
                reason = BASE_REASONS.get(qid)
                if qid == "Q01":
                    if name == "hybrid-wide":
                        reason = "Read controlflow:003 in final context: explicit innermost enclosing for/while rule and code; cited passage fully supports answer."
                    elif name == "dense-wide":
                        reason = "Read controlflow:004 prime-loop example and output: break ends inner loop while outer loop continues. Accept the scoped answer as a supported inference from the example; explicit gold rule is absent, so exact evidence metric remains a miss."
                    else:
                        reason = "Read final context: only loop-else/break discussion, no nested-loop exit rule; abstention on this answerable question is grade 0, context is partial."
                if qid == "Q11":
                    if name == "baseline":
                        r.update(answer_grade=1, citation_support=[False], context_grade=1)
                        r["note"] = "Correct value, but cited classes:003 only calls top-level code a module named __main__; it does not establish the __name__ assignment. Partial grounding, not full credit."
                        reason = "Read classes:003 and other final chunks directly. Downgraded AI judge grade 2 to 1 because the variable-assignment claim is not established by the cited passage."
                    elif name == "dense-wide":
                        reason = "Read both search contexts: indirect __main__ namespace reference only; no explicit assignment. Abstention on an answerable question earns 0. Extra retrieval does not guarantee better coverage."
                    else:
                        reason = "Read modules:004 __name__ == __main__ guard and explanation that guarded code runs only as main file. This code and explanation support the answer although the frozen exact gold quote is elsewhere."
                if not reason:
                    raise ValueError(f"Missing recorded inspection: {qid}")
            else:
                decision = decisions.get(name, {}).get(qid)
                if not decision:
                    raise ValueError(f"Missing explicit test inspection: {name}/{qid}")
                reason = decision["reason"]
                r.update({k: v for k, v in decision.items() if k != "reason"})
            after = {k: r[k] for k in original}
            if after != original:
                changes.append({"configuration": name, "query_id": qid, "before": original, "after": after})
            r.update(codex_verified=True, codex_reason=reason, reviewed_by="AI judge + Codex direct source inspection",
                     codex_reviewed_at=datetime.now(UTC).isoformat(), human_reviewed=False)
        save(path, reviews)
        save(path.parent / "summary.json", summarize(questions, traces, reviews))
    save(ROOT / f"results/codex-{args.split}-review.json", {"reviewer": "Codex (AI)",
         "method": "Read original answers, cited chunks, source-unit text, final context and judge reasons; no human review claimed.",
         "changes": changes, "human_review_complete": False})


if __name__ == "__main__":
    main()
