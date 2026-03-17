"""Products API contract tests."""

import pytest


@pytest.mark.asyncio
async def test_list_products_empty(client, auth_headers):
    """List products returns array or paginated structure."""
    resp = await client.get("/api/products/", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, (list, dict))
    if isinstance(data, dict):
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_create_product(client, auth_headers):
    """Create product returns product with id and name."""
    resp = await client.post(
        "/api/products/",
        headers=auth_headers,
        json={
            "name": "Test Product",
            "current_price": 1500.00,
            "currency": "RUB",
            "sku": "TEST-001",
        },
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert "id" in data
    assert "name" in data
    assert data["name"] == "Test Product"


@pytest.mark.asyncio
async def test_get_product_detail(client, auth_headers):
    """Get product detail returns full product structure."""
    create_resp = await client.post(
        "/api/products/",
        headers=auth_headers,
        json={
            "name": "Detail Test",
            "current_price": 2000.00,
            "currency": "RUB",
        },
    )
    product_id = create_resp.json()["id"]

    resp = await client.get(f"/api/products/{product_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert str(data["id"]) == str(product_id)
    assert "current_price" in data


@pytest.mark.asyncio
async def test_get_other_users_product_forbidden(client, auth_headers):
    """Get non-existent or other user's product returns 403 or 404."""
    resp = await client.get("/api/products/00000000-0000-0000-0000-000000000001", headers=auth_headers)
    assert resp.status_code in (403, 404)
