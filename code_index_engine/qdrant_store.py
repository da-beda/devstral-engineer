from __future__ import annotations

from typing import List, Dict, Optional

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import (
        Distance,
        VectorParams,
        PointStruct,
        PointIdsList,
    )
except Exception:  # pragma: no cover - optional dependency
    QdrantClient = None  # type: ignore

    class Distance:  # type: ignore
        COSINE = "cosine"

    class VectorParams:  # type: ignore
        def __init__(self, size: int, distance: Distance) -> None:
            self.size = size
            self.distance = distance

    class PointStruct:  # type: ignore
        def __init__(self, id: str, vector: List[float], payload: Dict[str, str]) -> None:
            self.id = id
            self.vector = vector
            self.payload = payload

    class PointIdsList:  # type: ignore
        def __init__(self, points: List[str]) -> None:
            self.points = points


class QdrantStore:
    """Simple wrapper around Qdrant for storing code embeddings."""

    def __init__(self, url: str, api_key: Optional[str] = None, collection: str = "code", dim: int = 32) -> None:
        if QdrantClient is None:  # pragma: no cover - runtime guard
            raise RuntimeError("qdrant-client is not installed")
        self.client = QdrantClient(url=url, api_key=api_key)
        self.collection = collection
        self.dim = dim
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
            )

    def upsert(self, doc_id: str, embedding: List[float], payload: Dict[str, str]) -> None:
        self.client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=doc_id, vector=embedding, payload=payload)],
        )

    def delete(self, doc_id: str) -> None:
        self.client.delete(
            collection_name=self.collection,
            points_selector=PointIdsList(points=[doc_id]),
        )

    def search(self, embedding: List[float], limit: int = 5) -> List[Dict[str, str]]:
        hits = self.client.search(
            collection_name=self.collection,
            query_vector=embedding,
            limit=limit,
        )
        return [
            {"path": hit.payload.get("path", ""), "score": hit.score}
            for hit in hits
        ]
