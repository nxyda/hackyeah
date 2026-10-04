"""HTTP contract tests for safe-place endpoints."""

from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.database.session import get_db
from app.main import app
from app.api.v1 import safe_places_router
from app.schemas.safe_place import NearbySafePlaceResponse, SafePlaceResponse


def _client(monkeypatch, service) -> TestClient:
    monkeypatch.setattr(safe_places_router, "_service", lambda session: service)
    app.dependency_overrides[get_db] = lambda: object()
    return TestClient(app)


def test_nearby_safe_places_uses_validated_query_and_returns_dtos(monkeypatch) -> None:
    class StubService:
        async def get_nearby(self, *, longitude, latitude, radius_m):
            assert (longitude, latitude, radius_m) == (19.945, 50.0647, 500)
            return [
                NearbySafePlaceResponse(
                    id=17,
                    category="police",
                    name="Central station",
                    opening_hours_raw=None,
                    is_24_7=True,
                    latitude=50.0647,
                    longitude=19.945,
                    distance_m=125.5,
                )
            ]

    try:
        response = _client(monkeypatch, StubService()).get(
            "/v1/safe-places/nearby",
            params={"lat": 50.0647, "lon": 19.945, "radius_m": 500},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["distance_m"] == 125.5
    assert response.json()[0]["latitude"] == 50.0647


def test_nearby_safe_places_rejects_invalid_coordinates_and_radius(monkeypatch) -> None:
    try:
        client = _client(monkeypatch, SimpleNamespace())
        invalid_latitude = client.get(
            "/v1/safe-places/nearby",
            params={"lat": 91, "lon": 0},
        )
        invalid_radius = client.get(
            "/v1/safe-places/nearby",
            params={"lat": 0, "lon": 0, "radius_m": 50_001},
        )
    finally:
        app.dependency_overrides.clear()

    assert invalid_latitude.status_code == 422
    assert invalid_radius.status_code == 422


def test_safe_place_not_found_returns_404(monkeypatch) -> None:
    class StubService:
        async def get_by_id(self, safe_place_id):
            return None

    try:
        response = _client(monkeypatch, StubService()).get("/v1/safe-places/404")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "Safe place not found"


def test_safe_place_detail_returns_dto_not_database_model(monkeypatch) -> None:
    class StubService:
        async def get_by_id(self, safe_place_id):
            return SafePlaceResponse(
                id=safe_place_id,
                category="police",
                name="Central station",
                opening_hours_raw=None,
                is_24_7=True,
                latitude=50.0647,
                longitude=19.945,
            )

    try:
        response = _client(monkeypatch, StubService()).get("/v1/safe-places/17")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["latitude"] == 50.0647
    assert "geom" not in response.json()


def test_database_failures_return_generic_server_error_and_are_logged(monkeypatch) -> None:
    class StubService:
        async def get_by_id(self, safe_place_id):
            raise SQLAlchemyError("private database detail")

    try:
        response = _client(monkeypatch, StubService()).get("/v1/safe-places/17")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json()["detail"] == "Unable to retrieve safe place"
    assert "private database detail" not in response.text
