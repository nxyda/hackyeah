"""API-level route planning test using seeded PostGIS and mocked Mapbox."""

from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker


@pytest.mark.e2e
@pytest.mark.parametrize(
    "payload",
    [
        {
            "start": {"lat": 91, "lon": 0},
            "end": {"lat": 0, "lon": 0},
            "departure_time": "2026-10-04T12:00:00+00:00",
            "safety_weight": 0.5,
        },
        {
            "start": {"lat": 0, "lon": 0},
            "end": {"lat": 1, "lon": 1},
            "departure_time": "2026-10-04T12:00:00+00:00",
            "safety_weight": 1.01,
        },
        {
            "start": {"lat": 0, "lon": 0},
            "end": {"lat": 1, "lon": 1},
            "departure_time": "2026-10-04T12:00:00+00:00",
            "safety_weight": 0.5,
            "profile": "cycling",
        },
    ],
)
def test_route_api_rejects_invalid_input_before_calling_route_provider(
    payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.database.session import get_db
    from app.main import app
    from app.services import route_service

    def unexpected_provider_call(*args, **kwargs):
        raise AssertionError("Invalid route input must not call Mapbox")

    monkeypatch.setattr(
        route_service,
        "MapboxDirectionsClient",
        unexpected_provider_call,
    )
    app.dependency_overrides[get_db] = lambda: object()
    try:
        with TestClient(app) as client:
            result = client.post("/v1/route", json=payload)
        assert result.status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.e2e
def test_route_api_returns_sanitized_unavailable_response_for_empty_provider_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.database.session import get_db
    from app.main import app
    from app.services import route_service

    class NoRoutesProvider:
        def __init__(self, token: str) -> None:
            pass

        def get_walking_routes(self, start, end, alternatives):
            return ()

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        route_service,
        "MapboxDirectionsClient",
        NoRoutesProvider,
    )
    app.dependency_overrides[get_db] = lambda: object()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/route",
                json={
                    "start": {"lat": 50.0614, "lon": 19.9366},
                    "end": {"lat": 50.0543, "lon": 19.9353},
                    "departure_time": datetime.now(timezone.utc).isoformat(),
                    "safety_weight": 0.5,
                },
            )

        assert response.status_code == 503
        assert response.json()["detail"] == (
            "Route planning is temporarily unavailable"
        )
        assert "Mapbox" not in response.text
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.integration
@pytest.mark.e2e
def test_route_api_uses_seeded_spatial_data_without_real_mapbox_requests(
    run_with_postgis_test_database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario(sessions: async_sessionmaker) -> None:
        from app.database.session import get_db
        from app.integrations.mapbox_directions_client import MapboxDirectionsClient
        from app.main import app
        from app.services import route_service

        http_clients: list[httpx.Client] = []

        def mock_mapbox_client(token: str) -> MapboxDirectionsClient:
            http_client = httpx.Client(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200,
                        json={
                            "code": "Ok",
                            "routes": [
                                {
                                    "distance": 850,
                                    "duration": 720,
                                    "geometry": {
                                        "type": "LineString",
                                        "coordinates": [
                                            [19.9366, 50.0614],
                                            [19.9353, 50.0543],
                                        ],
                                    },
                                }
                            ],
                        },
                    )
                )
            )
            http_clients.append(http_client)
            return MapboxDirectionsClient("test-token", http_client)

        monkeypatch.setattr(
            route_service,
            "MapboxDirectionsClient",
            mock_mapbox_client,
        )

        async def test_database_session():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_db] = test_database_session
        try:
            payload = {
                "start": {"lat": 50.0614, "lon": 19.9366},
                "end": {"lat": 50.0543, "lon": 19.9353},
                "departure_time": datetime.now(timezone.utc).isoformat(),
                "safety_weight": 0.7,
                "profile": "walking",
            }
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post("/v1/route", json=payload)

            assert response.status_code == 200, response.text
            body = response.json()
            routes = [body["fastest"], body["safest"], *body["alternatives"]]
            assert any(route["distance_m"] == 850 for route in routes)
            assert body["safest"]["safety_score"] >= 0
            assert body["fastest"]["components"]["crime_exposure"] > 0
            assert body["fastest"]["components"]["reports_nearby"] > 0
            assert len({str(route["geometry"]) for route in routes}) >= 2
            assert body["meta"]["data_coverage"] == "segment_data"
            assert body["meta"]["mode"] == "mock"
        finally:
            app.dependency_overrides.pop(get_db, None)
            for http_client in http_clients:
                http_client.close()

    run_with_postgis_test_database(scenario)
