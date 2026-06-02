from typing import List

import faiss
import numpy as np
import ollama

from config import EMBED_MODEL


def _safe_embed_text(text: str, max_chars: int = 3500) -> str:
    text = text.strip()
    return text[:max_chars] if len(text) > max_chars else text


def embed_texts(texts: List[str], model: str = EMBED_MODEL) -> np.ndarray:
    vecs = []
    for text in texts:
        text = _safe_embed_text(text)
        response = ollama.embeddings(model=model, prompt=text)
        vecs.append(response["embedding"])
    return np.array(vecs, dtype="float32")


def build_index(chunks: List[str]) -> faiss.IndexFlatL2:
    vecs = embed_texts(chunks, model=EMBED_MODEL)
    dim = vecs.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(vecs)
    return index
