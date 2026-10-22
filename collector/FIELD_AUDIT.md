# Course Explorer field audit

Audit date: October 21, 2026

Pilot: Spring 2027 CS 225

Public sources only:

- `https://courses.illinois.edu/cisapp/explorer/schedule/2027/spring/CS/225.xml`
- `https://courses.illinois.edu/schedule/2027/spring/CS/225`

## What the responses contain

The course XML provides the course label and description plus a section list.
Each section entry has a five-digit CRN (`id`), displayed section number, and a
link to section XML. Individual section XML includes parent term/subject/course,
section number, `statusCode`, `sectionStatusCode`, date range, meeting type/time,
location, and instructors when published.

The HTML course page provides the current student-facing availability for every
section along with CRN, type, section number, meeting time, days, location,
instructors, restrictions, and other display details. Observed availability
values included `Open` and `CrossListOpen (Restricted)`.

## Important findings

- Spring 2027 is published, so no Fall 2026 fallback is needed for the pilot.
- XML `statusCode=A` and `sectionStatusCode=A` are not sufficient live
  availability fields. During the audit, CRN 31208 had those XML codes while the
  HTML page displayed `CrossListOpen (Restricted)`.
- No seat-capacity, enrolled-count, or remaining-seat fields appeared in the
  inspected responses. The v1 collector does not invent them.
- Course pages can state cross-listed equivalents and availability can start with
  `CrossList`, but the inspected section XML did not expose a reliable
  cross-list-group identifier. `cross_list_group` therefore remains null.
- Restrictions are not the same as closure. The collector preserves the full raw
  availability and normalizes restricted open values to `open` for the v1 schema.
- If an expected section has no status row, it is recorded as `unknown`. A failed
  course request records a failure and no section statuses for that course.

## Join and timestamp choices

- Section identity: canonical term string plus CRN, e.g. `(2027-spring, 31208)`.
- Observation time: UTC time immediately after the HTML response is received.
- Run identity: UUID. The same UUID is used only to retry the same logical run;
  later collections use new UUIDs.
- Raw and normalized status are both retained.

This audit describes the source as observed on the audit date. The parser treats
unrecognized future values as `unknown` so source changes fail safely.
