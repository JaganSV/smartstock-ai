"""NFR-01: every read endpoint of P3-02a/b answers in under 500 ms on the seeded database.

Per endpoint: one warm-up request, then the median of 5 timed requests (in-process TestClient,
so the time covers routing, auth, database reads, analytics roll-up and serialisation). The
medians are printed; run with ``-s`` to see them. NFR-03: ``POST /analytics/recalculate`` (#16)
finishes in under 5 s (median of 3).
"""

import statistics
import time

import pytest

from tests.integration.auth_helpers import Api
from tests.integration.read_helpers import product_id, warehouse_id

pytestmark = pytest.mark.integration

LIMIT_MS = 500.0
RECALC_LIMIT_MS = 5000.0
WARM_RUNS = 5
RECALC_RUNS = 3


def _endpoints(api: Api) -> list[str]:
    pid = product_id(api.engine, "SKU-004")
    mum = warehouse_id(api.engine, "WH-MUM")
    return [
        "/api/v1/reference/categories",
        "/api/v1/reference/warehouses",
        "/api/v1/reference/suppliers",
        "/api/v1/products?sort=risk&page_size=100",
        f"/api/v1/products/{pid}",
        f"/api/v1/products/{pid}/sales?days=90",
        "/api/v1/dashboard/summary",
        "/api/v1/dashboard/sales-trend?days=90",
        "/api/v1/dashboard/risk-distribution",
        "/api/v1/analytics/metrics?page_size=100",
        f"/api/v1/analytics/metrics/{pid}/explain?warehouse_id={mum}",
        "/api/v1/analytics/snapshots?page_size=100",
        "/api/v1/risk/stockout?page_size=100",
        f"/api/v1/risk/{pid}?warehouse_id={mum}",
        "/api/v1/risk/slow-moving?page_size=100",
    ]


def test_every_endpoint_median_is_under_500_ms(read_api: Api) -> None:
    headers = read_api.headers("analyst")
    medians: dict[str, float] = {}
    for path in _endpoints(read_api):
        assert read_api.client.get(path, headers=headers).status_code == 200, path  # warm-up
        timings = []
        for _ in range(WARM_RUNS):
            started = time.perf_counter()
            response = read_api.client.get(path, headers=headers)
            timings.append((time.perf_counter() - started) * 1000)
            assert response.status_code == 200, path
        medians[path] = statistics.median(timings)
    print("\nNFR-01 medians (5 warm requests each):")
    for path, median in medians.items():
        print(f"  {median:7.1f} ms  GET {path}")
    slow = {path: round(ms, 1) for path, ms in medians.items() if ms >= LIMIT_MS}
    assert slow == {}, f"endpoints at or over {LIMIT_MS} ms: {slow}"


def test_recalculate_median_is_under_5_s(read_api: Api) -> None:
    headers = read_api.headers("admin")
    timings = []
    for _ in range(RECALC_RUNS):
        started = time.perf_counter()
        response = read_api.client.post("/api/v1/analytics/recalculate", headers=headers)
        timings.append((time.perf_counter() - started) * 1000)
        assert response.status_code == 201
    median = statistics.median(timings)
    print(f"\nNFR-03 median ({RECALC_RUNS} runs): {median:7.1f} ms  POST /analytics/recalculate")
    assert median < RECALC_LIMIT_MS
