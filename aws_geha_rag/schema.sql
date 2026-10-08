CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS geha_documents (
    id text PRIMARY KEY,
    title text NOT NULL,
    source text NOT NULL,
    relative_path text NOT NULL UNIQUE,
    category text NOT NULL,
    program text NOT NULL,
    plan_year integer,
    last_updated date,
    tags text[] NOT NULL DEFAULT '{}',
    validation jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS geha_chunks (
    id bigserial PRIMARY KEY,
    document_id text NOT NULL REFERENCES geha_documents(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,
    page_number integer NOT NULL,
    content text NOT NULL,
    embedding vector(1024) NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    content_len integer GENERATED ALWAYS AS (length(content)) STORED,
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS geha_documents_scope_idx
    ON geha_documents(category, program, plan_year);
CREATE INDEX IF NOT EXISTS geha_chunks_document_idx
    ON geha_chunks(document_id, page_number, chunk_index);
CREATE INDEX IF NOT EXISTS geha_chunks_tsv_idx ON geha_chunks USING gin(tsv);
CREATE INDEX IF NOT EXISTS geha_chunks_embedding_hnsw_idx
    ON geha_chunks USING hnsw (embedding vector_cosine_ops);

-- Okapi BM25 inverted index. Neon does not expose pg_search, so term
-- frequencies are materialized from each chunk's tsvector and maintained by
-- a trigger. This is the same retrieval design used by the legacy aws_rag.
ALTER TABLE geha_chunks
    ADD COLUMN IF NOT EXISTS content_len integer
    GENERATED ALWAYS AS (length(content)) STORED;

CREATE TABLE IF NOT EXISTS geha_terms (
    lexeme text NOT NULL,
    chunk_id bigint NOT NULL REFERENCES geha_chunks(id) ON DELETE CASCADE,
    tf integer NOT NULL,
    PRIMARY KEY (lexeme, chunk_id)
);
CREATE INDEX IF NOT EXISTS geha_terms_chunk_idx ON geha_terms(chunk_id);

CREATE OR REPLACE FUNCTION geha_terms_fill() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        DELETE FROM geha_terms WHERE chunk_id = NEW.id;
    END IF;
    INSERT INTO geha_terms (lexeme, chunk_id, tf)
    SELECT term.lexeme, NEW.id, coalesce(array_length(term.positions, 1), 1)
    FROM unnest(NEW.tsv) AS term
    ON CONFLICT (lexeme, chunk_id) DO UPDATE SET tf = EXCLUDED.tf;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS geha_terms_fill ON geha_chunks;
CREATE TRIGGER geha_terms_fill AFTER INSERT OR UPDATE OF content ON geha_chunks
    FOR EACH ROW EXECUTE FUNCTION geha_terms_fill();

-- Idempotent backfill for chunks inserted before this schema revision.
INSERT INTO geha_terms (lexeme, chunk_id, tf)
SELECT term.lexeme, chunk.id, coalesce(array_length(term.positions, 1), 1)
FROM geha_chunks AS chunk, unnest(chunk.tsv) AS term
ON CONFLICT (lexeme, chunk_id) DO UPDATE SET tf = EXCLUDED.tf;
