"""Run a small API-level RAG evaluation against the demo PDF.

This script is intentionally simple: it checks whether answers and retrieved
context contain expected evidence terms. It is not a full LLM judge, but it is a
useful first validation layer for a portfolio RAG service.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF = PROJECT_ROOT / "data" / "sample" / "sample_tech_spec_ru.pdf"


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    question: str
    expected_answer_terms: list[str]
    expected_context_terms: list[str]
    min_answer_recall: float = 0.6
    min_context_recall: float = 0.6


@dataclass
class CaseResult:
    case_id: str
    question: str
    passed: bool
    answer_recall: float
    context_recall: float
    matched_answer_terms: list[str]
    missing_answer_terms: list[str]
    matched_context_terms: list[str]
    missing_context_terms: list[str]
    latency_seconds: float
    answer_preview: str


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = text.replace("ё", "е").replace("Ё", "Е")
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_matches(text: str, terms: list[str]) -> tuple[list[str], list[str]]:
    normalized = normalize_text(text)
    matched = []
    missing = []

    for term in terms:
        if normalize_text(term) in normalized:
            matched.append(term)
        else:
            missing.append(term)

    return matched, missing


def recall_score(matched: list[str], terms: list[str]) -> float:
    if not terms:
        return 1.0
    return len(matched) / len(terms)


def default_eval_cases() -> list[EvalCase]:
    return [
        EvalCase(
            case_id="payment_terms",
            question="Какие условия оплаты указаны в документе?",
            expected_answer_terms=["предоплата 0%", "100% по факту", "окончательная оплата 0%"],
            expected_context_terms=["условия оплаты", "предоплата 0%", "100% по факту"],
        ),
        EvalCase(
            case_id="connection_deadline",
            question="Какой срок подключения и срок оказания услуг?",
            expected_answer_terms=["15 календарных дней", "31 декабря 2026"],
            expected_context_terms=["15 календарных дней", "31 декабря 2026"],
        ),
        EvalCase(
            case_id="technical_requirements",
            question="Какие ключевые технические требования к интернет-каналу?",
            expected_answer_terms=["100 Мбит/с", "оптической", "статических IPv4"],
            expected_context_terms=["100 Мбит/с", "оптической", "IPv4"],
        ),
        EvalCase(
            case_id="supplier_risks",
            question="Какие основные риски для поставщика?",
            expected_answer_terms=["сжатые сроки", "оптического подключения", "штраф"],
            expected_context_terms=["потенциальные риски", "сжатые сроки", "штрафные санкции"],
        ),
    ]


def post_json(base_url: str, path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    response = requests.post(
        base_url.rstrip("/") + path,
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def upload_pdf(base_url: str, pdf_path: Path, language: str, timeout: int) -> dict[str, Any]:
    with pdf_path.open("rb") as handle:
        response = requests.post(
            base_url.rstrip("/") + "/upload",
            data={"language": language},
            files={"file": (pdf_path.name, handle, "application/pdf")},
            timeout=timeout,
        )
    response.raise_for_status()
    return response.json()


def evaluate_case(
    base_url: str,
    session_id: str,
    customer_bin: str,
    language: str,
    case: EvalCase,
    timeout: int,
) -> CaseResult:
    started = time.perf_counter()
    data = post_json(
        base_url,
        "/ask",
        {
            "session_id": session_id,
            "question": case.question,
            "customer_bin": customer_bin,
            "language": language,
        },
        timeout=timeout,
    )
    latency = time.perf_counter() - started

    answer = data.get("answer", "")
    context = data.get("context", "")

    matched_answer, missing_answer = split_matches(answer, case.expected_answer_terms)
    matched_context, missing_context = split_matches(context, case.expected_context_terms)

    answer_recall = recall_score(matched_answer, case.expected_answer_terms)
    context_recall = recall_score(matched_context, case.expected_context_terms)
    passed = answer_recall >= case.min_answer_recall and context_recall >= case.min_context_recall

    return CaseResult(
        case_id=case.case_id,
        question=case.question,
        passed=passed,
        answer_recall=answer_recall,
        context_recall=context_recall,
        matched_answer_terms=matched_answer,
        missing_answer_terms=missing_answer,
        matched_context_terms=matched_context,
        missing_context_terms=missing_context,
        latency_seconds=latency,
        answer_preview=answer[:500],
    )


def summarize_results(results: list[CaseResult]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for item in results if item.passed)
    avg_answer_recall = sum(item.answer_recall for item in results) / total if total else 0.0
    avg_context_recall = sum(item.context_recall for item in results) / total if total else 0.0
    avg_latency = sum(item.latency_seconds for item in results) / total if total else 0.0

    return {
        "cases": total,
        "passed": passed,
        "pass_rate": passed / total if total else 0.0,
        "avg_answer_recall": avg_answer_recall,
        "avg_context_recall": avg_context_recall,
        "avg_latency_seconds": avg_latency,
    }


def print_report(upload: dict[str, Any], results: list[CaseResult], summary: dict[str, Any]) -> None:
    print("RAG evaluation")
    print(f"- session_id: {upload.get('session_id')}")
    print(f"- filename: {upload.get('filename')}")
    print(f"- chunk_count: {upload.get('chunk_count')}")
    print(f"- vector_backend: {upload.get('vector_backend', 'unknown')}")
    print()

    print("Summary")
    print(f"- cases: {summary['cases']}")
    print(f"- passed: {summary['passed']}")
    print(f"- pass_rate: {summary['pass_rate']:.2f}")
    print(f"- avg_answer_recall: {summary['avg_answer_recall']:.2f}")
    print(f"- avg_context_recall: {summary['avg_context_recall']:.2f}")
    print(f"- avg_latency_seconds: {summary['avg_latency_seconds']:.2f}")
    print()

    for item in results:
        status = "PASS" if item.passed else "FAIL"
        print(f"[{status}] {item.case_id}")
        print(f"  answer_recall={item.answer_recall:.2f}, context_recall={item.context_recall:.2f}, latency={item.latency_seconds:.2f}s")
        if item.missing_answer_terms:
            print(f"  missing_answer_terms={item.missing_answer_terms}")
        if item.missing_context_terms:
            print(f"  missing_context_terms={item.missing_context_terms}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate demo RAG answers through the FastAPI backend.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--language", default="Русский")
    parser.add_argument("--customer-bin", default="123456789012")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    upload = upload_pdf(args.base_url, args.pdf, args.language, args.timeout)
    session_id = upload["session_id"]

    results = [
        evaluate_case(
            base_url=args.base_url,
            session_id=session_id,
            customer_bin=args.customer_bin,
            language=args.language,
            case=case,
            timeout=args.timeout,
        )
        for case in default_eval_cases()
    ]
    summary = summarize_results(results)

    print_report(upload, results, summary)

    payload = {
        "upload": upload,
        "summary": summary,
        "results": [asdict(item) for item in results],
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print()
        print(f"Wrote {args.output}")

    return 0 if summary["passed"] == summary["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
