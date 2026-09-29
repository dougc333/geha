"""Hybrid search against the Weaviate mirror of rag_chunks (scripts/load_weaviate.py).

One Weaviate query does what the Postgres path does in three steps: BM25 over
`content`, vector search with the same Titan query embedding, and fusion.
`alpha` weights them (0 = keyword only, 1 = vector only); fusion is either
RANKED (reciprocal-rank style, like our RRF) or RELATIVE_SCORE (min-max
normalised scores, Weaviate's default).
"""

from __future__ import annotations

import atexit
import os

import weaviate
from langfuse import observe
from weaviate.classes.init import Auth
from weaviate.classes.query import Filter, HybridFusion, MetadataQuery

COLLECTION = "Chunk"
_client: weaviate.WeaviateClient | None = None


def enabled() -> bool:
    return bool(os.getenv("WEAVIATE_URL") and os.getenv("WEAVIATE_API_KEY"))


def _chunks():
    global _client
    if _client is None or not _client.is_connected():
        _client = weaviate.connect_to_weaviate_cloud(
            cluster_url=os.environ["WEAVIATE_URL"],
            auth_credentials=Auth.api_key(os.environ["WEAVIATE_API_KEY"]),
            skip_init_checks=True,  # saves a round trip on cold start
        )
        atexit.register(_client.close)
    return _client.collections.get(COLLECTION)


@observe(name="weaviate-hybrid", as_type="retriever", capture_output=False)
def hybrid(query: str, vector: list[float], *, alpha: float = 0.5, limit: int = 50,
           fusion: str = "relative_score", document_ids: list[str] | None = None) -> list[dict]:
    result = _chunks().query.hybrid(
        query=query,
        vector=vector,
        alpha=alpha,
        fusion_type=HybridFusion.RANKED if fusion == "ranked" else HybridFusion.RELATIVE_SCORE,
        limit=limit,
        filters=Filter.by_property("document_id").contains_any(document_ids) if document_ids else None,
        return_metadata=MetadataQuery(score=True, explain_score=True),
    )
    return [
        {
            "id": obj.properties["pg_id"],  # same ID as rag_chunks.id, so results line up
            "chunk_index": obj.properties["chunk_index"],
            "page": obj.properties["page"],
            "content": obj.properties["content"],
            "document_id": obj.properties["document_id"],
            "title": obj.properties["title"],
            "score": obj.metadata.score,
            "score_type": f"weaviate-{fusion}",
            "explain": obj.metadata.explain_score,
        }
        for obj in result.objects
    ]
