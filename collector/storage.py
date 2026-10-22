"""Persistence backends for collection runs and observations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, Sequence

from collector.models import RawResponse, Section, Snapshot


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class Storage(Protocol):
    def start_run(self, run_id: str, started_at: datetime) -> None: ...

    def save_raw_response(self, response: RawResponse) -> None: ...

    def save_observations(
        self, sections: Sequence[Section], snapshots: Sequence[Snapshot]
    ) -> None: ...

    def record_failure(
        self, run_id: str, request_url: str, error_type: str, error_message: str
    ) -> None: ...

    def finish_run(self, run_id: str, status: str, completed_at: datetime) -> None: ...

    def close(self) -> None: ...


class JsonStorage:
    """Small local store for demos; PostgreSQL remains the scheduled-run target."""

    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.directory / f"{name}.json"

    def _load(self, name: str) -> list[dict]:
        path = self._path(name)
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, name: str, rows: list[dict]) -> None:
        path = self._path(name)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    def start_run(self, run_id: str, started_at: datetime) -> None:
        rows = self._load("runs")
        existing = next((row for row in rows if row["run_id"] == run_id), None)
        if existing:
            existing["completed_at"] = None
            existing["status"] = "running"
        else:
            rows.append(
                {
                    "run_id": run_id,
                    "started_at": isoformat(started_at),
                    "completed_at": None,
                    "source": "course_explorer",
                    "is_demo": False,
                    "status": "running",
                }
            )
        self._write("runs", rows)

    def save_raw_response(self, response: RawResponse) -> None:
        rows = self._load("raw_responses")
        key = (response.run_id, response.request_url)
        if any((row["run_id"], row["request_url"]) == key for row in rows):
            return
        rows.append(
            {
                "run_id": response.run_id,
                "request_url": response.request_url,
                "retrieved_at": isoformat(response.retrieved_at),
                "status_code": response.status_code,
                "content_type": response.content_type,
                "sha256": hashlib.sha256(response.body).hexdigest(),
                "byte_count": len(response.body),
            }
        )
        self._write("raw_responses", rows)

    def save_observations(
        self, sections: Sequence[Section], snapshots: Sequence[Snapshot]
    ) -> None:
        section_rows = self._load("sections")
        section_index = {
            (row["term"], row["crn"]): index
            for index, row in enumerate(section_rows)
        }
        for section in sections:
            row = asdict(section)
            key = (section.term, section.crn)
            if key in section_index:
                old = section_rows[section_index[key]]
                for field, value in row.items():
                    if value is not None:
                        old[field] = value
            else:
                section_index[key] = len(section_rows)
                section_rows.append(row)
        self._write("sections", section_rows)

        snapshot_rows = self._load("snapshots")
        keys = {
            (row["run_id"], row["term"], row["crn"])
            for row in snapshot_rows
        }
        for snapshot in snapshots:
            key = (snapshot.run_id, snapshot.term, snapshot.crn)
            if key in keys:
                continue
            row = asdict(snapshot)
            row["observed_at"] = isoformat(snapshot.observed_at)
            row["source"] = "course_explorer"
            row["is_demo"] = False
            snapshot_rows.append(row)
            keys.add(key)
        self._write("snapshots", snapshot_rows)

    def record_failure(
        self, run_id: str, request_url: str, error_type: str, error_message: str
    ) -> None:
        rows = self._load("failures")
        key = (run_id, request_url)
        row = {
            "run_id": run_id,
            "request_url": request_url,
            "occurred_at": isoformat(utc_now()),
            "error_type": error_type,
            "error_message": error_message,
        }
        existing_index = next(
            (
                index
                for index, old in enumerate(rows)
                if (old["run_id"], old["request_url"]) == key
            ),
            None,
        )
        if existing_index is None:
            rows.append(row)
        else:
            rows[existing_index] = row
        self._write("failures", rows)

    def finish_run(self, run_id: str, status: str, completed_at: datetime) -> None:
        rows = self._load("runs")
        run = next((row for row in rows if row["run_id"] == run_id), None)
        if run is None:
            raise ValueError(f"Unknown run ID {run_id}")
        run["completed_at"] = isoformat(completed_at)
        run["status"] = status
        self._write("runs", rows)

    def close(self) -> None:
        pass


class PostgresStorage:
    def __init__(self, database_url: str):
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - dependency error is environment-specific
            raise RuntimeError("Install requirements.txt to use PostgreSQL") from exc
        self._connection = psycopg.connect(database_url)

    def start_run(self, run_id: str, started_at: datetime) -> None:
        with self._connection.transaction():
            self._connection.execute(
                """
                INSERT INTO collection_runs
                    (run_id, started_at, completed_at, source, is_demo, status)
                VALUES (%s, %s, NULL, 'course_explorer', FALSE, 'running')
                ON CONFLICT (run_id) DO UPDATE
                SET completed_at = NULL, status = 'running'
                """,
                (run_id, started_at),
            )

    def save_raw_response(self, response: RawResponse) -> None:
        with self._connection.transaction():
            self._connection.execute(
                """
                INSERT INTO raw_responses
                    (run_id, request_url, retrieved_at, status_code, content_type,
                     body, sha256)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id, request_url) DO NOTHING
                """,
                (
                    response.run_id,
                    response.request_url,
                    response.retrieved_at,
                    response.status_code,
                    response.content_type,
                    response.body,
                    hashlib.sha256(response.body).hexdigest(),
                ),
            )

    def save_observations(
        self, sections: Sequence[Section], snapshots: Sequence[Snapshot]
    ) -> None:
        with self._connection.transaction():
            for section in sections:
                self._connection.execute(
                    """
                    INSERT INTO sections
                        (term, crn, subject, course_number, section_number, instructor,
                         meeting_summary, cross_list_group)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (term, crn) DO UPDATE SET
                        subject = EXCLUDED.subject,
                        course_number = EXCLUDED.course_number,
                        section_number = EXCLUDED.section_number,
                        instructor = COALESCE(EXCLUDED.instructor, sections.instructor),
                        meeting_summary = COALESCE(
                            EXCLUDED.meeting_summary, sections.meeting_summary
                        ),
                        cross_list_group = COALESCE(
                            EXCLUDED.cross_list_group, sections.cross_list_group
                        )
                    """,
                    (
                        section.term,
                        section.crn,
                        section.subject,
                        section.course_number,
                        section.section_number,
                        section.instructor,
                        section.meeting_summary,
                        section.cross_list_group,
                    ),
                )
            for snapshot in snapshots:
                self._connection.execute(
                    """
                    INSERT INTO snapshots
                        (run_id, term, crn, observed_at, raw_status, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (run_id, term, crn) DO NOTHING
                    """,
                    (
                        snapshot.run_id,
                        snapshot.term,
                        snapshot.crn,
                        snapshot.observed_at,
                        snapshot.raw_status,
                        snapshot.status,
                    ),
                )

    def record_failure(
        self, run_id: str, request_url: str, error_type: str, error_message: str
    ) -> None:
        with self._connection.transaction():
            self._connection.execute(
                """
                INSERT INTO collection_failures
                    (run_id, request_url, occurred_at, error_type, error_message)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (run_id, request_url) DO UPDATE SET
                    occurred_at = EXCLUDED.occurred_at,
                    error_type = EXCLUDED.error_type,
                    error_message = EXCLUDED.error_message
                """,
                (run_id, request_url, utc_now(), error_type, error_message),
            )

    def finish_run(self, run_id: str, status: str, completed_at: datetime) -> None:
        with self._connection.transaction():
            self._connection.execute(
                """
                UPDATE collection_runs
                SET completed_at = %s, status = %s
                WHERE run_id = %s
                """,
                (completed_at, status, run_id),
            )

    def close(self) -> None:
        self._connection.close()
