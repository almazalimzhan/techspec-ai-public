import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class FakeIndex:
    def __init__(self, payload: str):
        self.payload = payload


def fake_serialize_index(index):
    return index.payload.encode("utf-8")


def fake_deserialize_index(payload):
    return FakeIndex(bytes(payload).decode("utf-8"))


class RuntimeStoreTests(unittest.TestCase):
    def setUp(self):
        self.fake_faiss = types.SimpleNamespace(
            serialize_index=fake_serialize_index,
            deserialize_index=fake_deserialize_index,
        )
        self.fake_numpy = types.SimpleNamespace(frombuffer=lambda payload, dtype=None: payload)

    def test_sqlite_store_round_trip(self):
        from runtime_store import SqliteRuntimeStore

        with patch.dict("sys.modules", {"faiss": self.fake_faiss, "numpy": self.fake_numpy}):
            with tempfile.TemporaryDirectory() as temp_dir:
                store = SqliteRuntimeStore(Path(temp_dir) / "runtime.db", ttl_seconds=3600)
                store.save_session(
                    "session-1",
                    {
                        "chunks": ["alpha", "beta"],
                        "index": FakeIndex("payload-1"),
                        "filename": "doc.pdf",
                        "language": "Русский",
                        "preview": "alpha",
                        "key_fields": {"subject": "demo"},
                    },
                )

                loaded = store.get_session("session-1")

        self.assertEqual(loaded["filename"], "doc.pdf")
        self.assertEqual(loaded["chunks"], ["alpha", "beta"])
        self.assertEqual(loaded["key_fields"]["subject"], "demo")
        self.assertEqual(loaded["index"].payload, "payload-1")

    def test_rate_limit_bucket(self):
        from runtime_store import MemoryRuntimeStore

        store = MemoryRuntimeStore(ttl_seconds=60)
        self.assertFalse(store.is_rate_limited("127.0.0.1", max_requests=2, window_seconds=60))
        self.assertFalse(store.is_rate_limited("127.0.0.1", max_requests=2, window_seconds=60))
        self.assertTrue(store.is_rate_limited("127.0.0.1", max_requests=2, window_seconds=60))


if __name__ == "__main__":
    unittest.main()
