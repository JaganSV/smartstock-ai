"""numeric helpers: safe_ceil, safe_ceil_array, money."""

import math
from decimal import Decimal

import numpy as np
import pytest

from app.analytics.numeric import money, safe_ceil, safe_ceil_array


def test_naive_ceil_really_has_the_artefact() -> None:
    """Documents why safe_ceil exists: plain ceil over-counts these exact-integer products."""
    assert math.ceil(0.1 * 3 * 10) == 4  # 3.0000000000000004
    assert safe_ceil(0.1 * 3 * 10) == 3


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (10 * 9, 90),  # the BP example: must be 90, not 91
        (10.0 * 9, 90),
        (0.1 * 3 * 10, 3),
        (2.0000000001, 2),  # 1e-10 is below the 9 dp rounding step
        (2.4, 3),
        (2.0, 2),
        (0.0, 0),
        (0.0000000004, 0),  # below the 9 dp rounding step: treated as zero
        (-0.5, 0),
        (-1.0, -1),
        (-1.2, -1),
        (1e6 + 0.1, 1_000_001),
    ],
)
def test_safe_ceil_values(value: float, expected: int) -> None:
    assert safe_ceil(value) == expected
    assert isinstance(safe_ceil(value), int)


def test_safe_ceil_exact_9dp_threshold() -> None:
    assert safe_ceil(5.000000001) == 6  # 1e-9 survives round(x, 9)
    assert safe_ceil(5.0000000004) == 5  # 4e-10 rounds away


def test_safe_ceil_array_matches_scalar_and_is_integer() -> None:
    values = np.array([90.0, 0.1 * 3 * 10, 2.4, 0.0, -1.2, 7.000000001, 7.0000000004])
    out = safe_ceil_array(values)
    assert out.dtype == np.int64
    assert out.tolist() == [safe_ceil(float(v)) for v in values]
    assert out.tolist() == [90, 3, 3, 0, -1, 8, 7]


def test_safe_ceil_array_handles_lists_and_empty() -> None:
    assert safe_ceil_array([1.2, 2.0]).tolist() == [2, 2]
    assert safe_ceil_array(np.array([], dtype=float)).tolist() == []


def test_safe_ceil_array_property_grid() -> None:
    """ceil(a/b * b) == a for integer a, b: float noise never pushes the result up (seeded grid)."""
    rng = np.random.default_rng(7)
    numerator = rng.integers(1, 5000, size=3000)
    denominator = rng.integers(1, 120, size=3000)
    noisy = (numerator / denominator) * denominator  # often a hair above or below `numerator`
    assert (safe_ceil_array(noisy) == numerator).all()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("0.005"), "0.01"),  # ROUND_HALF_UP: .005 -> .01 (banker's would give 0.00)
        (Decimal("0.015"), "0.02"),
        (Decimal("0.025"), "0.03"),
        (Decimal("2.675"), "2.68"),
        (Decimal("19688"), "19688.00"),
        (Decimal("1234.5649"), "1234.56"),
        (5, "5.00"),
        ("7.1", "7.10"),
    ],
)
def test_money_is_two_dp_round_half_up(value: Decimal | int | str, expected: str) -> None:
    assert str(money(value)) == expected
    assert isinstance(money(value), Decimal)
