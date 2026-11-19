"""Import-boundary test (BP §4.1 principle 4): analytics stays pure.

``app/analytics`` must not import from ``app.repositories``, ``app.api`` or ``app.ai`` (directly
or via ``from x import y``). Static AST walk, so it also catches imports inside functions.
"""

import ast
from pathlib import Path

import pytest

ANALYTICS_DIR = Path(__file__).resolve().parents[2] / "app" / "analytics"
FORBIDDEN = ("app.repositories", "app.api", "app.ai", "app.db", "data", "sqlalchemy")


def _imported_modules(tree: ast.AST) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import: resolve against package app.analytics
                base = "app.analytics" + ("." + node.module if node.module else "")
                modules.append(base)
            elif node.module:
                modules.append(node.module)
                modules.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def _violations(source: str) -> list[str]:
    return [
        m
        for m in _imported_modules(ast.parse(source))
        if any(m == f or m.startswith(f + ".") for f in FORBIDDEN)
    ]


def test_analytics_package_exists_and_is_scanned() -> None:
    assert (ANALYTICS_DIR / "__init__.py").is_file()


def test_analytics_has_no_forbidden_imports() -> None:
    offenders: dict[str, list[str]] = {}
    for path in ANALYTICS_DIR.rglob("*.py"):
        bad = _violations(path.read_text(encoding="utf-8"))
        if bad:
            offenders[str(path.relative_to(ANALYTICS_DIR))] = bad
    assert offenders == {}


@pytest.mark.parametrize(
    "source",
    [
        "import app.repositories",
        "from app.repositories.sales import SalesRepository",
        "from app import repositories",
        "from app.api.v1 import health",
        "import app.ai.rag",
        "def f():\n    from app.ai import client",
    ],
)
def test_detector_catches_forbidden_imports(source: str) -> None:
    """Guards the guard: the scanner really flags each import style."""
    assert _violations(source) != []


def test_detector_allows_models_and_stdlib() -> None:
    assert (
        _violations("import math\nfrom app.models import Product\nfrom app.core import config")
        == []
    )


# --- data/seed boundaries (BOB-P1-02 section 10) ---

APP_DIR = Path(__file__).resolve().parents[2] / "app"
SEED_DIR = Path(__file__).resolve().parents[2] / "data" / "seed"
SEED_FORBIDDEN = ("app.repositories", "app.api", "app.ai")


def _imports_of(source: str, forbidden: tuple[str, ...]) -> list[str]:
    return [
        m
        for m in _imported_modules(ast.parse(source))
        if any(m == f or m.startswith(f + ".") for f in forbidden)
    ]


def test_seed_package_is_scanned() -> None:
    assert len(list(SEED_DIR.glob("*.py"))) >= 7


def test_data_seed_does_not_import_repositories_api_or_ai() -> None:
    offenders = {
        path.name: bad
        for path in SEED_DIR.rglob("*.py")
        if (bad := _imports_of(path.read_text(encoding="utf-8"), SEED_FORBIDDEN))
    }
    assert offenders == {}


def test_app_never_imports_data() -> None:
    """Scenario-target formulas live in data/seed only; P2 implements the real ones itself."""
    offenders = {
        str(path.relative_to(APP_DIR)): bad
        for path in APP_DIR.rglob("*.py")
        if (bad := _imports_of(path.read_text(encoding="utf-8"), ("data",)))
    }
    assert offenders == {}


@pytest.mark.parametrize(
    ("source", "forbidden"),
    [
        ("from app.repositories.sales import SalesRepository", SEED_FORBIDDEN),
        ("import app.api.v1.health", SEED_FORBIDDEN),
        ("from app.ai import rag", SEED_FORBIDDEN),
        ("import data.seed.scenarios", ("data",)),
        ("from data.seed import catalog", ("data",)),
        ("def f():\n    from data.seed.report import checksums", ("data",)),
    ],
)
def test_seed_detector_catches_forbidden_imports(source: str, forbidden: tuple[str, ...]) -> None:
    assert _imports_of(source, forbidden) != []


def test_seed_detector_allows_models_and_config() -> None:
    source = "from app.models import Product\nfrom app.core.config import get_settings"
    assert _imports_of(source, SEED_FORBIDDEN) == []


# --- analytics purity (BOB-P2-01): no wall clock, no global NumPy warning suppression ---

WALL_CLOCK_TOKENS = (
    "date.today",
    "datetime.now",
    "datetime.utcnow",
    "time.time(",
    "time.monotonic",
)
SUPPRESSION_TOKENS = (
    "np.seterr",
    "numpy.seterr",
    "np.errstate",
    "numpy.errstate",
    "filterwarnings",
)


def test_analytics_never_reads_the_wall_clock() -> None:
    """ADR-012: all date logic uses the supplied t0."""
    for path in ANALYTICS_DIR.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for token in WALL_CLOCK_TOKENS:
            assert token not in source, f"{path.name} uses {token}"


def test_analytics_does_not_silence_numpy_warnings_or_catch_zero_division() -> None:
    for path in ANALYTICS_DIR.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for token in (*SUPPRESSION_TOKENS, "ZeroDivisionError"):
            assert token not in source, f"{path.name} uses {token}"


def test_analytics_reads_no_settings_or_files() -> None:
    for path in ANALYTICS_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert "app.core.config" not in _imported_modules(tree), path.name
        calls = [
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        assert "open" not in calls and "print" not in calls, path.name


@pytest.mark.parametrize(
    "source",
    [
        "import sqlalchemy",
        "from sqlalchemy.orm import Session",
        "from app.db.session import get_db",
        "import data.seed.generator",
        "from data.seed import catalog",
        "from app.repositories.sales import SalesRepository",
    ],
)
def test_extended_detector_catches_the_new_forbidden_imports(source: str) -> None:
    assert _violations(source) != []


def test_extended_detector_allows_pandas_numpy_and_stdlib() -> None:
    assert _violations("import pandas as pd\nimport numpy as np\nfrom datetime import date") == []
