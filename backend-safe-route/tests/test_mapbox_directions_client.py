"""Testy klienta Mapboxa z kontrolowanym transportem HTTP."""

import httpx
import pytest

from app.integrations.mapbox_directions_client import (
    MapboxDirectionsClient,
    MapboxDirectionsError,
)
from app.route_providers.mapbox_route_provider import MapboxRouteProvider
from app.schemas.route import Coordinate


def mapbox_payload() -> dict:
    """Zwraca minimalną poprawną odpowiedź Directions API z dwiema trasami."""

    return {
        "code": "Ok",
        "routes": [
            {
                "distance": 1000,
                "duration": 600,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[21.0, 52.0], [21.01, 52.01]],
                },
            },
            {
                "distance": 1300,
                "duration": 780,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[21.0, 52.0], [21.02, 52.02]],
                },
            },
        ],
    }


def test_client_requests_walking_alternatives() -> None:
    """Klient wysyła właściwy endpoint i parametry Mapboxa."""

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=mapbox_payload())

    client = MapboxDirectionsClient("test-token", httpx.Client(transport=httpx.MockTransport(handler)))
    routes = client.get_walking_routes(Coordinate(lat=52.0, lon=21.0), Coordinate(lat=52.01, lon=21.01))

    assert len(routes) == 2
    assert routes[0].duration_s == 600
    assert routes[0].geometry == ((21.0, 52.0), (21.01, 52.01))
    assert "/walking/21.0,52.0;21.01,52.01" in str(requests[0].url)
    assert requests[0].url.params["alternatives"] == "true"
    assert requests[0].url.params["geometries"] == "geojson"


def test_provider_maps_routes_to_candidate_routes() -> None:
    """Provider tworzy modele używane przez scoring."""

    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=mapbox_payload()))
    client = MapboxDirectionsClient("test-token", httpx.Client(transport=transport))
    routes = MapboxRouteProvider(client).get_candidate_routes(
        Coordinate(lat=52.0, lon=21.0),
        Coordinate(lat=52.01, lon=21.01),
    )

    assert [route.route_id for route in routes] == ["mapbox-0", "mapbox-1"]
    assert routes[0].segments == ()
    assert routes[1].distance_m == 1300


@pytest.mark.parametrize(
    "payload",
    (
        {"code": "NoRoute", "routes": []},
        {"code": "Ok", "routes": []},
        {"code": "Ok", "routes": [{"duration": 1, "distance": 1}]},
    ),
)
def test_invalid_mapbox_payload_is_rejected(payload: dict) -> None:
    """Niepełne odpowiedzi Mapboxa kończą się jawnym błędem."""

    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    client = MapboxDirectionsClient("test-token", httpx.Client(transport=transport))

    with pytest.raises(MapboxDirectionsError):
        client.get_walking_routes(Coordinate(lat=52.0, lon=21.0), Coordinate(lat=52.01, lon=21.01))


def test_http_error_is_rejected() -> None:
    """Błąd HTTP Mapboxa nie jest zamieniany na pustą odpowiedź."""

    transport = httpx.MockTransport(lambda request: httpx.Response(401, json={"message": "unauthorized"}))
    client = MapboxDirectionsClient("test-token", httpx.Client(transport=transport))

    with pytest.raises(MapboxDirectionsError, match="HTTP 401"):
        client.get_walking_routes(Coordinate(lat=52.0, lon=21.0), Coordinate(lat=52.01, lon=21.01))


def test_transport_error_is_reported_as_mapbox_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = MapboxDirectionsClient("test-token", httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(MapboxDirectionsError, match="request failed"):
        client.get_walking_routes(Coordinate(lat=52.0, lon=21.0), Coordinate(lat=52.01, lon=21.01))


def test_invalid_coordinates_are_rejected_before_http_call() -> None:
    """Niepoprawne współrzędne nie trafiają do Mapboxa."""

    client = MapboxDirectionsClient(
        "test-token",
        httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500))),
    )

    with pytest.raises(ValueError):
        client.get_walking_routes(Coordinate(lat=91, lon=21), Coordinate(lat=52, lon=21))
