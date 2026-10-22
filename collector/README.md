# Course Explorer collector

The collector reads only the public Course Explorer pages. It never accesses
Self-Service, student accounts, or registration endpoints.

For each configured course it makes two requests: the public XML course listing
for stable CRNs/section numbers, then the public HTML course page for current
availability. Raw responses are stored before parsing. The HTML page is necessary
because `sectionStatusCode=A` in XML is not the live seat-availability value.

## Local pilot

Install dependencies and run one small collection:

```bash
.venv/bin/python -m collector.collect \
  --term 2027-spring \
  --course CS:225 \
  --store json \
  --verbose
```

The command prints a run UUID, request count, section count, and runtime. Local
records go to ignored `data/live/` files and untouched responses go to ignored
`data/raw/<run-id>/`. JSON storage exists for development and demonstrations; the
scheduled pilot should use PostgreSQL.

## PostgreSQL pilot

Apply the schema once, then collect:

```bash
psql "$DATABASE_URL" -f database/schema.sql
.venv/bin/python -m collector.collect \
  --term 2027-spring \
  --course CS:225 \
  --course CS:233 \
  --store postgres \
  --verbose
```

`--store postgres` reads `DATABASE_URL` automatically. Credentials belong in the
environment or an uncommitted `.env`, never in source control.

## Safe rerun demonstration

Copy the `run_id` printed by a successful run and execute the identical command
with `--run-id UUID`. The retry keeps the original snapshot because the key is
`(run_id, term, crn)`. A later observation must omit `--run-id`, creating a new
UUID and preserving another snapshot for the same section.

Useful Postgres checks:

```sql
SELECT run_id, status, started_at, completed_at FROM collection_runs ORDER BY started_at;
SELECT run_id, count(*) FROM snapshots GROUP BY run_id ORDER BY run_id;
SELECT raw_status, status, count(*) FROM snapshots GROUP BY raw_status, status;
SELECT * FROM collection_failures ORDER BY occurred_at DESC;
```

## Behavior and boundaries

- Requests use an identifying user agent, a 15-second timeout, two bounded
  retries, and a one-second minimum interval by default.
- `Open`, `Open (Restricted)`, and `CrossListOpen...` normalize to `open`.
  `Closed`/`CrossListClosed...` normalize to `closed`. Any other or absent value
  becomes `unknown`.
- A failed request is logged; it never creates a made-up closed observation.
- Retrying a run keeps the first raw response and observation for each source URL
  and section. A new run ID represents a new observation time.
- The backend still reads demo JSON. Arnav owns scheduling and API integration.

See `FIELD_AUDIT.md` for the inspected source fields and known limitations.
