"""Regression checks for the real pipeline contracts, without API calls."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agent_run import client_from_env, run_agent, run_batch
from model_config import settings_from_env
from retrievers import evidence_hit, measure

CHUNK = {"id": "c1", "text": "Returns a new list. The original is unchanged.",
         "source_id": "doc", "source": "doc.txt", "page": "unit:001", "metadata": {}, "score": 0.8}
CONFIG = {"name": "unit", "method": "lexical", "model": "test-only",
          "reasoning_effort": "low", "top_k": 3, "budget": 800, "max_searches": 1}


def response(output):
    return SimpleNamespace(model_dump=lambda **kwargs: {"id": "unit-response", "status": "completed",
        "model": "test-only", "usage": {"input_tokens": 10, "output_tokens": 5}, "output": output})


class Client:
    def __init__(self, outputs):
        self.outputs, self.requests = iter(outputs), []
        self.responses = self

    def create(self, **kwargs):
        self.requests.append(json.loads(json.dumps(kwargs)))
        return response(next(self.outputs))


class Search:
    def search(self, query, **kwargs):
        return [CHUNK]


def final(citation="c1"):
    return [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(
        {"status": "answered", "answer": f"A new list; source unchanged [{citation}]", "citations": [citation]})}]}]


CALL = [{"type": "function_call", "name": "search", "arguments": '{"query":"rewritten"}', "call_id": "call1"}]


class Day7Tests(unittest.TestCase):
    def test_project_env_configures_api_client_without_exporting_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("OPENAI_API_KEY=test-secret\nOPENAI_MODEL=configured-model\n"
                                       "OPENAI_BASE_URL=https://example.invalid/v1\n", encoding="utf-8-sig")
            with patch("model_config.ROOT", root), patch.dict(os.environ, {}, clear=True), patch("openai.OpenAI") as factory:
                settings = settings_from_env()
                client = client_from_env(settings=settings)
                factory.assert_called_once_with(api_key="test-secret", base_url="https://example.invalid/v1",
                                                timeout=90, max_retries=1)
                self.assertIs(client, factory.return_value)
                self.assertEqual(settings.reasoning_effort, "low")
                self.assertNotIn("test-secret", repr(settings))
                self.assertNotIn("OPENAI_API_KEY", os.environ)

    def test_env_model_and_reasoning_override_experiment_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("OPENAI_MODEL=configured-model\nOPENAI_REASONING_EFFORT=high\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                config = settings_from_env(path).apply(CONFIG)
            client = Client([CALL, final()])
            result = run_agent({"question": "q"}, Search(), client, config)
            self.assertEqual(result["status"], "answered")
            self.assertTrue(all(r["model"] == "configured-model" for r in client.requests))
            self.assertTrue(all(r["reasoning"] == {"effort": "high"} for r in client.requests))
            self.assertEqual(CONFIG["model"], "test-only")

    def test_process_environment_wins_and_env_file_can_be_reloaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("OPENAI_MODEL=first-model\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(settings_from_env(path).model, "first-model")
                path.write_text("OPENAI_MODEL=second-model\n", encoding="utf-8")
                self.assertEqual(settings_from_env(path).model, "second-model")
                with patch.dict(os.environ, {"OPENAI_MODEL": "process-model"}):
                    self.assertEqual(settings_from_env(path).model, "process-model")
                self.assertNotIn("OPENAI_MODEL", os.environ)

    def test_missing_model_reports_required_env_variable(self):
        with (tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True),
              self.assertRaisesRegex(ValueError, "OPENAI_MODEL")):
            settings_from_env(Path(tmp) / ".env")

    def test_hit3_does_not_include_rank4(self):
        results = [{**CHUNK, "text": "unrelated", "id": str(i)} for i in range(3)] + [CHUNK]
        gold = [{"source_id": "doc", "page": "unit:001", "evidence": "Returns a new list."}]
        metrics = measure(results, gold, ["c1"])
        self.assertFalse(metrics["hit3"])
        self.assertTrue(metrics["context_hit"])

    def test_evidence_requires_full_quote_and_provenance(self):
        gold = [{"source_id": "doc", "page": "unit:001", "evidence": "Returns a new\nlist."}]
        self.assertTrue(evidence_hit(CHUNK, gold))
        self.assertFalse(evidence_hit({**CHUNK, "page": "unit:002"}, gold))
        self.assertFalse(evidence_hit({**CHUNK, "text": "Returns a new"}, gold))

    def test_model_tools_citations_and_no_gold(self):
        client = Client([CALL, final()])
        result = run_agent({"question": "How does sorting work?"}, Search(), client, CONFIG)
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["events"][1]["query"], "How does sorting work?")
        self.assertEqual(result["usage"]["input_tokens"], 20)
        self.assertEqual(client.requests[0]["tool_choice"], "required")
        self.assertNotIn("gold", json.dumps(client.requests))

    def test_out_of_context_citation_is_rejected(self):
        result = run_agent({"question": "q"}, Search(), Client([CALL, final("invented")]), CONFIG)
        self.assertEqual(result["status"], "abstain")
        self.assertEqual(result["citations"], [])

    def test_inline_citation_on_abstention_is_counted(self):
        cid = "a" * 64
        class CitedSearch:
            def search(self, query, **kwargs):
                return [{**CHUNK, "id": cid}]
        output = [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({
            "status": "abstain", "answer": f"No benchmark number is given; the source describes list behavior [{cid}].",
            "citations": []})}]}]
        result = run_agent({"question": "Which benchmark number?"}, CitedSearch(), Client([CALL, output]), CONFIG)
        self.assertEqual(result["status"], "abstain")
        self.assertEqual(result["citations"], [cid])

    def test_resume_rejects_changed_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "traces.json"
            path.write_text(json.dumps([{"query_id": "q", "config_sha256": "wrong"}]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Resume blocked"):
                run_batch([{"id": "q", "question": "q"}], [CHUNK], CONFIG, tmp, None, resume=True)

    def test_provider_failure_propagates_without_fake_answer(self):
        client = Client([])
        with patch.object(client, "create", side_effect=ConnectionError("offline")), self.assertRaises(ConnectionError):
            run_agent({"question": "q"}, Search(), client, CONFIG)


if __name__ == "__main__":
    unittest.main()
