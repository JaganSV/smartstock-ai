"""Seed CLI behaviour (no database): exit codes, dry run, static source checks."""

import ast
import dataclasses
from pathlib import Path

import pytest

import data.seed.generator as generator
from data.seed.report import Check

SEED_DIR = Path(__file__).resolve().parents[2] / "data" / "seed"
FORBIDDEN_MODULES = {"random", "uuid", "faker", "secrets"}


def test_refuses_to_run_outside_local_or_test(capsys: pytest.CaptureFixture[str]) -> None:
    assert generator.main(["--dry-run"], app_env="production") == 2
    assert "Refusing to seed" in capsys.readouterr().err


@pytest.mark.parametrize("env", ["local", "test"])
def test_dry_run_succeeds_in_allowed_environments(
    env: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert generator.main(["--dry-run"], app_env=env) == 0
    out = capsys.readouterr().out
    assert "Overall coverage result: **PASS**" in out
    assert "database untouched" in out


def test_bad_arguments_exit_with_code_2() -> None:
    with pytest.raises(SystemExit) as info:
        generator.main(["--as-of", "not-a-date"], app_env="local")
    assert info.value.code == 2


def test_coverage_failure_exits_1_and_prints_failing_rows(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    real_run_checks = generator.run_checks

    def broken(ds: generator.Dataset) -> list[Check]:
        checks = real_run_checks(ds)
        checks[0] = dataclasses.replace(checks[0], passed=False)
        return checks

    monkeypatch.setattr(generator, "run_checks", broken)
    assert generator.main(["--dry-run"], app_env="local") == 1
    err = capsys.readouterr().err
    assert "Coverage check FAILED" in err
    assert "SKU-001" in err


def test_coverage_failure_never_touches_the_database(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the database must not be used after a coverage failure")

    monkeypatch.setattr(generator, "create_engine", boom)
    monkeypatch.setattr(generator, "run_checks", lambda ds: [])
    # an empty check list fails the BP 2.4 minimum counts, so no engine may be created
    assert generator.main([], app_env="local") == 1


def test_database_error_exits_3_with_a_clear_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "59999")
    generator.get_settings.cache_clear()
    try:
        assert generator.main(["--report-path", "unused.md"], app_env="local") == 3
    finally:
        generator.get_settings.cache_clear()
    err = capsys.readouterr().err
    assert "rolled back" in err
    assert "test-db-password" not in err


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_no_random_uuid_or_faker_imports_in_seed_package() -> None:
    files = sorted(SEED_DIR.glob("*.py"))
    assert len(files) >= 7
    for path in files:
        assert _imports(path) & FORBIDDEN_MODULES == set(), path.name


def test_no_wall_clock_or_hash_randomness_in_seed_package() -> None:
    banned = ("datetime.now", "date.today", "time.time(", "utcnow", "hash(", "default_rng()")
    for path in sorted(SEED_DIR.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        # generator.py may use perf_counter() for timing only; that never feeds the data
        for token in banned:
            assert token not in source, f"{path.name} uses {token}"
