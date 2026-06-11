import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import evaluate_rag  # noqa: E402


class EvaluateRagTests(unittest.TestCase):
    def test_normalize_text_handles_nbsp_case_and_spacing(self):
        text = "Предоплата\u00a00%,   100% ПО ФАКТУ"

        self.assertEqual(evaluate_rag.normalize_text(text), "предоплата 0%, 100% по факту")

    def test_split_matches_returns_matched_and_missing_terms(self):
        matched, missing = evaluate_rag.split_matches(
            "Срок подключения: 15 календарных дней.",
            ["15 календарных дней", "31 декабря 2026"],
        )

        self.assertEqual(matched, ["15 календарных дней"])
        self.assertEqual(missing, ["31 декабря 2026"])

    def test_summarize_results_calculates_pass_rate_and_averages(self):
        results = [
            evaluate_rag.CaseResult(
                case_id="one",
                question="q1",
                passed=True,
                answer_recall=1.0,
                context_recall=0.8,
                matched_answer_terms=[],
                missing_answer_terms=[],
                matched_context_terms=[],
                missing_context_terms=[],
                latency_seconds=2.0,
                answer_preview="",
            ),
            evaluate_rag.CaseResult(
                case_id="two",
                question="q2",
                passed=False,
                answer_recall=0.5,
                context_recall=0.4,
                matched_answer_terms=[],
                missing_answer_terms=[],
                matched_context_terms=[],
                missing_context_terms=[],
                latency_seconds=4.0,
                answer_preview="",
            ),
        ]

        summary = evaluate_rag.summarize_results(results)

        self.assertEqual(summary["cases"], 2)
        self.assertEqual(summary["passed"], 1)
        self.assertEqual(summary["pass_rate"], 0.5)
        self.assertAlmostEqual(summary["avg_answer_recall"], 0.75)
        self.assertAlmostEqual(summary["avg_context_recall"], 0.6)
        self.assertAlmostEqual(summary["avg_latency_seconds"], 3.0)

    def test_metric_key_replaces_unsafe_characters(self):
        self.assertEqual(
            evaluate_rag.metric_key("case", "technical requirements", "answer/recall"),
            "case_technical_requirements_answer_recall",
        )

    def test_normalize_mlflow_tracking_uri_accepts_paths_and_remote_uris(self):
        local_uri = evaluate_rag.normalize_mlflow_tracking_uri(".runtime/mlruns")

        self.assertTrue(local_uri.startswith("file://"))
        self.assertIn(".runtime/mlruns", local_uri)
        self.assertEqual(
            evaluate_rag.normalize_mlflow_tracking_uri("http://127.0.0.1:5000"),
            "http://127.0.0.1:5000",
        )

    def test_build_report_payload_serializes_case_results(self):
        result = evaluate_rag.CaseResult(
            case_id="payment_terms",
            question="q",
            passed=True,
            answer_recall=1.0,
            context_recall=1.0,
            matched_answer_terms=["предоплата 0%"],
            missing_answer_terms=[],
            matched_context_terms=["условия оплаты"],
            missing_context_terms=[],
            latency_seconds=0.5,
            answer_preview="preview",
        )

        payload = evaluate_rag.build_report_payload(
            upload={"filename": "sample.pdf"},
            results=[result],
            summary={"cases": 1, "passed": 1},
        )

        self.assertEqual(payload["upload"]["filename"], "sample.pdf")
        self.assertEqual(payload["summary"]["passed"], 1)
        self.assertEqual(payload["results"][0]["case_id"], "payment_terms")
        self.assertEqual(payload["results"][0]["matched_answer_terms"], ["предоплата 0%"])


if __name__ == "__main__":
    unittest.main()
