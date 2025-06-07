from types import SimpleNamespace
from dataclasses import dataclass
import code_index_engine.qdrant_store as qs

@dataclass
class DummyPoint:
    id: str
    vector: list[float]
    payload: dict[str, str]

@dataclass
class DummyIds:
    points: list[str]

class DummyClient:
    def __init__(self, *a, **k):
        self.collections = {}

    def collection_exists(self, name):
        return name in self.collections

    def create_collection(self, collection_name, vectors_config):
        self.collections[collection_name] = {}

    def upsert(self, collection_name, points):
        col = self.collections.setdefault(collection_name, {})
        for p in points:
            col[p.id] = (p.vector, p.payload)

    def delete(self, collection_name, points_selector):
        col = self.collections.get(collection_name, {})
        for pid in points_selector.points:
            col.pop(pid, None)

    def search(self, collection_name, query_vector, limit):
        import numpy as np
        col = self.collections.get(collection_name, {})
        results = []
        for vec, payload in col.values():
            score = float(np.dot(query_vector, vec) / (np.linalg.norm(query_vector)*np.linalg.norm(vec)+1e-6))
            results.append(SimpleNamespace(payload=payload, score=score))
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]


def test_qdrant_store_roundtrip(monkeypatch):
    monkeypatch.setattr(qs, "QdrantClient", DummyClient)
    monkeypatch.setattr(qs, "PointStruct", DummyPoint)
    monkeypatch.setattr(qs, "PointIdsList", DummyIds)

    store = qs.QdrantStore("http://local")
    store.upsert("1", [0.0, 0.1], {"path": "a.py"})
    hits = store.search([0.0, 0.1])
    assert hits[0]["path"] == "a.py"
    store.delete("1")
    assert store.search([0.0, 0.1]) == []
