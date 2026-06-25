from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
import uuid

from app.core.config import settings

_client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)
VECTOR_SIZE = 384  # all-MiniLM-L6-v2


def ensure_collection():
    existing = [c.name for c in _client.get_collections().collections]
    if settings.QDRANT_COLLECTION not in existing:
        _client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def delete_by_filename(filename: str, project: str):
    """Remove all existing chunks for a file before re-indexing."""
    ensure_collection()
    _client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=Filter(
            must=[
                FieldCondition(key="filename", match=MatchValue(value=filename)),
                FieldCondition(key="project", match=MatchValue(value=project)),
            ]
        ),
    )


def store_chunks(chunks: List[Dict[str, Any]], embeddings: List[List[float]], metadata: Dict[str, Any]):
    ensure_collection()
    points = []
    for chunk, embedding in zip(chunks, embeddings):
        payload = {
            "chunk_id": chunk["chunk_id"],
            "text": chunk["text"],
            "filename": chunk["filename"],
            "doc_type": metadata["doc_type"],
            "project": metadata["project"],
            "doc_id": metadata["doc_id"],
        }
        points.append(PointStruct(id=str(uuid.uuid4()), vector=embedding, payload=payload))

    _client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)


def search(
    query_vector: List[float],
    project: str,
    doc_types: Optional[List[str]] = None,
    top_k: int = 6,
) -> List[Dict[str, Any]]:
    ensure_collection()

    must_conditions = [FieldCondition(key="project", match=MatchValue(value=project))]
    if doc_types:
        must_conditions.append(FieldCondition(key="doc_type", match=MatchValue(value=doc_types[0])))

    results = _client.search(
        collection_name=settings.QDRANT_COLLECTION,
        query_vector=query_vector,
        query_filter=Filter(must=must_conditions),
        limit=top_k,
        with_payload=True,
    )

    return [
        {
            "text": r.payload["text"],
            "filename": r.payload["filename"],
            "doc_type": r.payload["doc_type"],
            "score": r.score,
        }
        for r in results
    ]
