"""Check replay isolation, review provenance and cost arithmetic without API calls."""
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import experiment

from costs import estimate_usage, expression_tiers
from evaluation import summarize
from model_config import ModelSettings
from run_paths import artifact_path


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class ExperimentTests(unittest.TestCase):
    def settings(self):
        c = load(ROOT / "results/selection.json")["baseline"]
        return ModelSettings(model=c["model"], reasoning_effort=c["reasoning_effort"])

    def test_resume_frozen_selection_does_not_modify_any_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "replay"
            shutil.copytree(ROOT / "results", output)
            before = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
            for stage in ("select", "dev"):
                with (patch.object(sys, "argv", ["experiment.py", stage, "--resume", "--results-root", str(output)]),
                      patch.object(experiment, "settings_from_env", return_value=self.settings()),
                      patch.object(experiment, "client_from_env", side_effect=AssertionError("No API client expected")),
                      contextlib.redirect_stdout(io.StringIO())):
                    experiment.main()
            after = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
            self.assertEqual(before, after)

    def test_new_named_review_selection_is_portable_and_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "independent"
            questions = [q for q in load(ROOT / "data/questions.json") if q["split"] == "dev"]
            for config in load(ROOT / "configs/experiments.json"):
                folder = output / config["name"] / "dev"
                shutil.copytree(ROOT / "results" / config["name"] / "dev", folder)
                reviews = load(folder / "reviews.json")
                for r in reviews:
                    r.pop("codex_verified", None)
                    r.update(review_status="reviewed", reviewed_by="Test fixture reviewer")
                (folder / "reviews.json").write_text(json.dumps(reviews), encoding="utf-8")
                report = summarize(questions, load(folder / "traces.json"), reviews)
                (folder / "summary.json").write_text(json.dumps(report), encoding="utf-8")
            with (patch.object(sys, "argv", ["experiment.py", "select", "--results-root", str(output)]),
                  patch.object(experiment, "settings_from_env", return_value=self.settings()),
                  contextlib.redirect_stdout(io.StringIO())):
                experiment.main()
            selection = load(output / "selection.json")
            self.assertEqual(selection["selected"]["name"], "hybrid-wide")
            self.assertTrue(all(not p.startswith("results/") for p in selection["dev_artifact_sha256"]))
            relocated = Path(tmp) / "relocated"
            shutil.copytree(output, relocated)
            experiment.verify_selection(relocated, selection, load(ROOT / "data/benchmark_freeze.json"))

    def test_legacy_paths_resolve_inside_selected_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(artifact_path(root, r"results\baseline\dev\traces.json"), root / "baseline/dev/traces.json")
            with self.assertRaises(ValueError):
                artifact_path(root, "../outside.json")

    def test_cached_tokens_are_not_charged_as_uncached_input(self):
        card = load(ROOT / "data/pricing/modelapi-gpt-6.1-sol.json")
        cost = estimate_usage({"input_tokens": 1000, "output_tokens": 100,
                               "input_tokens_details": {"cached_tokens": 400}}, card)
        self.assertEqual(cost, Decimal("0.00224"))

    def test_context_tier_is_applied_per_request(self):
        card = load(ROOT / "data/pricing/modelapi-gpt-6.1-sol.json")
        self.assertEqual(estimate_usage({"input_tokens": 500000, "output_tokens": 0}, card), Decimal(2))

    def test_invalid_pricing_and_usage_are_rejected(self):
        with self.assertRaises(ValueError):
            expression_tiers("__import__('os').system('echo invalid')")
        with self.assertRaises(ValueError):
            estimate_usage({"input_tokens": 1, "input_tokens_details": {"cached_tokens": 2}}, {})


if __name__ == "__main__":
    unittest.main()
