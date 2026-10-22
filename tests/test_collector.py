import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx

from collector.course_explorer import (
    CourseExplorerClient,
    FetchError,
    normalize_status,
    parse_course_page,
    parse_course_xml,
)
from collector.models import CourseSpec, Section, Snapshot
from collector.runner import collect
from collector.storage import JsonStorage


COURSE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<course xmlns="http://rest.cis.illinois.edu" id="CS 225">
  <sections>
    <section id="31208">AL1</section>
    <section id="31234">AYA</section>
    <section id="39999">MISSING</section>
  </sections>
</course>
"""

COURSE_HTML = b"""<!doctype html>
<html><body><table><tbody>
  <tr>
    <td class="sd-control"></td>
    <td><i role="img" aria-label="Section CrossListOpen (Restricted)"></i></td>
    <td><a href="/userredirect/favorite/2027/spring/CS/225/31208">star</a></td>
    <td><div>31208</div></td>
    <td><div>Lecture</div></td>
    <td><div>AL1</div></td>
    <td><div>11:00AM -11:50AM</div></td>
    <td><div>MWF</div></td>
    <td><div>Auditorium</div></td>
    <td class="instructor"><div>Erickson, J</div></td>
    <td><dl><dt>Availability:</dt><dd>CrossListOpen (Restricted)</dd></dl></td>
  </tr>
  <tr>
    <td class="sd-control"></td>
    <td><i role="img" aria-label="Section Closed"></i></td>
    <td><a href="/userredirect/favorite/2027/spring/CS/225/31234">star</a></td>
    <td><div>31234</div></td>
    <td><div>Laboratory-Discussion</div></td>
    <td><div>AYA</div></td>
    <td><div>9:00AM -10:50AM</div></td>
    <td><div>T</div></td>
    <td><div>Siebel Center</div></td>
    <td class="instructor"><div>Staff</div></td>
    <td><dl><dt>Availability:</dt><dd>Closed</dd></dl></td>
  </tr>
</tbody></table></body></html>
"""


class ParserTests(unittest.TestCase):
    def test_parse_course_xml(self):
        self.assertEqual(
            parse_course_xml(COURSE_XML),
            {"31208": "AL1", "31234": "AYA", "39999": "MISSING"},
        )

    def test_status_normalization_is_conservative(self):
        self.assertEqual(normalize_status("Open"), "open")
        self.assertEqual(normalize_status("Open (Restricted)"), "open")
        self.assertEqual(normalize_status("CrossListOpen (Restricted)"), "open")
        self.assertEqual(normalize_status("Closed"), "closed")
        self.assertEqual(normalize_status("Pending"), "unknown")
        self.assertEqual(normalize_status("Opening soon"), "unknown")
        self.assertEqual(normalize_status("surprise-new-value"), "unknown")
        self.assertEqual(normalize_status(None), "unknown")

    def test_parse_page_preserves_raw_status_and_marks_missing_unknown(self):
        run_id = str(uuid4())
        observed_at = datetime(2026, 10, 21, 15, 30, tzinfo=timezone.utc)
        sections, snapshots = parse_course_page(
            COURSE_HTML,
            term="2027-spring",
            course=CourseSpec("CS", "225"),
            section_numbers=parse_course_xml(COURSE_XML),
            run_id=run_id,
            observed_at=observed_at,
        )

        self.assertEqual([section.crn for section in sections], ["31208", "31234", "39999"])
        by_crn = {snapshot.crn: snapshot for snapshot in snapshots}
        self.assertEqual(by_crn["31208"].raw_status, "CrossListOpen (Restricted)")
        self.assertEqual(by_crn["31208"].status, "open")
        self.assertEqual(by_crn["31234"].status, "closed")
        self.assertIsNone(by_crn["39999"].raw_status)
        self.assertEqual(by_crn["39999"].status, "unknown")
        self.assertEqual(sections[0].instructor, "Erickson, J")
        self.assertIn("Lecture", sections[0].meeting_summary)


class ClientTests(unittest.TestCase):
    def test_client_retries_a_server_error_then_succeeds(self):
        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(503, request=request)
            return httpx.Response(200, content=b"ok", request=request)

        client = CourseExplorerClient(
            user_agent="CourseCast test",
            request_interval=0,
            retries=1,
            transport=httpx.MockTransport(handler),
            sleep=lambda _seconds: None,
        )
        try:
            response = client.fetch("https://example.test/course")
        finally:
            client.close()
        self.assertEqual(response.body, b"ok")
        self.assertEqual(client.request_count, 2)

    def test_client_stops_after_bounded_retries(self):
        def handler(request):
            return httpx.Response(503, request=request)

        client = CourseExplorerClient(
            user_agent="CourseCast test",
            request_interval=0,
            retries=2,
            transport=httpx.MockTransport(handler),
            sleep=lambda _seconds: None,
        )
        try:
            with self.assertRaises(FetchError):
                client.fetch("https://example.test/course")
        finally:
            client.close()
        self.assertEqual(client.request_count, 3)


class JsonStorageTests(unittest.TestCase):
    def test_same_run_is_idempotent_and_later_run_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = JsonStorage(Path(directory))
            now = datetime(2026, 10, 21, 15, 30, tzinfo=timezone.utc)
            section = Section(
                term="2027-spring",
                crn="31208",
                subject="CS",
                course_number="225",
                section_number="AL1",
                instructor="Erickson, J",
                meeting_summary="Lecture",
            )
            run_a = str(uuid4())
            snapshot_a = Snapshot(run_a, "2027-spring", "31208", now, "Open", "open")

            storage.start_run(run_a, now)
            storage.save_observations([section], [snapshot_a])
            storage.save_observations([section], [snapshot_a])
            storage.finish_run(run_a, "complete", now)

            snapshots = json.loads((Path(directory) / "snapshots.json").read_text())
            self.assertEqual(len(snapshots), 1)

            run_b = str(uuid4())
            snapshot_b = Snapshot(run_b, "2027-spring", "31208", now, "Closed", "closed")
            storage.start_run(run_b, now)
            storage.save_observations([section], [snapshot_b])
            storage.finish_run(run_b, "complete", now)

            snapshots = json.loads((Path(directory) / "snapshots.json").read_text())
            self.assertEqual(len(snapshots), 2)
            self.assertEqual({row["run_id"] for row in snapshots}, {run_a, run_b})


class RunnerTests(unittest.TestCase):
    def test_failed_request_is_logged_without_invented_snapshots(self):
        class FailingClient:
            request_count = 3

            def fetch(self, url):
                raise FetchError(url, attempts=3, message="temporary outage")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = JsonStorage(root / "live")
            with self.assertLogs("collector.runner", level="ERROR"):
                summary = collect(
                    term="2027-spring",
                    courses=[CourseSpec("CS", "225")],
                    run_id=str(uuid4()),
                    client=FailingClient(),
                    storage=store,
                    raw_directory=root / "raw",
                )

            self.assertEqual(summary.status, "failed")
            self.assertEqual(summary.sections_observed, 0)
            self.assertFalse((root / "live" / "snapshots.json").exists())
            failures = json.loads((root / "live" / "failures.json").read_text())
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0]["error_type"], "FetchError")


if __name__ == "__main__":
    unittest.main()
