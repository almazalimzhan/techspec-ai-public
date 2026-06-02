from typing import List

import faiss

from config import WORD_RE
from embeddings import embed_texts


def _keyword_score(query: str, chunk: str) -> int:
    chunk_low = chunk.lower()
    tokens = [token for token in WORD_RE.findall(query.lower()) if len(token) >= 4]
    score = 0
    for token in tokens:
        if token in chunk_low:
            score += 2
    return score


def retrieve_context(question: str, chunks: List[str], index: faiss.IndexFlatL2, k: int) -> str:
    if not chunks:
        return ""

    dense_k = min(max(k * 3, k), len(chunks))
    q_vec = embed_texts([question])
    _, idxs = index.search(q_vec, k=dense_k)

    scored = {}
    for rank, idx in enumerate(idxs[0]):
        idx_int = int(idx)
        scored[idx_int] = max(scored.get(idx_int, 0), dense_k - rank)

    for idx, chunk in enumerate(chunks):
        kw = _keyword_score(question, chunk)
        if kw:
            scored[idx] = scored.get(idx, 0) + kw

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


def retrieve_multi(queries: List[str], chunks: List[str], index: faiss.IndexFlatL2, k_per_query: int = 5) -> str:
    seen = set()
    result = []
    for query in queries:
        ctx = retrieve_context(query, chunks, index, k=k_per_query)
        for part in ctx.split("\n\n---\n\n"):
            part = part.strip()
            if part and part not in seen:
                seen.add(part)
                result.append(part)
    return "\n\n---\n\n".join(result)
