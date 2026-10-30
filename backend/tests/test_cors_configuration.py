from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.main import configure_cors


def create_cors_client(monkeypatch, frontend_origin, *, production=False):
    monkeypatch.setenv("ASSETAI_FRONTEND_ORIGIN", frontend_origin)
    monkeypatch.setenv("RENDER", "true" if production else "false")
    monkeypatch.setenv("ASSETAI_ENV", "production" if production else "development")
    test_app = FastAPI()
    configure_cors(test_app)

    @test_app.get("/")
    def home():
        return {"ok": True}

    return TestClient(test_app)


def test_configured_production_frontend_origin_is_allowed(monkeypatch):
    origin = "https://sprite-generator.vercel.app"
    client = create_cors_client(monkeypatch, origin, production=True)

    response = client.options(
        "/",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_localhost_development_origins_are_allowed_outside_production(
    monkeypatch, origin
):
    client = create_cors_client(monkeypatch, "https://sprite-generator.vercel.app")

    response = client.get("/", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_localhost_development_origins_are_rejected_in_production(
    monkeypatch, origin
):
    client = create_cors_client(
        monkeypatch, "https://sprite-generator.vercel.app", production=True
    )

    response = client.get("/", headers={"Origin": origin})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_unconfigured_origin_is_not_allowed(monkeypatch):
    client = create_cors_client(monkeypatch, "https://sprite-generator.vercel.app")

    response = client.get("/", headers={"Origin": "https://untrusted.example"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_wildcard_frontend_origin_is_rejected(monkeypatch):
    monkeypatch.setenv("ASSETAI_FRONTEND_ORIGIN", "*")

    with pytest.raises(ValueError, match="single HTTP\\(S\\) origin"):
        configure_cors(FastAPI())
