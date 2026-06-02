import asyncio
import importlib
import io
import os
import sys
import types
import unittest

from fastapi import HTTPException, UploadFile


def load_main_module():
    fake_services = types.ModuleType("services")
    fake_services.analyze_risks = lambda chunks, index, language, key_fields=None: "risk-ok"
    fake_services.answer_question = (
        lambda question, chunks, index, language, key_fields=None: ("answer-ok", "ctx-ok")
    )
    fake_services.extract_json_fields = (
        lambda chunks, index, customer_bin, language, key_fields=None: '{"ok": true}'
    )
    fake_services.generate_summary = (
        lambda chunks, index, customer_bin, language, key_fields=None: "summary-ok"
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

    for module_name in ["config", "runtime_store", "llm_clients", "main"]:
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
        with unittest.mock.patch.object(main, "_check_ollama_ready", return_value=""):
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


if __name__ == "__main__":
    unittest.main()
