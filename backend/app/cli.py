"""CLI: ``python -m app.cli recalc [--triggered-by cli] [--report PATH]`` and ``seed-users``.

Exit codes: 0 success, 1 analytics/data error, 2 bad arguments or a refused ``seed-users`` run,
3 database error. ``--report`` additionally writes the risk-distribution evidence file (markdown)
after a successful run. ``seed-users`` creates or updates the four demo users and prints no
passwords.
"""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import get_session_factory
from app.services.analytics_service import RecalculationService, SnapshotResult
from app.services.errors import RecalculationError, SeedUsersRefusedError
from app.services.evidence import render_risk_distribution_report
from app.services.user_seed_service import seed_users

EXIT_OK, EXIT_DATA_ERROR, EXIT_REFUSED, EXIT_DB_ERROR = 0, 1, 2, 3

logger = logging.getLogger(__name__)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="SmartStock AI CLI")
    commands = parser.add_subparsers(dest="command", required=True)
    recalc = commands.add_parser("recalc", help="recalculate analytics and write a snapshot")
    recalc.add_argument("--triggered-by", default="cli", help="audit label, [a-z0-9_:-]{1,64}")
    recalc.add_argument("--report", metavar="PATH", help="also write the risk-distribution report")
    commands.add_parser("seed-users", help="create or update the 4 demo users (local/test only)")
    return parser.parse_args(argv)  # argparse exits with code 2 on bad arguments


def _print_result(result: SnapshotResult) -> None:
    print(
        f"Snapshot {result.snapshot_id}: {result.row_count} rows, t0 {result.t0.isoformat()}, "
        f"{result.duration_ms} ms"
    )
    for risk_class, count in result.risk_distribution.items():
        print(f"  {risk_class:<10} {count:>4}")


def _recalc(args: argparse.Namespace) -> int:
    configure_logging(get_settings().log_level)
    try:
        with get_session_factory()() as session:
            service = RecalculationService(session)
            result = service.run(triggered_by=args.triggered_by)
            report = render_risk_distribution_report(service, result) if args.report else None
    except RecalculationError as exc:
        print(f"Recalculation failed ({exc.code}): {exc}", file=sys.stderr)
        return EXIT_DATA_ERROR
    except SQLAlchemyError as exc:
        detail = str(getattr(exc, "orig", exc)).splitlines()[0]
        print(
            f"Database error ({type(exc).__name__}): {detail}\n"
            "The transaction was rolled back; no snapshot was written.",
            file=sys.stderr,
        )
        return EXIT_DB_ERROR
    _print_result(result)
    if args.report and report is not None:
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8", newline="\n")
        print(f"report written to {path}")
    return EXIT_OK


def _seed_users() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    try:
        with get_session_factory()() as session:
            seeded = seed_users(session, settings)
    except SeedUsersRefusedError as exc:
        print(f"Refusing to seed users: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except SQLAlchemyError as exc:
        detail = str(getattr(exc, "orig", exc)).splitlines()[0]
        print(
            f"Database error ({type(exc).__name__}): {detail}\n"
            "The transaction was rolled back; no user was written.",
            file=sys.stderr,
        )
        return EXIT_DB_ERROR
    for user in seeded:
        print(f"  {user.outcome:<8} {user.username:<10} {user.role}")
    print(f"{len(seeded)} demo users ready. Passwords are the SEED_USER_PASSWORD_* values in .env.")
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "recalc":
        return _recalc(args)
    if args.command == "seed-users":
        return _seed_users()
    return EXIT_REFUSED  # unreachable: argparse requires a known command


if __name__ == "__main__":
    sys.exit(main())
