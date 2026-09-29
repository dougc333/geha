#!/usr/bin/env python3
"""Copy every chunk (text, metadata and its existing Titan vector) from Neon
into a Weaviate collection, so both stores can be compared on identical data.

    python scripts/load_weaviate.py [--recreate]

No re-embedding: vectors are read from rag_chunks.embedding and handed to
Weaviate as self-provided vectors (no Weaviate vectorizer module). Object IDs
are derived from rag_chunks.id, so re-running updates rather than duplicates,
and objects whose chunk no longer exists in Neon are deleted.
Connection details come from SSM: /rag-demo/database-url,
/rag-demo/weaviate-url, /rag-demo/weaviate-api-key.
"""

from __future__ import annotations

import argparse
import time

import boto3
import psycopg
import weaviate
from pgvector.psycopg import register_vector
from weaviate.classes.config import Configure, DataType, Property, Tokenization, VectorDistances
from weaviate.classes.init import Auth
from weaviate.classes.query import Filter
from weaviate.util import generate_uuid5

COLLECTION = "Chunk"


def ssm(name: str, region: str) -> str:
    return boto3.client("ssm", region_name=region).get_parameter(
        Name=name, WithDecryption=True)["Parameter"]["Value"]


def create(client: weaviate.WeaviateClient) -> None:
    client.collections.create(
        COLLECTION,
        description="Paper chunks mirrored from Neon rag_chunks (Titan v2 vectors)",
        # Weaviate Cloud sandboxes only allow the HFresh index (posting lists,
        # SPFresh-style), not HNSW; pgvector uses HNSW, so the ANN algorithms differ.
        vector_config=Configure.Vectors.self_provided(
            vector_index_config=Configure.VectorIndex.hfresh(distance_metric=VectorDistances.COSINE),
        ),
        properties=[
            Property(name="content", data_type=DataType.TEXT),  # BM25-indexed, English word tokens
            Property(name="title", data_type=DataType.TEXT),
            Property(name="document_id", data_type=DataType.TEXT, tokenization=Tokenization.FIELD),
            Property(name="page", data_type=DataType.INT),
            Property(name="chunk_index", data_type=DataType.INT),
            Property(name="pg_id", data_type=DataType.INT),  # rag_chunks.id, to compare with Postgres
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--recreate", action="store_true", help="drop and rebuild the collection")
    parser.add_argument("--region", default="us-west-2")
    args = parser.parse_args()

    started = time.perf_counter()
    with psycopg.connect(ssm("/rag-demo/database-url", args.region)) as connection:
        register_vector(connection)
        rows = connection.execute(
            """SELECT c.id, c.document_id, c.chunk_index, c.page_number, c.content, c.embedding, d.title
               FROM rag_chunks c JOIN rag_documents d ON d.id = c.document_id ORDER BY c.id"""
        ).fetchall()
    print(f"read {len(rows)} chunks from Neon in {time.perf_counter() - started:.1f}s", flush=True)

    with weaviate.connect_to_weaviate_cloud(
        cluster_url=ssm("/rag-demo/weaviate-url", args.region),
        auth_credentials=Auth.api_key(ssm("/rag-demo/weaviate-api-key", args.region)),
    ) as client:
        if args.recreate and client.collections.exists(COLLECTION):
            client.collections.delete(COLLECTION)
        if not client.collections.exists(COLLECTION):
            create(client)
        chunks = client.collections.get(COLLECTION)

        step = time.perf_counter()
        with chunks.batch.fixed_size(batch_size=200) as batch:
            for pg_id, document_id, chunk_index, page, content, embedding, title in rows:
                batch.add_object(
                    uuid=generate_uuid5(pg_id),
                    properties={"content": content, "title": title, "document_id": document_id,
                                "page": page, "chunk_index": chunk_index, "pg_id": pg_id},
                    vector=embedding.to_list(),  # pgvector Vector -> list[float]
                )
        failed = chunks.batch.failed_objects

        # Remove objects whose chunk is gone from Neon (papers re-embedded since the
        # last copy get new rag_chunks ids), so both engines search the same set.
        current = {generate_uuid5(row[0]) for row in rows}
        stale = [str(obj.uuid) for obj in chunks.iterator(return_properties=[]) if str(obj.uuid) not in current]
        for start in range(0, len(stale), 500):
            chunks.data.delete_many(where=Filter.by_id().contains_any(stale[start:start + 500]))
        print(f"removed {len(stale)} stale objects")
        total = chunks.aggregate.over_all(total_count=True).total_count
        print(f"wrote {len(rows) - len(failed)} objects in {time.perf_counter() - step:.1f}s; "
              f"failed {len(failed)}; collection now holds {total}")
        for failure in failed[:5]:
            print("  failure:", failure.message)


if __name__ == "__main__":
    main()
