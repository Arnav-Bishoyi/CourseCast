-- PostgreSQL. Apply with: psql "$DATABASE_URL" -f database/schema.sql
-- Metadata only; no student identities or credentials belong in these tables.
BEGIN;
CREATE TABLE IF NOT EXISTS sections (
    term TEXT NOT NULL,
    crn TEXT NOT NULL,
    subject TEXT NOT NULL,
    course_number TEXT NOT NULL,
    section_number TEXT NOT NULL,
    instructor TEXT,
    meeting_summary TEXT,
    cross_list_group TEXT,
    PRIMARY KEY (term, crn)
);
CREATE TABLE IF NOT EXISTS collection_runs (
    run_id UUID PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    source TEXT NOT NULL,
    is_demo BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL CHECK (status IN ('running', 'complete', 'partial', 'failed'))
);
CREATE TABLE IF NOT EXISTS raw_responses (
    run_id UUID NOT NULL REFERENCES collection_runs(run_id),
    request_url TEXT NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL,
    status_code INTEGER NOT NULL,
    content_type TEXT,
    body BYTEA NOT NULL,
    sha256 TEXT NOT NULL,
    PRIMARY KEY (run_id, request_url)
);
CREATE TABLE IF NOT EXISTS collection_failures (
    run_id UUID NOT NULL REFERENCES collection_runs(run_id),
    request_url TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    PRIMARY KEY (run_id, request_url)
);
CREATE TABLE IF NOT EXISTS snapshots (
    run_id UUID NOT NULL REFERENCES collection_runs(run_id),
    term TEXT NOT NULL,
    crn TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    raw_status TEXT,
    status TEXT NOT NULL CHECK (status IN ('open', 'closed', 'unknown')),
    PRIMARY KEY (run_id, term, crn),
    FOREIGN KEY (term, crn) REFERENCES sections(term, crn)
);
CREATE INDEX IF NOT EXISTS snapshots_section_time ON snapshots(term, crn, observed_at);
COMMIT;
-- A retry reuses run_id; a later collection creates a new run_id.
-- ON CONFLICT DO NOTHING on (run_id, term, crn) makes retries idempotent.
-- Track source retrieval timestamps per section, not only the batch start time.
