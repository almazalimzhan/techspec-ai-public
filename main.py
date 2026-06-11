"""
FastAPI backend — замена Streamlit app.py
"""
import logging
import secrets
import time
import uuid
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from config import (
    API_AUTH_TOKEN,
    CORS_ALLOW_ORIGINS,
    LLM_PROVIDER,
    MAX_UPLOAD_BYTES,
    RATE_LIMIT_MAX_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    SUPPORTED_LANGUAGES,
    VECTOR_BACKEND,
)
from logging_utils import log_usage
from metrics import metrics
from qdrant_store import QdrantError, check_qdrant_ready, is_qdrant_enabled, upsert_session_chunks
from runtime_store import create_runtime_store
from llm_clients import check_llm_backend_ready
from services import (
    analyze_risks,
    answer_question,
    extract_json_fields,
    generate_summary,
    prepare_document,
)

logger = logging.getLogger(__name__)
store = create_runtime_store()

app = FastAPI(title="ТехСпек AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ── Schemas ────────────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    session_id: str
    question: str
    customer_bin: Optional[str] = ""
    language: str = "Русский"


class AnalyzeRequest(BaseModel):
    session_id: str
    customer_bin: Optional[str] = ""
    language: str = "Русский"


# ── Helpers ────────────────────────────────────────────────────────────────
def _validate_language(language: str) -> str:
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=422, detail="Поддерживаются только языки: Русский, Қазақша.")
    return language


def _validate_customer_bin(customer_bin: str, *, required: bool = False) -> str:
    value = (customer_bin or "").strip()
    if required and not value:
        raise HTTPException(status_code=422, detail="Требуется БИН из 12 цифр.")
    if value and (not value.isdigit() or len(value) != 12):
        raise HTTPException(status_code=422, detail="БИН должен содержать ровно 12 цифр.")
    return value


def _validate_upload(file: UploadFile, payload: bytes) -> str:
    filename = file.filename or "upload.pdf"
    is_pdf_name = filename.lower().endswith(".pdf")
    is_pdf_type = file.content_type in {"application/pdf", "application/x-pdf"}
    if not is_pdf_name and not is_pdf_type:
        raise HTTPException(status_code=415, detail="Поддерживаются только PDF-файлы.")
    if not payload:
        raise HTTPException(status_code=400, detail="Файл пустой.")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Файл слишком большой. Лимит: {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )
    return filename


def _get_client_id(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "anonymous"


def _authorize_request(request: Request) -> None:
    if not API_AUTH_TOKEN:
        return

    provided = request.headers.get("x-api-key", "").strip()
    auth_header = request.headers.get("authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        provided = auth_header[7:].strip() or provided

    if not provided or not secrets.compare_digest(provided, API_AUTH_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized.")


def _enforce_rate_limit(request: Request) -> None:
    if RATE_LIMIT_MAX_REQUESTS <= 0 or RATE_LIMIT_WINDOW_SECONDS <= 0:
        return

    client_id = _get_client_id(request)
    if store.is_rate_limited(client_id, RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS):
        raise HTTPException(status_code=429, detail="Слишком много запросов. Попробуйте позже.")


def _run_service(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.warning("Upstream dependency failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unhandled service error")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервиса.") from exc


def _safe_log_usage(customer_bin: str, language: str, filename: str, interface: str) -> None:
    try:
        log_usage(customer_bin, language, filename, interface=interface)
    except Exception:
        logger.exception("Usage logging failed")


def get_session(session_id: str) -> dict:
    try:
        return store.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Сессия не найдена. Загрузите PDF заново.")


def _check_embedding_backend_ready() -> str:
    try:
        import ollama

        ollama.list()
        return ""
    except Exception as exc:
        return str(exc)


def _record_request_metrics(request: Request, status_code: int, start: float) -> None:
    elapsed = time.perf_counter() - start
    metrics.record_request(request.method, request.url.path, status_code, elapsed)


def _index_session_vectors(session_id: str, chunks: list, index) -> str:
    if not is_qdrant_enabled():
        return "faiss"

    try:
        upsert_session_chunks(session_id, chunks, index)
    except QdrantError as exc:
        logger.warning("Qdrant indexing skipped; FAISS fallback will be used: %s", exc)
        return "faiss"

    return "qdrant"


@app.middleware("http")
async def protect_api(request: Request, call_next):
    start = time.perf_counter()

    if request.method == "OPTIONS" or request.url.path in {"/health", "/metrics"}:
        response = await call_next(request)
        _record_request_metrics(request, response.status_code, start)
        return response

    try:
        _authorize_request(request)
        _enforce_rate_limit(request)
    except HTTPException as exc:
        _record_request_metrics(request, exc.status_code, start)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    response = await call_next(request)
    _record_request_metrics(request, response.status_code, start)
    return response


# ── Endpoints ──────────────────────────────────────────────────────────────
@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    language: str = Form("Русский"),
):
    """Загружает PDF, строит индекс, возвращает session_id."""
    language = _validate_language(language)
    pdf_bytes = await file.read()
    filename = _validate_upload(file, pdf_bytes)

    try:
        chunks, index, preview, key_fields = _run_service(prepare_document, pdf_bytes, language)
    except HTTPException:
        raise

    session_id = uuid.uuid4().hex
    vector_backend = _index_session_vectors(session_id, chunks, index)
    store.save_session(session_id, {
        "chunks": chunks,
        "index": index,
        "filename": filename,
        "language": language,
        "preview": preview,
        "key_fields": key_fields,
        "vector_backend": vector_backend,
    })
    return {
        "session_id": session_id,
        "filename": filename,
        "chunk_count": len(chunks),
        "preview": preview[:500],
        "key_fields": key_fields,
        "vector_backend": vector_backend,
    }


@app.post("/summary")
def get_summary(req: AnalyzeRequest):
    language = _validate_language(req.language)
    customer_bin = _validate_customer_bin(req.customer_bin or "", required=True)
    s = get_session(req.session_id)
    _safe_log_usage(customer_bin, language, s["filename"], interface="react")
    result = _run_service(
        generate_summary,
        s["chunks"],
        s["index"],
        customer_bin,
        language,
        s.get("key_fields"),
        session_id=req.session_id,
    )
    return {"result": result}


@app.post("/json-fields")
def get_json_fields(req: AnalyzeRequest):
    language = _validate_language(req.language)
    customer_bin = _validate_customer_bin(req.customer_bin or "", required=True)
    s = get_session(req.session_id)
    _safe_log_usage(customer_bin, language, s["filename"], interface="react")
    result = _run_service(
        extract_json_fields,
        s["chunks"],
        s["index"],
        customer_bin,
        language,
        s.get("key_fields"),
        session_id=req.session_id,
    )
    return {"result": result}


@app.post("/risks")
def get_risks(req: AnalyzeRequest):
    language = _validate_language(req.language)
    s = get_session(req.session_id)
    customer_bin = _validate_customer_bin(req.customer_bin or "", required=False)
    _safe_log_usage(customer_bin, language, s["filename"], interface="react")
    result = _run_service(
        analyze_risks,
        s["chunks"],
        s["index"],
        language,
        s.get("key_fields"),
        req.session_id,
    )
    return {"result": result}


@app.post("/ask")
def ask_question(req: AskRequest):
    language = _validate_language(req.language)
    s = get_session(req.session_id)
    customer_bin = _validate_customer_bin(req.customer_bin or "", required=False)
    if not req.question.strip():
        raise HTTPException(status_code=422, detail="Вопрос не должен быть пустым.")
    _safe_log_usage(customer_bin, language, s["filename"], interface="react")
    answer, context = _run_service(
        answer_question,
        req.question.strip(),
        s["chunks"],
        s["index"],
        language,
        s.get("key_fields"),
        session_id=req.session_id,
    )
    return {"answer": answer, "context": context}


@app.get("/health")
def health():
    return {"status": "ok", "session_backend": store.backend_name}


@app.get("/metrics", response_class=PlainTextResponse)
def get_metrics():
    return metrics.render_prometheus()


@app.get("/ready")
def ready():
    embeddings_error = _check_embedding_backend_ready()
    llm_error = check_llm_backend_ready()
    qdrant_error = check_qdrant_ready()
    payload = {
        "status": "ok" if not embeddings_error and not llm_error and not qdrant_error else "degraded",
        "session_backend": store.backend_name,
        "auth_enabled": bool(API_AUTH_TOKEN),
        "llm_provider": LLM_PROVIDER,
        "vector_backend": VECTOR_BACKEND,
    }
    if is_qdrant_enabled():
        payload["qdrant"] = "ok" if not qdrant_error else qdrant_error

    if embeddings_error or llm_error or qdrant_error:
        payload["embeddings"] = "ok" if not embeddings_error else embeddings_error
        payload["llm"] = "ok" if not llm_error else llm_error
        raise HTTPException(status_code=503, detail=payload)

    payload["embeddings"] = "ok"
    payload["llm"] = "ok"
    return payload
