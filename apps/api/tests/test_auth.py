import httpx
import pytest

from src.main import app


@pytest.fixture
async def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(client: httpx.AsyncClient, username: str, password: str) -> httpx.Response:
    return await client.post(
        "/auth/login",
        data={"username": username, "password": password},
    )


@pytest.mark.asyncio
async def test_login_returns_access_token(client: httpx.AsyncClient) -> None:
    response = await _login(client, "operator", "operator123")
    assert response.status_code == 200
    body = response.json()
    assert body["tokenType"] == "bearer"
    assert isinstance(body["accessToken"], str) and body["accessToken"]


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(client: httpx.AsyncClient) -> None:
    response = await _login(client, "operator", "wrong-password")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_rejects_unknown_user(client: httpx.AsyncClient) -> None:
    response = await _login(client, "ghost", "whatever")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_bearer_token(client: httpx.AsyncClient) -> None:
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(client: httpx.AsyncClient) -> None:
    login_response = await _login(client, "admin", "admin123")
    token = login_response.json()["accessToken"]

    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "username": "admin",
        "email": "admin@retail.example",
        "role": "admin",
    }
