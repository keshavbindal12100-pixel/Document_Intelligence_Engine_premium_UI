import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Verify /health endpoint returns 200 OK and status healthy."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "project" in data


@pytest.mark.asyncio
async def test_readiness_check(client: AsyncClient):
    """Verify /ready endpoint checks database connectivity."""
    response = await client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "healthy"


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Verify root / endpoint returns welcome metadata."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "docs_url" in data


@pytest.mark.asyncio
async def test_guest_token_and_token_alias(client: AsyncClient):
    """Verify /api/v1/auth/guest-token and /api/v1/auth/token endpoints."""
    # 1. Guest token acquisition
    res_guest = await client.post("/api/v1/auth/guest-token")
    assert res_guest.status_code == 200
    guest_token = res_guest.json()
    assert "access_token" in guest_token
    assert guest_token["token_type"] == "bearer"

    # 2. Token alias endpoint
    res_token = await client.post(
        "/api/v1/auth/token",
        json={"email": "admin@example.com", "password": "Password12345!"},
    )
    assert res_token.status_code == 200
    assert "access_token" in res_token.json()


@pytest.mark.asyncio
async def test_dev_mode_unauthenticated_request_fallback(client: AsyncClient):
    """Verify that unauthenticated requests in dev/test mode gracefully fallback to default system user."""
    # Omit Authorization header completely
    res = await client.get("/api/v1/workflows")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # Supply an invalid/expired token
    res_invalid = await client.get(
        "/api/v1/workflows",
        headers={"Authorization": "Bearer invalid.expired.token"},
    )
    assert res_invalid.status_code == 200
    assert isinstance(res_invalid.json(), list)
