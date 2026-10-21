-- Tables for the RAG teaching lab. They live in their own schema because the
-- same Neon database holds the AWS stack's tables in `public` (Titan 1024-d
-- vectors); these use OpenAI text-embedding-3-small (1536-d). Safe to re-run.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS teaching;

CREATE TABLE IF NOT EXISTS teaching.rag_documents (
    id text PRIMARY KEY,
    title text NOT NULL,
    source text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS teaching.rag_chunks (
    id bigserial PRIMARY KEY,
    document_id text NOT NULL REFERENCES teaching.rag_documents(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,
    page_number integer,
    content text NOT NULL,
    embedding vector(1536) NOT NULL,
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS rag_chunks_document_idx
    ON teaching.rag_chunks (document_id, chunk_index);

CREATE INDEX IF NOT EXISTS rag_chunks_embedding_hnsw_idx
    ON teaching.rag_chunks USING hnsw (embedding vector_cosine_ops);
