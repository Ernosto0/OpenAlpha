import httpx
import pytest

from backend.app.main import create_app


@pytest.mark.anyio
async def test_health_endpoint() -> None:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "openalpha-api"
