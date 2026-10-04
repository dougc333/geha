CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rag_documents (
    id text PRIMARY KEY,
    title text NOT NULL,
    source text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rag_chunks (
    id bigserial PRIMARY KEY,
    document_id text NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,
    page_number integer,
    content text NOT NULL,
    embedding vector(1024) NOT NULL,
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS rag_chunks_document_idx
    ON rag_chunks (document_id, chunk_index);

CREATE INDEX IF NOT EXISTS rag_chunks_embedding_hnsw_idx
    ON rag_chunks USING hnsw (embedding vector_cosine_ops);

-- Paper metadata, mostly from the arXiv API (NULL for PDFs without it). Safe
-- to re-run on an existing database.
ALTER TABLE rag_documents
    ADD COLUMN IF NOT EXISTS arxiv_id text,
    ADD COLUMN IF NOT EXISTS authors text[],
    ADD COLUMN IF NOT EXISTS published date,
    ADD COLUMN IF NOT EXISTS updated date,
    ADD COLUMN IF NOT EXISTS abstract text,
    ADD COLUMN IF NOT EXISTS primary_category text,
    ADD COLUMN IF NOT EXISTS categories text[],
    ADD COLUMN IF NOT EXISTS comment text,
    ADD COLUMN IF NOT EXISTS journal_ref text,
    ADD COLUMN IF NOT EXISTS doi text;

-- Keyword search for the chatbot, which searches every paper: Postgres full-text
-- search instead of loading all chunks into Python for BM25. Generated, so the
-- embedder doesn't need to change; existing rows are filled when it's added.
ALTER TABLE rag_chunks
    ADD COLUMN IF NOT EXISTS tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

CREATE INDEX IF NOT EXISTS rag_chunks_tsv_idx ON rag_chunks USING gin (tsv);

-- Figure chunks (local_ingest/describe_figures.py): S3 key of the figure's PNG in
-- the chunks bucket, e.g. figures/<document_id>/p003_f01.png. NULL for text and
-- table chunks. The query API turns it into a short-lived presigned URL.
ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS image text;

-- BM25 support (Neon doesn't allow the pg_search extension). rag_terms is an
-- inverted index: one row per (word, chunk) with the word's count in that chunk,
-- filled from the tsvector by a trigger, so the embedder needs no changes and
-- deleting a paper's chunks cascades. chat.bm25_search reads it with indexed
-- lookups instead of unpacking every candidate chunk's tsvector per query.
ALTER TABLE rag_chunks
    ADD COLUMN IF NOT EXISTS content_len integer GENERATED ALWAYS AS (length(content)) STORED;

CREATE TABLE IF NOT EXISTS rag_terms (
    lexeme text NOT NULL,
    chunk_id bigint NOT NULL REFERENCES rag_chunks(id) ON DELETE CASCADE,
    tf integer NOT NULL,
    PRIMARY KEY (lexeme, chunk_id)
);
CREATE INDEX IF NOT EXISTS rag_terms_chunk_idx ON rag_terms (chunk_id);

CREATE OR REPLACE FUNCTION rag_terms_fill() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO rag_terms (lexeme, chunk_id, tf)
    SELECT u.lexeme, NEW.id, coalesce(array_length(u.positions, 1), 1)
    FROM unnest(NEW.tsv) AS u
    ON CONFLICT DO NOTHING;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS rag_terms_fill ON rag_chunks;
CREATE TRIGGER rag_terms_fill AFTER INSERT ON rag_chunks
    FOR EACH ROW EXECUTE FUNCTION rag_terms_fill();

-- Backfill chunks that existed before the trigger (no-op afterwards).
INSERT INTO rag_terms (lexeme, chunk_id, tf)
SELECT u.lexeme, c.id, coalesce(array_length(u.positions, 1), 1)
FROM rag_chunks c, unnest(c.tsv) AS u
ON CONFLICT DO NOTHING;

-- Guided member signup is transactional application data, kept logically
-- separate from the retrieval corpus. Langfuse receives only redacted telemetry;
-- these tables are the authoritative, resumable signup record.
CREATE SCHEMA IF NOT EXISTS signup;

CREATE TABLE IF NOT EXISTS signup.applications (
    id uuid PRIMARY KEY,
    member_ref text NOT NULL,
    product text NOT NULL CHECK (product IN ('dental')),
    coverage_year integer NOT NULL CHECK (coverage_year BETWEEN 2026 AND 2100),
    stage text NOT NULL CHECK (stage IN (
        'eligibility', 'household', 'plan_selection', 'contact',
        'review', 'completed', 'handoff'
    )),
    status text NOT NULL CHECK (status IN ('active', 'completed', 'handoff')),
    slots jsonb NOT NULL DEFAULT '{}'::jsonb,
    version integer NOT NULL DEFAULT 0 CHECK (version >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS signup_applications_member_idx
    ON signup.applications (member_ref, updated_at DESC);

CREATE TABLE IF NOT EXISTS signup.messages (
    id bigserial PRIMARY KEY,
    application_id uuid NOT NULL REFERENCES signup.applications(id) ON DELETE CASCADE,
    client_message_id uuid NOT NULL,
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (application_id, client_message_id, role)
);
CREATE INDEX IF NOT EXISTS signup_messages_application_idx
    ON signup.messages (application_id, created_at);

CREATE TABLE IF NOT EXISTS signup.events (
    id bigserial PRIMARY KEY,
    application_id uuid NOT NULL REFERENCES signup.applications(id) ON DELETE CASCADE,
    event_type text NOT NULL,
    from_version integer NOT NULL,
    to_version integer NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS signup_events_application_idx
    ON signup.events (application_id, id);

-- A coverage-year/plan release explicitly selects the RAG documents that are
-- allowed to answer signup questions. Use plan_code='all' for shared brochures.
CREATE TABLE IF NOT EXISTS signup.plan_versions (
    product text NOT NULL,
    coverage_year integer NOT NULL,
    plan_code text NOT NULL CHECK (plan_code IN ('all', 'high', 'standard')),
    document_ids text[] NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (product, coverage_year, plan_code)
);
