"""Command-line entry point for the Course Explorer collector."""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import asdict
from pathlib import Path
from uuid import UUID, uuid4

from collector.course_explorer import CourseExplorerClient, term_parts
from collector.models import CourseSpec
from collector.runner import collect
from collector.storage import JsonStorage, PostgresStorage


DEFAULT_USER_AGENT = "CourseCast/0.1 (UIUC student project; SIGAIDA/ACM@UIUC)"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect public UIUC Course Explorer section-status snapshots."
    )
    parser.add_argument("--term", required=True, help="Canonical term, e.g. 2027-spring")
    parser.add_argument(
        "--course",
        action="append",
        required=True,
        help="Pilot course as SUBJECT:NUMBER; repeat for multiple courses",
    )
    parser.add_argument(
        "--run-id",
        help="Reuse this UUID only when safely retrying the same logical run",
    )
    parser.add_argument(
        "--store",
        choices=("postgres", "json"),
        default=None,
        help="Defaults to postgres when DATABASE_URL is set, otherwise json",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="PostgreSQL connection URL (defaults to DATABASE_URL)",
    )
    parser.add_argument("--json-directory", type=Path, default=Path("data/live"))
    parser.add_argument("--raw-directory", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--user-agent",
        default=os.getenv("COURSECAST_USER_AGENT", DEFAULT_USER_AGENT),
    )
    parser.add_argument(
        "--request-interval",
        type=float,
        default=float(os.getenv("COURSECAST_REQUEST_INTERVAL", "1.0")),
        help="Minimum seconds between requests",
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    try:
        term_parts(args.term)
        courses = list(dict.fromkeys(CourseSpec.parse(value) for value in args.course))
        run_id = str(UUID(args.run_id)) if args.run_id else str(uuid4())
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    store_name = args.store or ("postgres" if args.database_url else "json")
    if store_name == "postgres":
        if not args.database_url:
            raise SystemExit("--database-url or DATABASE_URL is required for postgres")
        storage = PostgresStorage(args.database_url)
    else:
        storage = JsonStorage(args.json_directory)

    try:
        with CourseExplorerClient(
            user_agent=args.user_agent,
            request_interval=args.request_interval,
            timeout=args.timeout,
            retries=args.retries,
        ) as client:
            summary = collect(
                term=args.term.lower(),
                courses=courses,
                run_id=run_id,
                client=client,
                storage=storage,
                raw_directory=args.raw_directory,
            )
    finally:
        storage.close()

    print(json.dumps(asdict(summary), indent=2))
    return 0 if summary.status != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
