import logging
import uuid
from typing import Dict, List, Tuple

import requests

from config import (
    QDRANT_COLLECTION,
    QDRANT_TIMEOUT_SECONDS,
    QDRANT_URL,
    VECTOR_BACKEND,
)
from embeddings import embed_texts

logger = logging.getLogger(__name__)


class QdrantError(RuntimeError):
    pass


def is_qdrant_enabled() -> bool:
    return VECTOR_BACKEND == "qdrant"


def _request(method: str, path: str, **kwargs) -> requests.Response:
    url = f"{QDRANT_URL}{path}"
    try:
        return requests.request(method, url, timeout=QDRANT_TIMEOUT_SECONDS, **kwargs)
    except requests.RequestException as exc:
        raise QdrantError(f"Qdrant unavailable: {exc}") from exc


def check_qdrant_ready() -> str:
    if not is_qdrant_enabled():
        return ""

    try:
        response = _request("GET", "/collections")
    except QdrantError as exc:
        return str(exc)

    if response.status_code != 200:
        return f"Qdrant bad status: {response.status_code}"
    return ""


def _point_id(session_id: str, chunk_index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"techspec:{session_id}:{chunk_index}"))


def _vectors_from_faiss(index, count: int) -> List[List[float]]:
    vectors = []
    for idx in range(count):
        vector = index.reconstruct(idx)
        if hasattr(vector, "tolist"):
            vector = vector.tolist()
        vectors.append([float(value) for value in vector])
    return vectors


def ensure_collection(vector_size: int) -> None:
    response = _request("GET", f"/collections/{QDRANT_COLLECTION}")
    if response.status_code == 200:
        return
    if response.status_code != 404:
        raise QdrantError(f"Qdrant collection check failed: {response.status_code}, {response.text}")

    payload = {
        "vectors": {
            "size": vector_size,
            "distance": "Cosine",
        }
    }
    response = _request("PUT", f"/collections/{QDRANT_COLLECTION}", json=payload)
    if response.status_code not in {200, 201}:
        raise QdrantError(f"Qdrant collection create failed: {response.status_code}, {response.text}")


def upsert_session_chunks(session_id: str, chunks: List[str], index) -> None:
    if not chunks:
        return

    vectors = _vectors_from_faiss(index, len(chunks))
    if not vectors:
        return

    ensure_collection(vector_size=len(vectors[0]))

    points = []
    for chunk_index, (chunk, vector) in enumerate(zip(chunks, vectors)):
        points.append(
            {
                "id": _point_id(session_id, chunk_index),
                "vector": vector,
                "payload": {
                    "session_id": session_id,
                    "chunk_index": chunk_index,
                    "text": chunk,
                },
            }
        )

    payload = {"points": points}
    response = _request("PUT", f"/collections/{QDRANT_COLLECTION}/points?wait=true", json=payload)
    if response.status_code not in {200, 201}:
        raise QdrantError(f"Qdrant upsert failed: {response.status_code}, {response.text}")


def search_session_chunks(question: str, session_id: str, limit: int) -> List[Tuple[int, str, float]]:
    query_vector = embed_texts([question])[0]
    if hasattr(query_vector, "tolist"):
        query_vector = query_vector.tolist()

    payload: Dict = {
        "vector": [float(value) for value in query_vector],
        "limit": limit,
        "with_payload": True,
        "filter": {
            "must": [
                {
                    "key": "session_id",
                    "match": {"value": session_id},
                }
            ]
        },
    }

    response = _request("POST", f"/collections/{QDRANT_COLLECTION}/points/search", json=payload)
    if response.status_code != 200:
        raise QdrantError(f"Qdrant search failed: {response.status_code}, {response.text}")

    data = response.json()
    hits = []
    for item in data.get("result", []):
        payload = item.get("payload") or {}
        chunk_index = payload.get("chunk_index")
        text = payload.get("text")
        if chunk_index is None or not text:
            continue
        hits.append((int(chunk_index), str(text), float(item.get("score", 0.0))))

    return hits
