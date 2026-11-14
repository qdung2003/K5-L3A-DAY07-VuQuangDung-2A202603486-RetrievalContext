"""Price saved agent and audit usage without modifying frozen benchmark artifacts."""
import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agent_run import save
from costs import estimate_calls, expression_tiers
from model_config import settings_from_env
from run_paths import results_directory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path)
    parser.add_argument("--pricing", type=Path, default=ROOT / "data/pricing/modelapi-gpt-6.1-sol.json")
    parser.add_argument("--fetch-pricing", action="store_true", help="Fetch only public pricing from the configured provider")
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    results_root = results_directory(args.results_root)
    if args.fetch_pricing:
        import requests
        settings = settings_from_env(args.env_file)
        parsed = urlsplit(settings.base_url)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            raise ValueError("Public price source must use HTTPS without embedded credentials")
        url = f"https://{parsed.netloc}/api/pricing"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        payload = response.json()
        record = next(row for row in payload["data"] if row["model_name"] == settings.model)
        expression_tiers(record["billing_expr"])
        card = {"model": settings.model, "source_url": url, "retrieved_at": datetime.now(UTC).isoformat(),
                "unit": "USD per million tokens", "billing_expr": record["billing_expr"],
                "pricing_version": payload.get("pricing_version"),
                "group_multipliers": {name: payload["group_ratio"][name] for name in record["enable_groups"]},
                "basis": "Published expression rates before account/group multiplier. p=uncached input, c=output, cr=cache read, cc=cache write. Frontend labels rates USD per 1M tokens.",
                "limitations": "Current public rates applied retrospectively. Actual account group, discounts, prior prices, unsuccessful probes and unrecorded judge attempts are not known. This is an estimate, not an invoice."}
        save(args.pricing, card)
    card = json.loads(args.pricing.read_text(encoding="utf-8"))
    groups = list(card["group_multipliers"].values())
    entries = []
    for path in sorted(results_root.glob("*/*/traces.json")):
        if path.parent.parent.name == "retrieval":
            continue
        traces = json.loads(path.read_text(encoding="utf-8"))
        usages = []
        for t in traces:
            for event in t.get("events", []):
                if event["event"] == "model":
                    if event.get("model") != card["model"]:
                        raise ValueError("Saved model differs from rate card")
                    usages.append(event["usage"])
        amount = estimate_calls(usages, card)
        review_path = path.parent / "reviews.json"
        reviews = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else []
        if any(r.get("judge_model", card["model"]) != card["model"] for r in reviews):
            raise ValueError("Saved audit model differs from rate card")
        audit = estimate_calls([r["judge_usage"] for r in reviews if r.get("judge_usage")], card)
        entries.append({"configuration": path.parent.parent.name, "split": path.parent.name,
            "agent_estimate_usd_before_group": amount, "audit_estimate_usd_before_group": audit,
            "agent_group_range_usd": [amount * min(groups), amount * max(groups)],
            "trace_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "reviews_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest() if review_path.exists() else None,
            "input_tokens": sum(u.get("input_tokens", 0) for u in usages),
            "output_tokens": sum(u.get("output_tokens", 0) for u in usages)})
    report = {"pricing": card, "pricing_sha256": hashlib.sha256(args.pricing.read_bytes()).hexdigest(),
              "kind": "estimate", "account_invoice_verified": False, "runs": entries,
              "agent_total_usd_before_group": sum(r["agent_estimate_usd_before_group"] for r in entries),
              "audit_total_usd_before_group": sum(r["audit_estimate_usd_before_group"] for r in entries)}
    save(results_root / "costs.json", report)
    print(json.dumps({k: v for k, v in report.items() if k not in ("pricing", "runs")}, indent=2))


if __name__ == "__main__":
    main()
