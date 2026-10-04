"""Klient Mapbox Directions API dla tras pieszych."""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.schemas.route import Coordinate

logger = logging.getLogger(__name__)


class MapboxDirectionsError(RuntimeError):
    """Błąd komunikacji lub niepoprawna odpowiedź Mapbox Directions API."""


@dataclass(frozen=True)
class MapboxRoute:
    """Surowe dane trasy potrzebne aplikacji."""

    route_index: int
    geometry: tuple[tuple[float, float], ...]
    duration_s: float
    distance_m: float


class MapboxDirectionsClient:
    """Wykonuje żądania Directions API bez znajomości logiki scoringu."""

    base_url = "https://api.mapbox.com/directions/v5/mapbox"

    def __init__(
        self,
        access_token: str,
        http_client: httpx.Client | None = None,
        timeout_s: float = 10.0,
    ) -> None:
        """Tworzy klienta z tokenem Mapbox i opcjonalnym klientem HTTP."""

        if not access_token.strip():
            raise ValueError("Mapbox access token must not be empty")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self._access_token = access_token
        self._http_client = http_client or httpx.Client(timeout=timeout_s)
        self._owns_http_client = http_client is None

    def close(self) -> None:
        """Zamyka klienta HTTP, jeśli został utworzony przez ten obiekt."""

        if self._owns_http_client:
            self._http_client.close()

    def get_walking_routes(
        self,
        start: Coordinate,
        end: Coordinate,
        alternatives: bool = True,
    ) -> tuple[MapboxRoute, ...]:
        """Pobiera trasę pieszą oraz dostępne alternatywy z Mapboxa."""

        self._validate_coordinate(start)
        self._validate_coordinate(end)
        coordinates = f"{start.lon},{start.lat};{end.lon},{end.lat}"
        try:
            response = self._http_client.get(
                f"{self.base_url}/walking/{coordinates}",
                params={
                    "access_token": self._access_token,
                    "alternatives": str(alternatives).lower(),
                    "geometries": "geojson",
                    "overview": "full",
                    "steps": "false",
                },
            )
        except httpx.RequestError as exc:
            logger.warning(
                "Mapbox Directions request failed error=%s",
                type(exc).__name__,
            )
            raise MapboxDirectionsError("Mapbox Directions request failed") from exc
        if response.is_error:
            logger.warning(
                "Mapbox Directions returned HTTP status=%d",
                response.status_code,
            )
            raise MapboxDirectionsError(
                f"Mapbox Directions request failed with HTTP {response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError:
            logger.warning("Mapbox Directions returned invalid JSON")
            raise MapboxDirectionsError(
                "Mapbox Directions returned invalid JSON"
            ) from None
        try:
            routes = self._parse_routes(payload)
        except MapboxDirectionsError as exc:
            logger.warning(
                "Mapbox Directions returned an invalid payload error=%s",
                type(exc).__name__,
            )
            raise
        logger.debug("Mapbox Directions returned route_count=%d", len(routes))
        return routes

    @staticmethod
    def _validate_coordinate(coordinate: Coordinate) -> None:
        """Sprawdza zakres współrzędnych przed wysłaniem żądania."""

        if not -90 <= coordinate.lat <= 90:
            raise ValueError("latitude must be between -90 and 90")
        if not -180 <= coordinate.lon <= 180:
            raise ValueError("longitude must be between -180 and 180")

    @classmethod
    def _parse_routes(cls, payload: Any) -> tuple[MapboxRoute, ...]:
        """Waliduje minimalny kształt odpowiedzi Mapboxa i mapuje trasy."""

        if not isinstance(payload, dict):
            raise MapboxDirectionsError("Mapbox response must be a JSON object")
        if payload.get("code") != "Ok":
            raise MapboxDirectionsError(f"Mapbox returned error code: {payload.get('code')!r}")
        raw_routes = payload.get("routes")
        if not isinstance(raw_routes, list) or not raw_routes:
            raise MapboxDirectionsError("Mapbox response contains no routes")

        routes: list[MapboxRoute] = []
        for index, raw_route in enumerate(raw_routes):
            if not isinstance(raw_route, dict):
                raise MapboxDirectionsError(f"Mapbox route {index} must be an object")
            geometry = raw_route.get("geometry")
            coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
            if geometry.get("type") != "LineString" if isinstance(geometry, dict) else True:
                raise MapboxDirectionsError(f"Mapbox route {index} has invalid geometry")
            if not cls._valid_coordinates(coordinates):
                raise MapboxDirectionsError(f"Mapbox route {index} has invalid coordinates")
            duration_s = raw_route.get("duration")
            distance_m = raw_route.get("distance")
            if not isinstance(duration_s, (int, float)) or not isinstance(distance_m, (int, float)):
                raise MapboxDirectionsError(f"Mapbox route {index} has invalid metrics")
            if duration_s < 0 or distance_m < 0:
                raise MapboxDirectionsError(f"Mapbox route {index} has negative metrics")
            routes.append(
                MapboxRoute(
                    route_index=index,
                    geometry=tuple((float(lon), float(lat)) for lon, lat in coordinates),
                    duration_s=float(duration_s),
                    distance_m=float(distance_m),
                )
            )
        return tuple(routes)

    @staticmethod
    def _valid_coordinates(value: Any) -> bool:
        """Sprawdza, czy geometria zawiera poprawne pary longitude, latitude."""

        return (
            isinstance(value, list)
            and len(value) >= 2
            and all(
                isinstance(point, list)
                and len(point) >= 2
                and isinstance(point[0], (int, float))
                and isinstance(point[1], (int, float))
                and -180 <= point[0] <= 180
                and -90 <= point[1] <= 90
                for point in value
            )
        )
