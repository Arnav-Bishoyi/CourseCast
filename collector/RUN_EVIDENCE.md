# Pilot run evidence

Collected October 21, 2026 (America/Chicago) from the public Spring 2027 CS 225
Course Explorer page. The ignored local raw files retain the complete responses;
this note contains only counts and sample parsed records.

## Run A and safe rerun

- Run ID: `a1dcdc71-276f-49d5-ac3d-50307d50163c`
- Requests per execution: 2
- First execution runtime: 1.094 seconds
- Parsed snapshots after first execution: 10
- Safe-rerun runtime: 1.074 seconds
- Parsed snapshots after rerunning the same UUID: 10 (no duplicates)

## Later run B

- Run ID: `7a620028-38db-4ecf-8574-798295f24f72`
- Requests: 2
- Runtime: 1.073 seconds
- Parsed snapshots: 10
- Total snapshots retained across A and B: 20
- Run B raw statuses: 7 `Open`, 3 `CrossListOpen (Restricted)`

## Sample parsed records

Section metadata:

```json
{
  "term": "2027-spring",
  "crn": "70578",
  "subject": "CS",
  "course_number": "225",
  "section_number": "AH",
  "instructor": "Erickson, J",
  "meeting_summary": "Laboratory | 5:00PM -5:50PM | M | 0216 Siebel Center for Comp Sci",
  "cross_list_group": null
}
```

Snapshot from run B:

```json
{
  "run_id": "7a620028-38db-4ecf-8574-798295f24f72",
  "term": "2027-spring",
  "crn": "70578",
  "observed_at": "2026-10-22T03:21:39.015848Z",
  "raw_status": "CrossListOpen (Restricted)",
  "status": "open",
  "source": "course_explorer",
  "is_demo": false
}
```

These values are evidence from a point-in-time pilot, not current registration
advice and not Spring 2027 model-training labels.
