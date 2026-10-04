"""Adapter mapujący odpowiedzi Mapboxa na kandydackie trasy aplikacji."""

from app.integrations.mapbox_directions_client import MapboxDirectionsClient
from app.schemas.route import Coordinate
from app.scoring.route_models import CandidateRoute


class MapboxRouteProvider:
    """Dostarcza kandydackie trasy piesze z Mapbox Directions API."""

    def __init__(self, client: MapboxDirectionsClient) -> None:
        """Przechowuje klienta odpowiedzialnego za komunikację HTTP."""

        self.client = client

    def get_candidate_routes(
        self,
        start: Coordinate,
        end: Coordinate,
    ) -> tuple[CandidateRoute, ...]:
        """Pobiera i mapuje trasę główną oraz dostępne alternatywy."""

        return tuple(
            CandidateRoute(
                route_id=f"mapbox-{route.route_index}",
                geometry=route.geometry,
                duration_s=route.duration_s,
                distance_m=route.distance_m,
                segments=(),
            )
            for route in self.client.get_walking_routes(start, end, alternatives=True)
        )
