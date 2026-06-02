import re
from typing import List

import fitz

from config import CHUNK_OVERLAP_CHARS, KZ_CHARS, LANG_PAGE_FALLBACK_MIN_CHARS


def extract_pages_by_language(pdf_bytes: bytes, target_language: str, kz_ratio_threshold: float = 0.02) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    selected_pages = []
    all_pages = []

    for page in doc:
        text = page.get_text()
        if text.strip():
            all_pages.append(text)
        letters = [ch for ch in text if ch.isalpha()]
        if not letters:
            continue

        kz_count = sum(1 for ch in letters if ch in KZ_CHARS)
        ratio = kz_count / max(1, len(letters))

        if target_language == "ru":
            if ratio <= kz_ratio_threshold:
                selected_pages.append(text)
        else:
            if ratio > kz_ratio_threshold:
                selected_pages.append(text)

    selected_text = clean_text("\n\n".join(selected_pages))
    if len(selected_text) >= LANG_PAGE_FALLBACK_MIN_CHARS:
        return selected_text

    return clean_text("\n\n".join(all_pages))


def clean_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _with_overlap(previous_chunk: str, next_text: str, overlap_chars: int = CHUNK_OVERLAP_CHARS) -> str:
    previous_chunk = previous_chunk.strip()
    if not previous_chunk:
        return next_text
    overlap = previous_chunk[-overlap_chars:].strip()
    if not overlap:
        return next_text
    return f"{overlap}\n{next_text}".strip()


def chunk_text(text: str, max_chars: int = 1500) -> List[str]:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks = []
    cur = ""

    for p in paragraphs:
        if len(p) > max_chars:
            for i in range(0, len(p), max_chars):
                part = p[i:i + max_chars].strip()
                if part:
                    if cur.strip():
                        chunks.append(cur.strip())
                        cur = ""
                    if chunks:
                        part = _with_overlap(chunks[-1], part)
                    chunks.append(part)
            continue

        if len(cur) + len(p) + 1 <= max_chars:
            cur += p + "\n"
        else:
            if cur.strip():
                chunks.append(cur.strip())
            cur = _with_overlap(chunks[-1], p) + "\n" if chunks else p + "\n"

    if cur.strip():
        chunks.append(cur.strip())

    return [c for c in chunks if len(c) >= 50]
