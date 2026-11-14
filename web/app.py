"""Small browser demo for the Day 7 RAG pipeline."""
import argparse
import json
import mimetypes
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_run import client_from_env, run_agent
from day6_store import corpus_hash
from model_config import settings_from_env
from retrievers import Retriever

WEB_ROOT = ROOT / "web"
CHUNKS = json.loads((ROOT / "data/chunks.json").read_text(encoding="utf-8"))
QUESTIONS = json.loads((ROOT / "data/questions.json").read_text(encoding="utf-8"))
CONFIG = json.loads((ROOT / "results/selection.json").read_text(encoding="utf-8"))["selected"]
TRACE_PATHS = [ROOT / "results/hybrid-wide/test/traces.json", ROOT / "results/hybrid-wide/dev/traces.json"]
TRACES = []
for path in TRACE_PATHS:
    if path.exists():
        TRACES.extend(json.loads(path.read_text(encoding="utf-8")))
TRACE_BY_ID = {trace["query_id"]: trace for trace in TRACES}
TRACE_BY_QUESTION = {q["question"].casefold(): TRACE_BY_ID[q["id"]]
                     for q in QUESTIONS if q["id"] in TRACE_BY_ID}
CHUNK_BY_ID = {chunk["id"]: chunk for chunk in CHUNKS}
LIVE_RETRIEVER = None
LIVE_LOCK = threading.Lock()


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def source_rows(trace):
    rows = {}
    searches = [event for event in trace.get("events", []) if event.get("event") == "search"]
    final_ids = searches[-1].get("context_ids", []) if searches else []
    for event in searches:
        for row in event.get("results", []):
            rows[row["id"]] = row
    result = []
    for rank, chunk_id in enumerate(final_ids, 1):
        row = rows.get(chunk_id) or CHUNK_BY_ID.get(chunk_id, {})
        if row:
            result.append({"rank": rank, "id": chunk_id, "source": row.get("source", ""),
                          "page": row.get("page", ""), "text": row.get("text", ""),
                          "score": row.get("score")})
    return result


def view_trace(trace, *, mode, config=None):
    searches = [event for event in trace.get("events", []) if event.get("event") == "search"]
    return {"mode": mode, "query_id": trace.get("query_id"), "question": trace.get("question", ""),
            "status": trace.get("status"), "answer": trace.get("answer", ""),
            "citations": trace.get("citations", []), "sources": source_rows(trace),
            "searches": [{"query": event.get("query", ""), "result_count": len(event.get("results", [])),
                          "context_ids": event.get("context_ids", []), "context": event.get("context", "")} for event in searches],
            "elapsed_ms": trace.get("elapsed_ms"), "usage": trace.get("usage", {}), "config": config or CONFIG}


def question_list():
    preferred = {qid: rank for rank, qid in enumerate(("T02", "T-U02", "Q01", "Q11", "T01", "T05"))}
    return [{"id": q["id"], "split": q["split"], "question": q["question"],
             "status": TRACE_BY_ID[q["id"]].get("status")}
            for q in sorted(QUESTIONS, key=lambda q: preferred.get(q["id"], 99)) if q["id"] in TRACE_BY_ID]


def ask_saved(question):
    trace = TRACE_BY_QUESTION.get(question.strip().casefold())
    if trace is None:
        return {"error": "Câu hỏi chưa có trace lưu sẵn. Hãy bật Live model."}, 404
    return view_trace(trace, mode="saved"), 200


def ask_live(question):
    global LIVE_RETRIEVER
    settings = settings_from_env()
    config = settings.apply(CONFIG)
    filters = next((q.get("filter") for q in QUESTIONS if q["question"].casefold() == question.casefold()), None)
    with LIVE_LOCK:
        if LIVE_RETRIEVER is None:
            LIVE_RETRIEVER = Retriever(CHUNKS, CONFIG["method"])
        with client_from_env(settings=settings) as client:
            result = run_agent({"question": question, "filter": filters}, LIVE_RETRIEVER, client, config)
    result["question"] = question
    return view_trace(result, mode="live", config=config), 200


class Handler(BaseHTTPRequestHandler):
    server_version = "Day7Demo/1.0"

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def send_json(self, value, status=200):
        payload = json_bytes(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def send_file(self, path):
        payload = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", (mimetypes.guess_type(path.name)[0] or "application/octet-stream") + "; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/api/health":
            return self.send_json({"status": "ok", "corpus_chunks": len(CHUNKS),
                                   "corpus_sha256": corpus_hash(CHUNKS), "selected": CONFIG["name"]})
        if route == "/api/questions":
            return self.send_json({"questions": question_list(), "selected": CONFIG,
                                   "saved_trace_count": len(TRACE_BY_ID)})
        if route in ("/", "/index.html"):
            return self.send_file(WEB_ROOT / "index.html")
        if route in ("/app.js", "/style.css", "/logo.svg"):
            return self.send_file(WEB_ROOT / route.lstrip("/"))
        return self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/ask":
            return self.send_json({"error": "Not found"}, 404)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 16384:
                return self.send_json({"error": "Invalid request size."}, 400)
            body = json.loads(self.rfile.read(length) or b"{}")
            origin = self.headers.get("Origin")
            if origin and origin != f"http://{self.headers.get('Host')}":
                return self.send_json({"error": "Origin is not allowed."}, 403)
            if not isinstance(body, dict):
                return self.send_json({"error": "Expected a JSON object."}, 400)
            question, mode = body.get("question", ""), body.get("mode", "saved")
            if mode not in ("saved", "live"):
                return self.send_json({"error": "Unknown demo mode."}, 400)
            if not isinstance(question, str) or not question.strip() or len(question) > 1000:
                return self.send_json({"error": "Question must be 1-1000 characters."}, 400)
            result, status = ask_live(question) if mode == "live" else ask_saved(question)
            return self.send_json(result, status)
        except (ValueError, json.JSONDecodeError):
            return self.send_json({"error": "Yêu cầu không hợp lệ. Kiểm tra câu hỏi và cấu hình model."}, 400)
        except Exception as exc:  # noqa: BLE001 -- HTTP boundary; do not expose credentials or provider payloads.
            print(f"Demo request failed: {type(exc).__name__}")
            return self.send_json({"error": "Không chạy được model. Kiểm tra kết nối, cấu hình API và quota."}, 502)


def main():
    parser = argparse.ArgumentParser(description="Day 7 browser demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Day 7 demo: http://{args.host}:{args.port}")
    print("Saved trace mode is free; Live model mode uses the configured API.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping demo.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
