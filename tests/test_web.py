"""Demo contracts: replay stays offline, live uses settings, errors hide credentials."""
import contextlib
import http.client
import importlib.util
import io
import json
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("day7_web_app", ROOT / "web/app.py")
web = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = web
spec.loader.exec_module(web)


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = web.ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path, body=None, headers=None):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        with patch.object(web.Handler, "log_message"):
            client.request("POST" if body is not None else "GET", path,
                           body=json.dumps(body) if body is not None else None,
                           headers={"Content-Type": "application/json", **(headers or {})})
            response = client.getresponse()
            data = response.read()
            status = response.status
        client.close()
        return status, data

    def test_saved_answer_and_abstention_preserve_context_without_api(self):
        with patch.object(web, "client_from_env", side_effect=AssertionError("No API in replay")):
            for qid, expected in (("T02", "answered"), ("T-U02", "abstain")):
                question = next(q["question"] for q in web.QUESTIONS if q["id"] == qid)
                status, payload = self.request("/api/ask", {"question": question, "mode": "saved"})
                result = json.loads(payload)
                self.assertEqual(status, 200)
                self.assertEqual(result["status"], expected)
                self.assertEqual(result["mode"], "saved")
                self.assertTrue(result["searches"][0]["context"])
                self.assertTrue(set(result["citations"]).issubset({s["id"] for s in result["sources"]}))

    def test_static_routes_do_not_serve_python_or_project_secrets(self):
        for path in ("/app.py", "/../.env", "/.env", "/README.md"):
            self.assertEqual(self.request(path)[0], 404)
        self.assertEqual(self.request("/")[0], 200)
        self.assertEqual(self.request("/app.js")[0], 200)

    def test_invalid_input_and_cross_origin_are_rejected(self):
        for body in ([], {"question": ""}, {"question": "x", "mode": "unknown"}):
            self.assertEqual(self.request("/api/ask", body)[0], 400)
        self.assertEqual(self.request("/api/ask", {"question": "x"}, {"Origin": "https://other.invalid"})[0], 403)

    def test_live_error_does_not_return_provider_exception_text(self):
        with (patch.object(web, "ask_live", side_effect=RuntimeError("test-private-key")),
              contextlib.redirect_stdout(io.StringIO())):
            status, payload = self.request("/api/ask", {"question": "x", "mode": "live"})
        self.assertEqual(status, 502)
        self.assertNotIn(b"test-private-key", payload)

    def test_live_uses_configured_model_and_closes_client(self):
        settings = SimpleNamespace(apply=lambda config: {**config, "model": "configured-test-model"})
        client = MagicMock()
        with (patch.object(web, "settings_from_env", return_value=settings),
              patch.object(web, "LIVE_RETRIEVER", object()),
              patch.object(web, "client_from_env", return_value=client),
              patch.object(web, "run_agent", return_value={"status": "abstain", "answer": "No evidence", "events": []}) as agent):
            result, status = web.ask_live("a new question")
        self.assertEqual(status, 200)
        self.assertEqual(result["config"]["model"], "configured-test-model")
        self.assertEqual(agent.call_args.args[0], {"question": "a new question", "filter": None})
        client.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
