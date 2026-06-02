import csv
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterator

from config import USAGE_LOG_FILE

LOG_FILE = USAGE_LOG_FILE
LOCK_FILE = LOG_FILE.with_suffix(LOG_FILE.suffix + ".lock")
LOG_COLUMNS = [
    "timestamp",
    "customer_bin",
    "language",
    "pdf_filename",
    "interface",
    "tg_username",
]

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX fallback
    msvcrt = None


class _FileLock:
    def __init__(self, path: Path):
        self.path = path
        self.file = None

    def __enter__(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = open(self.path, mode="a+", encoding="utf-8")
        if fcntl is not None:
            fcntl.flock(self.file.fileno(), fcntl.LOCK_EX)
        elif msvcrt is not None:
            msvcrt.locking(self.file.fileno(), msvcrt.LK_LOCK, 1)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.file is None:
            return
        if fcntl is not None:
            fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        elif msvcrt is not None:
            self.file.seek(0)
            msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        self.file.close()


def _normalize_existing_log() -> None:
    if not LOG_FILE.exists():
        return

    with open(LOG_FILE, mode="r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
        current_columns = rows[0].keys() if rows else []

    if list(current_columns) == LOG_COLUMNS:
        return

    normalized_rows = []
    for row in rows:
        normalized_rows.append({
            "timestamp": row.get("timestamp", ""),
            "customer_bin": row.get("customer_bin", ""),
            "language": row.get("language", ""),
            "pdf_filename": row.get("pdf_filename", ""),
            "interface": row.get("interface", "streamlit"),
            "tg_username": row.get("tg_username", ""),
        })

    with NamedTemporaryFile(
        mode="w",
        newline="",
        encoding="utf-8-sig",
        delete=False,
        dir=LOG_FILE.parent or Path("."),
    ) as temp_file:
        writer = csv.DictWriter(temp_file, fieldnames=LOG_COLUMNS)
        writer.writeheader()
        writer.writerows(normalized_rows)
        temp_name = temp_file.name

    os.replace(temp_name, LOG_FILE)


def log_usage(
    customer_bin: str,
    language: str,
    pdf_filename: str = "",
    interface: str = "streamlit",
    tg_username: str = "",
) -> None:
    with _FileLock(LOCK_FILE):
        _normalize_existing_log()
        file_exists = LOG_FILE.exists()

        with open(LOG_FILE, mode="a", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)

            if not file_exists:
                writer.writerow(LOG_COLUMNS)

            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                customer_bin,
                language,
                pdf_filename,
                interface,
                tg_username,
            ])
