"""Collector orchestration independent of command-line and storage details."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from collector.course_explorer import (
    CourseExplorerClient,
    FetchError,
    ParseError,
    course_urls,
    parse_course_page,
    parse_course_xml,
)
from collector.models import (
    CollectionSummary,
    CourseSpec,
    FetchResult,
    RawResponse,
)
from collector.storage import Storage


LOGGER = logging.getLogger(__name__)


def _save_raw_file(
    raw_directory: Path,
    run_id: str,
    course: CourseSpec,
    kind: str,
    response: FetchResult,
) -> Path:
    run_directory = raw_directory / run_id
    run_directory.mkdir(parents=True, exist_ok=True)
    path = run_directory / f"{course.slug}.{kind}"
    if not path.exists():
        path.write_bytes(response.body)
    return path


def _persist_raw(
    storage: Storage,
    raw_directory: Path,
    run_id: str,
    course: CourseSpec,
    kind: str,
    response: FetchResult,
) -> None:
    path = _save_raw_file(raw_directory, run_id, course, kind, response)
    LOGGER.info("Saved raw response to %s", path)
    storage.save_raw_response(
        RawResponse(
            run_id=run_id,
            request_url=response.url,
            retrieved_at=response.retrieved_at,
            status_code=response.status_code,
            content_type=response.content_type,
            body=response.body,
        )
    )


def collect(
    *,
    term: str,
    courses: Sequence[CourseSpec],
    run_id: str,
    client: CourseExplorerClient,
    storage: Storage,
    raw_directory: Path,
) -> CollectionSummary:
    started_at = datetime.now(timezone.utc)
    timer_started = time.monotonic()
    storage.start_run(run_id, started_at)
    courses_succeeded = 0
    sections_observed = 0
    failures = 0

    for course in courses:
        xml_url, html_url = course_urls(term, course)
        LOGGER.info("Collecting %s %s for %s", course.subject, course.number, term)
        try:
            xml_response = client.fetch(xml_url)
            _persist_raw(storage, raw_directory, run_id, course, "xml", xml_response)
            html_response = client.fetch(html_url)
            _persist_raw(storage, raw_directory, run_id, course, "html", html_response)

            section_numbers = parse_course_xml(xml_response.body)
            sections, snapshots = parse_course_page(
                html_response.body,
                term=term,
                course=course,
                section_numbers=section_numbers,
                run_id=run_id,
                observed_at=html_response.retrieved_at,
            )
            storage.save_observations(sections, snapshots)
            courses_succeeded += 1
            sections_observed += len(snapshots)
            LOGGER.info("Recorded %d section snapshots", len(snapshots))
        except (FetchError, ParseError, ValueError) as exc:
            failures += 1
            request_url = exc.url if isinstance(exc, FetchError) else html_url
            storage.record_failure(
                run_id=run_id,
                request_url=request_url,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            LOGGER.error("Could not collect %s: %s", course.slug, exc)

    if courses_succeeded == len(courses):
        status = "complete"
    elif courses_succeeded:
        status = "partial"
    else:
        status = "failed"
    completed_at = datetime.now(timezone.utc)
    storage.finish_run(run_id, status, completed_at)
    return CollectionSummary(
        run_id=run_id,
        status=status,
        courses_requested=len(courses),
        courses_succeeded=courses_succeeded,
        sections_observed=sections_observed,
        courses_failed=failures,
        request_count=client.request_count,
        runtime_seconds=round(time.monotonic() - timer_started, 3),
    )
