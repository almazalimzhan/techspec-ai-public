import types
import unittest
from unittest.mock import patch

import qdrant_store


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class FakeIndex:
    def __init__(self, vectors):
        self.vectors = vectors

    def reconstruct(self, idx):
        return self.vectors[idx]


class QdrantStoreTests(unittest.TestCase):
    def test_ensure_collection_creates_missing_collection(self):
        with patch.object(qdrant_store, "QDRANT_COLLECTION", "demo_chunks"):
            with patch.object(qdrant_store.requests, "request") as mock_request:
                mock_request.side_effect = [
                    FakeResponse(status_code=404),
                    FakeResponse(status_code=200),
                ]

                qdrant_store.ensure_collection(vector_size=3)

        create_call = mock_request.call_args_list[1]
        self.assertEqual(create_call.args[0], "PUT")
        self.assertIn("/collections/demo_chunks", create_call.args[1])
        self.assertEqual(create_call.kwargs["json"]["vectors"]["size"], 3)
        self.assertEqual(create_call.kwargs["json"]["vectors"]["distance"], "Cosine")

    def test_upsert_session_chunks_sends_vectors_and_payload(self):
        fake_index = FakeIndex(vectors=[[0.1, 0.2], [0.3, 0.4]])

        with patch.object(qdrant_store, "ensure_collection") as mock_ensure:
            with patch.object(qdrant_store, "_request", return_value=FakeResponse(status_code=200)) as mock_request:
                qdrant_store.upsert_session_chunks(
                    session_id="session-1",
                    chunks=["alpha", "beta"],
                    index=fake_index,
                )

        mock_ensure.assert_called_once_with(vector_size=2)
        payload = mock_request.call_args.kwargs["json"]
        self.assertEqual(len(payload["points"]), 2)
        self.assertEqual(payload["points"][0]["vector"], [0.1, 0.2])
        self.assertEqual(payload["points"][0]["payload"]["session_id"], "session-1")
        self.assertEqual(payload["points"][1]["payload"]["text"], "beta")

    def test_search_session_chunks_returns_chunk_hits(self):
        response = FakeResponse(
            status_code=200,
            payload={
                "result": [
                    {
                        "score": 0.91,
                        "payload": {
                            "chunk_index": 2,
                            "text": "matched chunk",
                        },
                    }
                ]
            },
        )

        fake_vectors = [types.SimpleNamespace(tolist=lambda: [0.5, 0.6])]
        with patch.object(qdrant_store, "embed_texts", return_value=fake_vectors):
            with patch.object(qdrant_store, "_request", return_value=response) as mock_request:
                hits = qdrant_store.search_session_chunks("query", "session-1", limit=3)

        payload = mock_request.call_args.kwargs["json"]
        self.assertEqual(payload["limit"], 3)
        self.assertEqual(payload["filter"]["must"][0]["match"]["value"], "session-1")
        self.assertEqual(hits, [(2, "matched chunk", 0.91)])


if __name__ == "__main__":
    unittest.main()
