import json
import sqlite3
import tempfile
import time
from pathlib import Path
from threading import RLock
from typing import Dict

from config import SESSION_BACKEND, SESSION_DB_PATH, SESSION_TTL_SECONDS


def _import_faiss():
    import faiss

    return faiss


def _import_numpy():
    import numpy as np

    return np


def _serialize_index(index) -> bytes:
    faiss = _import_faiss()
    try:
        raw = faiss.serialize_index(index)
    except (AttributeError, ImportError):
        with tempfile.NamedTemporaryFile(suffix=".faiss") as tmp:
            faiss.write_index(index, tmp.name)
            tmp.seek(0)
            return tmp.read()

    if hasattr(raw, "tobytes"):
        return raw.tobytes()
    return bytes(raw)


def _deserialize_index(payload: bytes):
    faiss = _import_faiss()
    try:
        np = _import_numpy()
        return faiss.deserialize_index(np.frombuffer(payload, dtype="uint8"))
    except (AttributeError, ImportError):
        with tempfile.NamedTemporaryFile(suffix=".faiss") as tmp:
            tmp.write(payload)
            tmp.flush()
            return faiss.read_index(tmp.name)


class MemoryRuntimeStore:
    backend_name = "memory"

    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = max(0, ttl_seconds)
        self._sessions: Dict[str, dict] = {}
        self._request_buckets: Dict[tuple, int] = {}
        self._lock = RLock()

    def _expires_at(self) -> int:
        if self.ttl_seconds <= 0:
            return 0
        return int(time.time()) + self.ttl_seconds

    def _cleanup_expired_sessions(self) -> None:
        if self.ttl_seconds <= 0:
            return
        now = int(time.time())
        expired_ids = [
            session_id
            for session_id, payload in self._sessions.items()
            if payload.get("_expires_at", 0) and payload["_expires_at"] <= now
        ]
        for session_id in expired_ids:
            self._sessions.pop(session_id, None)

    def save_session(self, session_id: str, data: dict) -> None:
        with self._lock:
            self._cleanup_expired_sessions()
            payload = dict(data)
            payload["_expires_at"] = self._expires_at()
            self._sessions[session_id] = payload

    def get_session(self, session_id: str) -> dict:
        with self._lock:
            self._cleanup_expired_sessions()
            payload = self._sessions.get(session_id)
            if not payload:
                raise KeyError(session_id)
            result = dict(payload)
            result.pop("_expires_at", None)
            return result

    def is_rate_limited(self, client_id: str, max_requests: int, window_seconds: int) -> bool:
        if max_requests <= 0 or window_seconds <= 0:
            return False

        now = int(time.time())
        bucket_start = now - (now % window_seconds)
        key = (client_id, bucket_start)

        with self._lock:
            stale_keys = [
                item
                for item in self._request_buckets
                if item[1] < bucket_start - window_seconds
            ]
            for stale_key in stale_keys:
                self._request_buckets.pop(stale_key, None)

            current = self._request_buckets.get(key, 0)
            if current >= max_requests:
                return True

            self._request_buckets[key] = current + 1
            return False


class SqliteRuntimeStore:
    backend_name = "sqlite"

    def __init__(self, db_path: Path, ttl_seconds: int):
        self.db_path = Path(db_path)
        self.ttl_seconds = max(0, ttl_seconds)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    language TEXT NOT NULL,
                    preview TEXT NOT NULL,
                    chunks_json TEXT NOT NULL,
                    key_fields_json TEXT NOT NULL,
                    index_blob BLOB NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rate_limits (
                    client_id TEXT NOT NULL,
                    bucket_start INTEGER NOT NULL,
                    request_count INTEGER NOT NULL,
                    PRIMARY KEY (client_id, bucket_start)
                );
                """
            )

    def _expires_at(self) -> int:
        if self.ttl_seconds <= 0:
            return 0
        return int(time.time()) + self.ttl_seconds

    def cleanup_expired_sessions(self) -> None:
        if self.ttl_seconds <= 0:
            return
        now = int(time.time())
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at > 0 AND expires_at <= ?", (now,))

    def save_session(self, session_id: str, data: dict) -> None:
        now = int(time.time())
        expires_at = self._expires_at()
        payload = (
            session_id,
            now,
            expires_at,
            data.get("filename", "") or "upload.pdf",
            data.get("language", ""),
            data.get("preview", ""),
            json.dumps(data.get("chunks", []), ensure_ascii=False),
            json.dumps(data.get("key_fields", {}), ensure_ascii=False),
            sqlite3.Binary(_serialize_index(data["index"])),
        )

        self.cleanup_expired_sessions()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions (
                    session_id,
                    created_at,
                    expires_at,
                    filename,
                    language,
                    preview,
                    chunks_json,
                    key_fields_json,
                    index_blob
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )

    def get_session(self, session_id: str) -> dict:
        self.cleanup_expired_sessions()
        now = int(time.time())
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT filename, language, preview, chunks_json, key_fields_json, index_blob
                FROM sessions
                WHERE session_id = ?
                  AND (expires_at = 0 OR expires_at > ?)
                """,
                (session_id, now),
            ).fetchone()

        if row is None:
            raise KeyError(session_id)

        return {
            "filename": row["filename"],
            "language": row["language"],
            "preview": row["preview"],
            "chunks": json.loads(row["chunks_json"]),
            "key_fields": json.loads(row["key_fields_json"]),
            "index": _deserialize_index(bytes(row["index_blob"])),
        }

    def is_rate_limited(self, client_id: str, max_requests: int, window_seconds: int) -> bool:
        if max_requests <= 0 or window_seconds <= 0:
            return False

        now = int(time.time())
        bucket_start = now - (now % window_seconds)

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "DELETE FROM rate_limits WHERE bucket_start < ?",
                (bucket_start - (window_seconds * 2),),
            )
            row = conn.execute(
                """
                SELECT request_count
                FROM rate_limits
                WHERE client_id = ? AND bucket_start = ?
                """,
                (client_id, bucket_start),
            ).fetchone()

            current = row["request_count"] if row else 0
            if current >= max_requests:
                conn.execute("COMMIT")
                return True

            conn.execute(
                """
                INSERT INTO rate_limits (client_id, bucket_start, request_count)
                VALUES (?, ?, 1)
                ON CONFLICT(client_id, bucket_start)
                DO UPDATE SET request_count = request_count + 1
                """,
                (client_id, bucket_start),
            )
            conn.execute("COMMIT")
            return False


def create_runtime_store():
    if SESSION_BACKEND == "memory":
        return MemoryRuntimeStore(ttl_seconds=SESSION_TTL_SECONDS)
    return SqliteRuntimeStore(db_path=SESSION_DB_PATH, ttl_seconds=SESSION_TTL_SECONDS)
