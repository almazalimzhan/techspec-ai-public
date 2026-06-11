import asyncio
import importlib
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient


def load_main_module():
    fake_services = types.ModuleType("services")
    fake_services.analyze_risks = lambda chunks, index, language, key_fields=None, session_id=None: "risk-ok"
    fake_services.answer_question = (
        lambda question, chunks, index, language, key_fields=None, session_id=None: ("answer-ok", "ctx-ok")
    )
    fake_services.extract_json_fields = (
        lambda chunks, index, customer_bin, language, key_fields=None, session_id=None: '{"ok": true}'
    )
    fake_services.generate_summary = (
        lambda chunks, index, customer_bin, language, key_fields=None, session_id=None: "summary-ok"
    )
    fake_services.prepare_document = (
        lambda pdf_bytes, language: (["chunk-1"], "fake-index", "preview-text", {"subject": "demo"})
    )

    fake_logging = types.ModuleType("logging_utils")
    fake_logging.log_usage = lambda *args, **kwargs: None
    fake_python_multipart = types.ModuleType("python_multipart")
    fake_python_multipart.__version__ = "0.0.13"
    fake_ollama = types.ModuleType("ollama")
    fake_ollama.list = lambda: {"models": []}
    os.environ["SESSION_BACKEND"] = "memory"
    os.environ["LLM_PROVIDER"] = "ollama"
    os.environ["VECTOR_BACKEND"] = "faiss"

    for module_name in ["config", "runtime_store", "llm_clients", "qdrant_store", "main"]:
        sys.modules.pop(module_name, None)

    with unittest.mock.patch.dict(
        sys.modules,
        {
            "services": fake_services,
            "logging_utils": fake_logging,
            "python_multipart": fake_python_multipart,
            "ollama": fake_ollama,
        },
    ):
        return importlib.import_module("main")


class MainEndpointTests(unittest.TestCase):
    def test_upload_and_followup_actions(self):
        main = load_main_module()
        upload = UploadFile(filename="demo.pdf", file=io.BytesIO(b"%PDF-1.4 demo"))

        response = asyncio.run(main.upload_pdf(upload, "Русский"))
        summary = main.get_summary(
            main.AnalyzeRequest(
                session_id=response["session_id"],
                customer_bin="123456789012",
                language="Русский",
            )
        )
        answer = main.ask_question(
            main.AskRequest(
                session_id=response["session_id"],
                question="Каков срок поставки?",
                customer_bin="",
                language="Русский",
            )
        )

        self.assertEqual(response["filename"], "demo.pdf")
        self.assertEqual(summary["result"], "summary-ok")
        self.assertEqual(answer["answer"], "answer-ok")
        with unittest.mock.patch.object(main, "_check_embedding_backend_ready", return_value=""):
            ready = main.ready()
        self.assertEqual(ready["embeddings"], "ok")
        self.assertEqual(ready["llm"], "ok")

    def test_rejects_large_uploads(self):
        main = load_main_module()
        main.MAX_UPLOAD_BYTES = 4
        upload = UploadFile(filename="demo.pdf", file=io.BytesIO(b"12345"))

        with self.assertRaises(HTTPException) as exc:
            asyncio.run(main.upload_pdf(upload, "Русский"))

        self.assertEqual(exc.exception.status_code, 413)

    def test_metrics_endpoint_renders_prometheus_text(self):
        main = load_main_module()
        main.metrics.record_request("GET", "/health", 200, 0.012)

        response = main.get_metrics()

        self.assertIn("techspec_app_uptime_seconds", response)
        self.assertIn("techspec_http_requests_total", response)
        self.assertIn('method="GET",path="/health",status="200"', response)

    def test_health_request_is_recorded_by_metrics_middleware(self):
        main = load_main_module()
        client = TestClient(main.app)

        health_response = client.get("/health")
        metrics_response = client.get("/metrics")

        self.assertEqual(health_response.status_code, 200)
        self.assertIn('method="GET",path="/health",status="200"', metrics_response.text)

    def test_latest_eval_report_reads_runtime_json(self):
        main = load_main_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "rag_eval_latest.json"
            report_path.write_text(
                json.dumps({"summary": {"pass_rate": 1.0}, "results": []}),
                encoding="utf-8",
            )
            main.EVAL_REPORT_FILE = report_path

            response = main.get_latest_eval_report()

        self.assertEqual(response["status"], "ready")
        self.assertEqual(response["report"]["summary"]["pass_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
