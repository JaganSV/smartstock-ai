"""Import-boundary test (BP §4.1 principle 4): analytics stays pure.

``app/analytics`` must not import from ``app.repositories``, ``app.api`` or ``app.ai`` (directly
or via ``from x import y``). Static AST walk, so it also catches imports inside functions.
"""

import ast
from pathlib import Path

import pytest

ANALYTICS_DIR = Path(__file__).resolve().parents[2] / "app" / "analytics"
FORBIDDEN = ("app.repositories", "app.api", "app.ai")


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
