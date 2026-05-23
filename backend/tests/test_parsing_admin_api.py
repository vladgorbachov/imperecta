"""Integration tests for parsing admin API endpoints."""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import delete

from app.database import async_session_maker
from app.models.app_tables import ScrapeJob
from app.modules.admin.parsing_admin import ParsingAdminService


@pytest.mark.asyncio
async def test_parsing_admin_endpoints_forbidden_for_regular_user(client, auth_headers):
    """Non-superuser cannot access parsing admin endpoints."""
    paths = [
        ("GET", "/api/admin/parsing/test-marketplaces"),
        ("POST", "/api/admin/parsing/run-full-test"),
        ("GET", "/api/admin/parsing/test-runs"),
        ("GET", "/api/admin/parsing/job-status/00000000-0000-0000-0000-000000000001"),
        ("GET", "/api/admin/parsing/users-detailed"),
        ("GET", "/api/admin/parsing/marketplaces-detailed"),
        ("GET", "/api/admin/parsing/job-live-feed/00000000-0000-0000-0000-000000000001"),
        ("GET", "/api/admin/parsing/active-job"),
    ]
    for method, path in paths:
        if method == "GET":
            resp = await client.get(path, headers=auth_headers)
        else:
            resp = await client.post(path, headers=auth_headers)
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_parsing_admin_get_marketplaces_contract(client, superuser_headers):
    """Superuser can fetch parsing marketplaces in frontend contract shape."""
    list_resp = await client.get("/api/admin/parsing/test-marketplaces", headers=superuser_headers)
    assert list_resp.status_code == 200
    rows = list_resp.json()
    assert isinstance(rows, list)
    if rows:
        expected_keys = {
            "name",
            "url",
            "products_in_pool",
            "last_successful_scrape",
            "success_rate",
            "last_run",
            "status",
        }
        assert set(rows[0].keys()) == expected_keys


@pytest.mark.asyncio
async def test_parsing_admin_get_users_and_marketplaces_detailed(client, superuser_headers):
    """Superuser can fetch detailed users/marketplaces lists for admin tabs."""
    users_resp = await client.get("/api/admin/parsing/users-detailed", headers=superuser_headers)
    assert users_resp.status_code == 200
    users_payload = users_resp.json()
    assert isinstance(users_payload, list)

    marketplaces_resp = await client.get(
        "/api/admin/parsing/marketplaces-detailed",
        headers=superuser_headers,
    )
    assert marketplaces_resp.status_code == 200
    marketplaces_payload = marketplaces_resp.json()
    assert isinstance(marketplaces_payload, list)


@pytest.mark.asyncio
async def test_parsing_admin_run_full_test_and_poll_status(client, superuser_headers, monkeypatch):
    """Run endpoint returns job identifiers and status endpoint supports polling contract."""

    class DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(ParsingAdminService, "TEST_PIPELINE_JOB_TYPE", "manual")
    monkeypatch.setattr(
        "app.modules.admin.api_parsing.run_full_pipeline_test.delay",
        lambda _job_id: DummyAsyncResult(),
    )

    run_resp = await client.post("/api/admin/parsing/run-full-test", headers=superuser_headers)
    assert run_resp.status_code == 200
    created = run_resp.json()
    assert "job_id" in created
    assert "started_at" in created
    job_id = created["job_id"]

    status_resp = await client.get(
        f"/api/admin/parsing/job-status/{job_id}",
        headers=superuser_headers,
    )
    assert status_resp.status_code == 200
    status_payload = status_resp.json()
    assert status_payload["job_id"] == job_id
    assert status_payload["status"] in {"running", "completed", "failed"}
    assert "current_stage" in status_payload

    async with async_session_maker() as session:
        await session.execute(delete(ScrapeJob).where(ScrapeJob.id == UUID(job_id)))
        await session.commit()


@pytest.mark.asyncio
async def test_parsing_admin_run_full_test_auto_repairs_constraint(client, superuser_headers):
    """run-full-test creates a job even when DB initially has stale job_type constraint."""
    resp = await client.post("/api/admin/parsing/run-full-test", headers=superuser_headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("job_id")
    assert payload.get("started_at")


@pytest.mark.asyncio
async def test_parsing_admin_test_runs_with_limit_and_contract(client, superuser_headers, monkeypatch):
    """History endpoint returns expected fields and obeys limit query."""
    class DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(ParsingAdminService, "TEST_PIPELINE_JOB_TYPE", "manual")
    monkeypatch.setattr(
        "app.modules.admin.api_parsing.run_full_pipeline_test.delay",
        lambda _job_id: DummyAsyncResult(),
    )
    run_resp = await client.post("/api/admin/parsing/run-full-test", headers=superuser_headers)
    assert run_resp.status_code == 200
    job_id = run_resp.json()["job_id"]

    list_resp = await client.get(
        "/api/admin/parsing/test-runs",
        headers=superuser_headers,
        params={"limit": 1},
    )
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert isinstance(payload, list)
    assert len(payload) <= 1
    if payload:
        expected_keys = {
            "job_id",
            "started_at",
            "completed_at",
            "duration_seconds",
            "listings_created",
            "prices_saved",
            "errors_count",
            "status",
        }
        assert set(payload[0].keys()) == expected_keys

    async with async_session_maker() as session:
        await session.execute(delete(ScrapeJob).where(ScrapeJob.id == UUID(job_id)))
        await session.commit()


@pytest.mark.asyncio
async def test_parsing_admin_job_status_validation(client, superuser_headers):
    """Job status endpoint validates UUID path parameters."""
    resp = await client.get("/api/admin/parsing/job-status/not-a-uuid", headers=superuser_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_parsing_admin_test_runs_limit_validation(client, superuser_headers):
    """History endpoint validates limit bounds."""
    resp = await client.get(
        "/api/admin/parsing/test-runs",
        headers=superuser_headers,
        params={"limit": 0},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_parsing_admin_job_status_not_found(client, superuser_headers):
    """Unknown job id returns 404 for polling endpoint."""
    resp = await client.get(
        "/api/admin/parsing/job-status/00000000-0000-0000-0000-000000000001",
        headers=superuser_headers,
    )
    assert resp.status_code == 404
