import logging
from typing import Dict, List, Optional

import faiss

from config import WORD_RE
from embeddings import embed_texts
from qdrant_store import QdrantError, is_qdrant_enabled, search_session_chunks

logger = logging.getLogger(__name__)


def _keyword_score(query: str, chunk: str) -> int:
    chunk_low = chunk.lower()
    tokens = [token for token in WORD_RE.findall(query.lower()) if len(token) >= 4]
    score = 0
    for token in tokens:
        if token in chunk_low:
            score += 2
    return score


def _faiss_dense_scores(question: str, index: faiss.IndexFlatL2, dense_k: int) -> Dict[int, int]:
    q_vec = embed_texts([question])
    _, idxs = index.search(q_vec, k=dense_k)
    scored: Dict[int, int] = {}
    for rank, idx in enumerate(idxs[0]):
        idx_int = int(idx)
        scored[idx_int] = max(scored.get(idx_int, 0), dense_k - rank)
    return scored


def _qdrant_dense_scores(question: str, session_id: str, dense_k: int) -> Dict[int, int]:
    hits = search_session_chunks(question, session_id=session_id, limit=dense_k)
    scored: Dict[int, int] = {}
    for rank, (idx, _text, _score) in enumerate(hits):
        scored[idx] = max(scored.get(idx, 0), dense_k - rank)
    return scored


def _select_context_from_scores(scored: Dict[int, int], chunks: List[str], k: int) -> str:
    top_hits = sorted(scored.items(), key=lambda item: (-item[1], item[0]))[: min(k, len(chunks))]
    selected_idxs = set()
    for idx, _ in top_hits:
        selected_idxs.add(idx)
        if idx - 1 >= 0:
            selected_idxs.add(idx - 1)
        if idx + 1 < len(chunks):
            selected_idxs.add(idx + 1)

    ordered = sorted(selected_idxs)
    context_chunks = []
    seen = set()
    for idx in ordered:
        chunk = chunks[idx]
        if chunk in seen:
            continue
        seen.add(chunk)
        context_chunks.append(chunk)
        if len(context_chunks) >= min(k + 2, len(chunks)):
            break

    return "\n\n---\n\n".join(context_chunks)


def retrieve_context(
    question: str,
    chunks: List[str],
    index: faiss.IndexFlatL2,
    k: int,
    session_id: Optional[str] = None,
) -> str:
    if not chunks:
        return ""

    dense_k = min(max(k * 3, k), len(chunks))

    if session_id and is_qdrant_enabled():
        try:
            scored = _qdrant_dense_scores(question, session_id=session_id, dense_k=dense_k)
        except QdrantError as exc:
            logger.warning("Qdrant retrieval failed; falling back to FAISS: %s", exc)
            scored = _faiss_dense_scores(question, index, dense_k)
    else:
        scored = _faiss_dense_scores(question, index, dense_k)

    for idx, chunk in enumerate(chunks):
        kw = _keyword_score(question, chunk)
        if kw:
            scored[idx] = scored.get(idx, 0) + kw

    return _select_context_from_scores(scored, chunks, k)


def retrieve_multi(
    queries: List[str],
    chunks: List[str],
    index: faiss.IndexFlatL2,
    k_per_query: int = 5,
    session_id: Optional[str] = None,
) -> str:
    seen = set()
    result = []
    for query in queries:
        ctx = retrieve_context(query, chunks, index, k=k_per_query, session_id=session_id)
        for part in ctx.split("\n\n---\n\n"):
            part = part.strip()
            if part and part not in seen:
                seen.add(part)
                result.append(part)
    return "\n\n---\n\n".join(result)
