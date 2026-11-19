"""Seed against the real PostgreSQL test database (strict mode applies via conftest).

The seed commits, so a module fixture empties the seeded tables before and after these tests.
"""

import dataclasses
from collections.abc import Iterator
from datetime import UTC
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import data.seed.generator as generator
from app.models import IncomingStock, InventoryLevel, Product, SalesDaily
from data.seed.generator import (
    UNSEEDED_TABLES,
    build_dataset,
    count_rows,
    db_checksums,
    delete_seeded,
    seed_database,
)
from data.seed.report import TABLE_COLUMNS, Dataset, canonical_rows, checksums

pytestmark = pytest.mark.integration

EXPECTED_COUNTS = {
    "categories": 5,
    "incoming_stock": 113,
    "inventory_levels": 150,
    "inventory_policies": 150,
    "products": 50,
    "sales_daily": 13_500,
    "suppliers": 5,
    "warehouses": 3,
}


@pytest.fixture(scope="module")
def ds() -> Dataset:
    return build_dataset(generator.DEFAULT_SEED, generator.DEFAULT_AS_OF)


@pytest.fixture
def engine(migrated_engine: Engine) -> Iterator[Engine]:
    def clean() -> None:
        with Session(migrated_engine) as session, session.begin():
            delete_seeded(session)

    clean()
    yield migrated_engine
    clean()


def _snapshot(engine: Engine) -> tuple[dict[str, int], str]:
    with Session(engine) as session:
        return count_rows(session, sorted(TABLE_COLUMNS)), db_checksums(session)[1]


def test_seed_twice_gives_same_counts_and_db_checksum(engine: Engine, ds: Dataset) -> None:
    first_checksum, first_counts = seed_database(engine, ds)
    assert first_counts == EXPECTED_COUNTS
    second_checksum, second_counts = seed_database(engine, ds)  # idempotent re-seed
    assert second_counts == first_counts
    assert second_checksum == first_checksum == checksums(canonical_rows(ds))[1]
    assert _snapshot(engine) == (EXPECTED_COUNTS, first_checksum)


def test_different_seed_gives_different_db_checksum(engine: Engine, ds: Dataset) -> None:
    base, _ = seed_database(engine, ds)
    other, _ = seed_database(engine, build_dataset(43, generator.DEFAULT_AS_OF))
    assert other != base


def test_non_seeded_tables_stay_empty(engine: Engine, ds: Dataset) -> None:
    seed_database(engine, ds)
    with Session(engine) as session:
        assert count_rows(session, UNSEEDED_TABLES) == {name: 0 for name in UNSEEDED_TABLES}


def test_seeded_data_satisfies_the_schema_and_reference_rules(engine: Engine, ds: Dataset) -> None:
    seed_database(engine, ds)
    with Session(engine) as session:
        stamps = set(session.scalars(select(InventoryLevel.as_of)))
        assert len(stamps) == 1
        stamp = stamps.pop()
        # the same instant, whatever time zone the DB session reports it in
        assert stamp.astimezone(UTC).isoformat() == "2026-09-30T23:59:59+00:00"
        low, high, days = session.execute(
            select(
                func.min(SalesDaily.sale_date),
                func.max(SalesDaily.sale_date),
                func.count(func.distinct(SalesDaily.sale_date)),
            )
        ).one()
        assert (low.isoformat(), high.isoformat(), days) == ("2026-07-03", "2026-09-30", 90)
        assert session.scalar(select(func.min(SalesDaily.units_sold))) >= 0
        assert session.scalar(select(func.count()).select_from(Product)) == 50
        statuses = {
            status: count
            for status, count in session.execute(
                select(IncomingStock.status, func.count()).group_by(IncomingStock.status)
            )
        }
        assert statuses["CANCELLED"] == 4
        assert (
            session.scalar(
                select(func.count())
                .select_from(IncomingStock)
                .where(IncomingStock.expected_arrival_date < IncomingStock.order_date)
            )
            == 0
        )


def test_forced_constraint_violation_rolls_back_the_whole_seed(engine: Engine, ds: Dataset) -> None:
    seed_database(engine, ds)
    before = _snapshot(engine)

    bad_units = ds.demand.units.copy()
    bad_units[0, 0, 0] = -1  # violates ck_sales_daily_units_sold_nonneg (the last table written)
    bad = dataclasses.replace(ds, demand=dataclasses.replace(ds.demand, units=bad_units))
    with pytest.raises(SQLAlchemyError):
        seed_database(engine, bad)

    assert _snapshot(engine) == before  # delete + inserts were all rolled back


def test_cli_db_error_exits_3_and_leaves_the_database_unchanged(
    engine: Engine,
    ds: Dataset,
    test_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seed_database(engine, ds)
    before = _snapshot(engine)

    def fail(*_args: object, **_kwargs: object) -> None:
        raise SQLAlchemyError("forced failure after the delete step")

    monkeypatch.setattr(
        generator, "create_engine", lambda *_a, **_k: create_engine(test_database_url)
    )
    monkeypatch.setattr(generator, "insert_sales", fail)
    assert generator.main(["--report-path", "unused.md"], app_env="test") == 3
    assert "rolled back" in capsys.readouterr().err
    assert _snapshot(engine) == before


def test_cli_seed_twice_via_main_gives_identical_checksums(
    engine: Engine,
    test_database_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        generator, "create_engine", lambda *_a, **_k: create_engine(test_database_url)
    )
    report = str(tmp_path / "seed_report.md")
    outputs = []
    for _ in range(2):
        assert generator.main(["--report-path", report], app_env="test") == 0
        outputs.append(capsys.readouterr().out)
    checksum_lines = [
        next(line for line in out.splitlines() if line.startswith("overall checksum"))
        for out in outputs
    ]
    assert checksum_lines[0] == checksum_lines[1]
    assert (
        (tmp_path / "seed_report.md")
        .read_text(encoding="utf-8")
        .endswith("Synthetic data — fictional entities only.\n")
    )
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM products")).scalar_one() == 50
