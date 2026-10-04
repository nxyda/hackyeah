"""Modele kandydackich tras niezależne od Mapboxa i warstwy HTTP."""

from dataclasses import dataclass

from app.scoring.scoring_models import RouteScoreResult, SegmentSafetyInput


@dataclass(frozen=True)
class CandidateRoute:
    """Jedna trasa oczekująca na ocenę bezpieczeństwa."""

    route_id: str
    geometry: tuple[tuple[float, float], ...]
    duration_s: float
    distance_m: float
    segments: tuple[SegmentSafetyInput, ...]
    segment_geometries: tuple[tuple[tuple[float, float], ...], ...] = ()

    def __post_init__(self) -> None:
        """Sprawdza podstawowe parametry trasy przed scoringiem."""

        if not self.route_id:
            raise ValueError("route_id must not be empty")
        if self.duration_s < 0:
            raise ValueError("duration_s must be non-negative")
        if self.distance_m < 0:
            raise ValueError("distance_m must be non-negative")


@dataclass(frozen=True)
class ScoredCandidateRoute:
    """Kandydacka trasa z wynikiem bezpieczeństwa i preferencji użytkownika."""

    candidate: CandidateRoute
    score: RouteScoreResult
    duration_score: float
    combined_score: float

    @property
    def safety_score(self) -> float:
        """Zwraca wynik bezpieczeństwa w skali 0–100."""

        return self.score.score
