# Collector handoff (Eli; scheduling with Arnav)

No real collector is implemented yet. Start with the public Course Explorer API
and inspect its actual XML before writing a parser. Never access Self-Service.

Input: a configurable term and pilot course list.
Output: metadata in `sections`, one `collection_runs` record per run, and snapshots.
Use `data/demo_snapshots.json` as a format example, not actual API responses.
Run the offline validator with `python -m collector.validate_samples`.

- Fetch politely: identifying user agent, about one request/second initially,
  timeouts and bounded retries. Record failures and unknown status explicitly.
- Reuse a run UUID for retries. Create a new UUID for later observations.
- Preserve raw source status alongside normalized status. No seat counts assumed.
- Do not turn an unobserved or failed fetch into `closed`.
- Keep demo fixtures separate from live data. Mark source and `is_demo` per run.
- Measure pilot runtime before expanding to every section or changing cadence.
- PostgreSQL schema is in `database/schema.sql`; no connection is required to run the demo app.

Arnav owns scheduling, freshness checks and API wiring. The backend currently
reads only offline JSON; replacing that with database queries is later work.
