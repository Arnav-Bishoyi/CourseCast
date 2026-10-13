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
-- Upsert on (run_id, term, crn) prevents duplicates without deleting history.
-- Track source retrieval timestamps per section, not only the batch start time.
