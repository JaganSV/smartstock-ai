"""Per-package coverage table from the ``.coverage`` data written by the last ``make test`` run.

Usage (from ``backend/``): ``python scripts/coverage_summary.py``. It never runs the tests; it only
reads the data file, so the numbers are those of the run that just finished. Exit code 1 when the
data file is missing.
"""

import sys
from pathlib import Path

import coverage

PACKAGES = (
    "app/analytics",
    "app/services",
    "app/repositories",
    "app/api",
    "app/core",
    "data/seed",
)
BACKEND_DIR = Path(__file__).resolve().parents[1]


def package_of(path: Path) -> str | None:
    relative = path.resolve().relative_to(BACKEND_DIR).as_posix()
    return next((pkg for pkg in PACKAGES if relative.startswith(pkg + "/")), None)


def main() -> int:
    data_file = BACKEND_DIR / ".coverage"
    if not data_file.is_file():
        print("No .coverage file: run `make test` first.", file=sys.stderr)
        return 1
    cov = coverage.Coverage(data_file=str(data_file))
    cov.load()
    totals = {pkg: [0, 0] for pkg in PACKAGES}  # statements, missed
    for name in cov.get_data().measured_files():
        path = Path(name)
        try:
            package = package_of(path)
        except ValueError:  # a measured file outside backend/ (not ours)
            continue
        if package is None:
            continue
        _, statements, _, missing, _ = cov.analysis2(name)
        totals[package][0] += len(statements)
        totals[package][1] += len(missing)

    print(f"{'Package':<18} {'Statements':>10} {'Missed':>7} {'Covered %':>10}")
    for package in PACKAGES:
        statements, missed = totals[package]
        percent = 100.0 * (statements - missed) / statements if statements else 0.0
        print(f"{package:<18} {statements:>10} {missed:>7} {percent:>10.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
