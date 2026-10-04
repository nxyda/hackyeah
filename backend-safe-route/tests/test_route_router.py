import asyncio
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1.route_router import create_route
from app.integrations.mapbox_directions_client import MapboxDirectionsError
from app.schemas.route import RouteRequest
from app.services.route_service import RouteService, RouteUnavailableError


@pytest.mark.parametrize(
    "error",
    [
        MapboxDirectionsError("provider error"),
        RouteUnavailableError("no route"),
    ],
)
def test_route_provider_failures_return_service_unavailable(monkeypatch, error) -> None:
    async def fail_calculate_route(self, request):
        raise error

    monkeypatch.setattr(RouteService, "calculate_route", fail_calculate_route)
    request = RouteRequest(
        start={"lat": 50.0614, "lon": 19.9366},
        end={"lat": 50.0543, "lon": 19.9353},
        departure_time=datetime.now(timezone.utc),
        safety_weight=0.5,
        profile="walking",
    )

    with pytest.raises(HTTPException) as raised:
        asyncio.run(create_route(request, object()))

    assert raised.value.status_code == 503
    assert raised.value.detail == "Route planning is temporarily unavailable"


def test_route_validation_errors_return_bad_request(monkeypatch) -> None:
    async def fail_calculate_route(self, request):
        raise ValueError("unsupported departure time")

    monkeypatch.setattr(RouteService, "calculate_route", fail_calculate_route)
    request = RouteRequest(
        start={"lat": 50.0614, "lon": 19.9366},
        end={"lat": 50.0543, "lon": 19.9353},
        departure_time=datetime.now(timezone.utc),
        safety_weight=0.5,
        profile="walking",
    )

    with pytest.raises(HTTPException) as raised:
        asyncio.run(create_route(request, object()))

    assert raised.value.status_code == 400
    assert raised.value.detail == "unsupported departure time"


def test_route_request_and_session_are_forwarded_to_service(monkeypatch) -> None:
    request = RouteRequest(
        start={"lat": 50.0614, "lon": 19.9366},
        end={"lat": 50.0543, "lon": 19.9353},
        departure_time=datetime.now(timezone.utc),
        safety_weight=0.5,
        profile="walking",
    )
    session = object()
    result = object()
    calls = []

    async def calculate_route(self, received_request):
        calls.append((self.session, received_request))
        return result

    monkeypatch.setattr(RouteService, "calculate_route", calculate_route)

    response = asyncio.run(create_route(request, session))

    assert response is result
    assert calls == [(session, request)]


def test_route_endpoint_is_registered_under_v1() -> None:
    from app.api.v1.router import v1_router
    from app.main import app

    with TestClient(app) as client:
        paths = set(client.get("/openapi.json").json()["paths"])
    registered_paths = [
        route.path
        for included_router in v1_router.routes
        for route in included_router.original_router.routes
        if hasattr(route, "path")
    ]

    assert "/v1/route" in paths
    assert "/v1/cameras/nearby" in paths
    assert "/v1/street-lamps/nearby" in paths
    assert "/v1/crime-events/nearby" in paths
    assert registered_paths.count("/cameras/nearby") == 1
    assert registered_paths.count("/crime-events/nearby") == 1
