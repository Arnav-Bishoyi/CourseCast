"""Small data objects shared by the collector, parsers, and storage backends."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CourseSpec:
    subject: str
    number: str

    @classmethod
    def parse(cls, value: str) -> "CourseSpec":
        try:
            subject, number = value.split(":", maxsplit=1)
        except ValueError as exc:
            raise ValueError(f"Course must look like CS:225, not {value!r}") from exc
        subject = subject.strip().upper()
        number = number.strip().upper()
        if not subject or not number or "/" in subject or "/" in number:
            raise ValueError(f"Invalid course {value!r}")
        return cls(subject=subject, number=number)

    @property
    def slug(self) -> str:
        return f"{self.subject}-{self.number}"


@dataclass(frozen=True, slots=True)
class Section:
    term: str
    crn: str
    subject: str
    course_number: str
    section_number: str
    instructor: str | None
    meeting_summary: str | None
    cross_list_group: str | None = None


@dataclass(frozen=True, slots=True)
class Snapshot:
    run_id: str
    term: str
    crn: str
    observed_at: datetime
    raw_status: str | None
    status: str


@dataclass(frozen=True, slots=True)
class RawResponse:
    run_id: str
    request_url: str
    retrieved_at: datetime
    status_code: int
    content_type: str | None
    body: bytes


@dataclass(frozen=True, slots=True)
class FetchResult:
    url: str
    retrieved_at: datetime
    status_code: int
    content_type: str | None
    body: bytes


@dataclass(frozen=True, slots=True)
class CollectionSummary:
    run_id: str
    status: str
    courses_requested: int
    courses_succeeded: int
    sections_observed: int
    courses_failed: int
    request_count: int
    runtime_seconds: float
