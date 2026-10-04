"""Interfejs źródła tras niezależny od konkretnego dostawcy map."""

from collections.abc import Protocol

from app.schemas.route import Coordinate
from app.scoring.route_models import CandidateRoute


class RouteProvider(Protocol):
    """Kontrakt dla Mapboxa, mocka lub lokalnego silnika routingu."""

    def get_candidate_routes(
        self,
        start: Coordinate,
        end: Coordinate,
    ) -> tuple[CandidateRoute, ...]:
        """Zwraca dostępne warianty trasy pomiędzy punktami."""

        ...
