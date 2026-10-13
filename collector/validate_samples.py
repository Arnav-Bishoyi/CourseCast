"""Offline format sanity check; does not scrape or write to a database."""
import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

def validate():
    data = Path(__file__).resolve().parents[1] / "data"
    sections = json.loads((data / "demo_sections.json").read_text())
    keys = {(s["term"], s["crn"]) for s in sections}
    runs = json.loads((data / "demo_runs.json").read_text())
    run_ids = {r["run_id"] for r in runs}
    assert all(r["is_demo"] and r["source"] == "synthetic_fixture" for r in runs)
    seen = set()
    snapshots = json.loads((data / "demo_snapshots.json").read_text())
    for row in snapshots:
        UUID(row["run_id"])
        assert row["run_id"] in run_ids
        key = (row["run_id"], row["term"], row["crn"])
        assert key not in seen, f"Duplicate row: {key}"
        seen.add(key)
        assert (row["term"], row["crn"]) in keys
        assert row["status"] in {"open", "closed", "unknown"}
        assert datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00")).utcoffset() is not None
        assert row["is_demo"] is True
    print(f"Validated {len(snapshots)} synthetic snapshots across {len(keys)} sections.")

if __name__ == "__main__":
    validate()
