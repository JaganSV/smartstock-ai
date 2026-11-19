"""Numeric helpers: float-artefact-safe ceiling and 2 dp money rounding (BP 7.7).

``safe_ceil(x) = ceil(round(x, 9))`` so that products such as ``0.1 * 3 * 10``
(= 3.0000000000000004) give 3, not 4. Every ceiling in BP 7.2 goes through here.
"""

import math
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import numpy.typing as npt

SAFE_CEIL_DECIMALS = 9


def safe_ceil(value: float) -> int:
    """Ceiling of ``round(value, 9)`` as a Python int."""
    return math.ceil(round(value, SAFE_CEIL_DECIMALS))


def safe_ceil_array(values: npt.ArrayLike) -> npt.NDArray[np.int64]:
    """Vectorised ``safe_ceil``; returns int64 (NaN is not allowed)."""
    arr = np.asarray(values, dtype=np.float64)
    return np.ceil(np.round(arr, SAFE_CEIL_DECIMALS)).astype(np.int64)


def money(value: Decimal | int | str) -> Decimal:
    """Decimal with 2 dp, ROUND_HALF_UP (monetary values)."""
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
