"""Dashboard API contract tests. KPI, anomalies, aggregate-trend. Market overview uses /api/markets/overview."""

import pytest


@pytest.mark.asyncio
async def test_dashboard_kpi_shape(client, auth_headers):
    """Dashboard KPI returns expected fields for KPIOverview."""
    resp = await client.get("/api/dashboard/kpi", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    expected_fields = [
        "total_products",
        "total_competitors",
        "avg_price_change_24h",
        "active_alerts_count",
        "products_at_risk",
    ]
    for field in expected_fields:
        assert field in data, f"Missing field: {field}"
    assert isinstance(data["total_products"], (int, float))


@pytest.mark.asyncio
async def test_dashboard_anomalies_shape(client, auth_headers):
    """Dashboard anomalies returns list with expected item shape."""
    resp = await client.get("/api/dashboard/anomalies?limit=5", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if data:
        anomaly = data[0]
        assert "product_name" in anomaly
        assert "change_percent" in anomaly
        assert "severity" in anomaly


@pytest.mark.asyncio
async def test_dashboard_aggregate_trend_shape(client, auth_headers):
    """Dashboard aggregate-trend returns chart data structure."""
    resp = await client.get(
        "/api/dashboard/aggregate-trend?period=30&forecast=7",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "labels" in data
    assert "my_products_avg" in data
    assert "competitors_avg" in data
    assert "forecast" in data
    assert isinstance(data["labels"], list)
