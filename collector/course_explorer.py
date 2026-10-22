"""Polite Course Explorer HTTP client and response parsers."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import quote

import httpx
from lxml import etree, html

from collector.models import CourseSpec, FetchResult, Section, Snapshot


BASE_URL = "https://courses.illinois.edu"
TERM_PATTERN = re.compile(r"^(?P<year>\d{4})-(?P<term>spring|summer|fall|winter)$")


class FetchError(RuntimeError):
    def __init__(self, url: str, attempts: int, message: str):
        super().__init__(f"Failed to fetch {url} after {attempts} attempt(s): {message}")
        self.url = url
        self.attempts = attempts


class ParseError(ValueError):
    pass


def term_parts(term: str) -> tuple[str, str]:
    match = TERM_PATTERN.fullmatch(term.lower())
    if not match:
        raise ValueError("Term must look like 2027-spring")
    return match.group("year"), match.group("term")


def course_urls(term: str, course: CourseSpec) -> tuple[str, str]:
    year, season = term_parts(term)
    subject = quote(course.subject, safe="")
    number = quote(course.number, safe="")
    path = f"{year}/{season}/{subject}/{number}"
    return (
        f"{BASE_URL}/cisapp/explorer/schedule/{path}.xml",
        f"{BASE_URL}/schedule/{path}",
    )


class CourseExplorerClient:
    """Synchronous client with spacing, timeouts, and bounded retries."""

    def __init__(
        self,
        user_agent: str,
        request_interval: float = 1.0,
        timeout: float = 15.0,
        retries: int = 2,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not user_agent.strip():
            raise ValueError("An identifying user agent is required")
        if request_interval < 0 or retries < 0:
            raise ValueError("Request interval and retries cannot be negative")
        self.request_interval = request_interval
        self.retries = retries
        self.request_count = 0
        self._clock = clock
        self._sleep = sleep
        self._last_request_started: float | None = None
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CourseExplorerClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _wait_for_rate_limit(self) -> None:
        if self._last_request_started is None:
            return
        remaining = self.request_interval - (self._clock() - self._last_request_started)
        if remaining > 0:
            self._sleep(remaining)

    def fetch(self, url: str) -> FetchResult:
        last_error = "unknown error"
        attempts = self.retries + 1
        for attempt in range(1, attempts + 1):
            self._wait_for_rate_limit()
            self._last_request_started = self._clock()
            self.request_count += 1
            try:
                response = self._client.get(url)
                response.raise_for_status()
                return FetchResult(
                    url=str(response.url),
                    retrieved_at=datetime.now(timezone.utc),
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type"),
                    body=response.content,
                )
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = str(exc)
                if attempt < attempts:
                    self._sleep(min(0.5 * (2 ** (attempt - 1)), 4.0))
        raise FetchError(url=url, attempts=attempts, message=last_error)


def parse_course_xml(body: bytes) -> dict[str, str]:
    """Return CRN -> section number from the public course XML."""
    try:
        root = etree.fromstring(body)
    except etree.XMLSyntaxError as exc:
        raise ParseError(f"Invalid course XML: {exc}") from exc

    sections: dict[str, str] = {}
    for element in root.xpath("//*[local-name()='sections']/*[local-name()='section']"):
        crn = (element.get("id") or "").strip()
        section_number = " ".join("".join(element.itertext()).split())
        if crn and section_number:
            sections[crn] = section_number
    if not sections:
        raise ParseError("Course XML contained no sections")
    return sections


def normalize_status(raw_status: str | None) -> str:
    """Reduce source values to the v1 open/closed/unknown vocabulary."""
    if raw_status is None:
        return "unknown"
    compact = re.sub(r"[^a-z]", "", raw_status.casefold())
    if compact in {"open", "openrestricted", "crosslistopen", "crosslistopenrestricted"}:
        return "open"
    if compact in {"closed", "crosslistclosed"}:
        return "closed"
    return "unknown"


def _text(element: etree._Element) -> str | None:
    value = " ".join(" ".join(element.itertext()).split())
    return value or None


def _crn_from_row(row: etree._Element) -> str | None:
    favorite_links = row.xpath(".//a[contains(@href, '/favorite/')]/@href")
    if favorite_links:
        candidate = favorite_links[0].rstrip("/").rsplit("/", maxsplit=1)[-1]
        if candidate.isdigit():
            return candidate
    for cell in row.xpath("./td"):
        candidate = _text(cell)
        if candidate and re.fullmatch(r"\d{5}", candidate):
            return candidate
    return None


def parse_course_page(
    body: bytes,
    term: str,
    course: CourseSpec,
    section_numbers: dict[str, str],
    run_id: str,
    observed_at: datetime,
) -> tuple[list[Section], list[Snapshot]]:
    """Parse static metadata and live availability from a course HTML page."""
    try:
        document = html.fromstring(body)
    except (etree.ParserError, ValueError) as exc:
        raise ParseError(f"Invalid course HTML: {exc}") from exc

    parsed: dict[str, tuple[Section, Snapshot]] = {}
    rows = document.xpath("//tr[.//i[starts-with(@aria-label, 'Section ')]]")
    for row in rows:
        crn = _crn_from_row(row)
        if not crn:
            continue
        icons = row.xpath(".//i[starts-with(@aria-label, 'Section ')]/@aria-label")
        if not icons:
            continue
        raw_status = icons[0].removeprefix("Section ").strip() or None
        cells = row.xpath("./td")
        crn_index = next(
            (index for index, cell in enumerate(cells) if _text(cell) == crn),
            None,
        )

        section_number = section_numbers.get(crn, "")
        instructor = None
        meeting_parts: list[str] = []
        if crn_index is not None:
            # The cells after CRN are type, section, time, day, location, instructor.
            values = [
                _text(cells[index]) if index < len(cells) else None
                for index in range(crn_index + 1, crn_index + 7)
            ]
            meeting_type, displayed_section, meeting_time, days, location, instructor = values
            section_number = section_number or displayed_section or ""
            meeting_parts = [
                value for value in (meeting_type, meeting_time, days, location) if value
            ]

        if not section_number:
            raise ParseError(f"Section number missing for CRN {crn}")
        section = Section(
            term=term,
            crn=crn,
            subject=course.subject,
            course_number=course.number,
            section_number=section_number,
            instructor=instructor,
            meeting_summary=" | ".join(meeting_parts) or None,
            cross_list_group=None,
        )
        snapshot = Snapshot(
            run_id=run_id,
            term=term,
            crn=crn,
            observed_at=observed_at,
            raw_status=raw_status,
            status=normalize_status(raw_status),
        )
        parsed[crn] = (section, snapshot)

    if not parsed:
        raise ParseError("Course page contained no recognizable section-status rows")

    # A section present in XML but missing from the status table is unknown, not closed.
    for crn, section_number in section_numbers.items():
        if crn in parsed:
            continue
        parsed[crn] = (
            Section(
                term=term,
                crn=crn,
                subject=course.subject,
                course_number=course.number,
                section_number=section_number,
                instructor=None,
                meeting_summary=None,
                cross_list_group=None,
            ),
            Snapshot(
                run_id=run_id,
                term=term,
                crn=crn,
                observed_at=observed_at,
                raw_status=None,
                status="unknown",
            ),
        )

    ordered = [parsed[crn] for crn in section_numbers if crn in parsed]
    extras = [value for crn, value in parsed.items() if crn not in section_numbers]
    all_rows = ordered + extras
    return [row[0] for row in all_rows], [row[1] for row in all_rows]
