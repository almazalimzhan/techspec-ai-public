import importlib
import os
import sys
import types
import unittest
from unittest.mock import patch


def _clear_modules():
    for module_name in ["config", "llm_clients"]:
        sys.modules.pop(module_name, None)


class LlmClientsTests(unittest.TestCase):
    def test_llm_chat_uses_litellm_when_configured(self):
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "litellm",
                "LLM_MODEL": "gemma3-27b-32bit",
                "LITELLM_BASE_URL": "https://example.test/v1",
                "LITELLM_API_KEY": "test-api-key",
            },
            clear=False,
        ):
            _clear_modules()
            with patch("requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {
                    "choices": [{"message": {"content": "hello"}}]
                }

                llm_clients = importlib.import_module("llm_clients")
                result = llm_clients.llm_chat("sys", "user", temperature=0.2)

        self.assertEqual(result, "hello")
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["model"], "gemma3-27b-32bit")
        self.assertEqual(kwargs["json"]["temperature"], 0.2)

    def test_ready_check_uses_models_endpoint_for_litellm(self):
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "litellm",
                "LITELLM_BASE_URL": "https://example.test/v1",
                "LITELLM_API_KEY": "test-api-key",
            },
            clear=False,
        ):
            _clear_modules()
            with patch("requests.get") as mock_get:
                mock_get.return_value.status_code = 200
                llm_clients = importlib.import_module("llm_clients")
                error = llm_clients.check_llm_backend_ready()

        self.assertEqual(error, "")
        mock_get.assert_called_once()

    def test_ready_check_reports_missing_litellm_url(self):
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "litellm",
                "LITELLM_BASE_URL": "",
                "LITELLM_API_KEY": "",
            },
            clear=False,
        ):
            _clear_modules()
            llm_clients = importlib.import_module("llm_clients")
            error = llm_clients.check_llm_backend_ready()

        self.assertIn("LITELLM_BASE_URL is required", error)

    def test_ensure_language_only_normalizes_russian(self):
        _clear_modules()
        llm_clients = importlib.import_module("llm_clients")

        with patch.object(llm_clients, "ensure_russian", return_value="fixed-ru") as mock_ensure:
            self.assertEqual(llm_clients.ensure_language("mixed", "Русский"), "fixed-ru")
            self.assertEqual(llm_clients.ensure_language("mixed", "Қазақша"), "mixed")

        mock_ensure.assert_called_once_with("mixed")


if __name__ == "__main__":
    unittest.main()
