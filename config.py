import os
import re
from pathlib import Path
from typing import Iterable, List

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_list(name: str, default: Iterable[str]) -> List[str]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]


LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:8b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").strip().lower() or "ollama"

LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "").strip()
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "").strip()
ALEM_MODEL = os.getenv("ALEM_MODEL", "astanahub/alemllm")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
VERIFY_TLS = _env_bool("VERIFY_TLS", True)

SUPPORTED_LANGUAGES = ("Русский", "Қазақша")
CORS_ALLOW_ORIGINS = _env_list(
    "CORS_ALLOW_ORIGINS",
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ],
)

SESSION_BACKEND = os.getenv("SESSION_BACKEND", "sqlite").strip().lower() or "sqlite"
SESSION_DB_PATH = Path(os.getenv("SESSION_DB_PATH", ".runtime/techspec.db"))
SESSION_TTL_SECONDS = _env_int("SESSION_TTL_SECONDS", 3600)

MAX_UPLOAD_BYTES = _env_int("MAX_UPLOAD_BYTES", 25 * 1024 * 1024)
API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "")
RATE_LIMIT_WINDOW_SECONDS = _env_int("RATE_LIMIT_WINDOW_SECONDS", 60)
RATE_LIMIT_MAX_REQUESTS = _env_int("RATE_LIMIT_MAX_REQUESTS", 30)

USAGE_LOG_FILE = Path(os.getenv("USAGE_LOG_FILE", "usage_logs.csv"))

QA_TOP_K = 6
STRUCT_TOP_K = 12
RISK_TOP_K = 6
LANG_PAGE_FALLBACK_MIN_CHARS = 500
CHUNK_OVERLAP_CHARS = 220

KZ_CHARS = set("әғқңөұүһіӘҒҚҢӨҰҮҺІ")
LATIN_RE = re.compile(r"[A-Za-z]")
WORD_RE = re.compile(r"\w+", re.UNICODE)
