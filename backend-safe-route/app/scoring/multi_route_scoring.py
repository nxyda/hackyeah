"""Ocenianie wielu tras i wybór wariantów dla użytkownika."""

from collections.abc import Sequence
from typing import Literal

from app.scoring.route_models import CandidateRoute, ScoredCandidateRoute
from app.scoring.route_scoring import calculate_route_score
from app.scoring.scoring_models import NormalizationConfig, ScoringWeights


def normalize_duration(duration_s: float, minimum_s: float, maximum_s: float) -> float:
    """Normalizuje czas trasy do wyniku 0–1, gdzie krócej oznacza lepiej."""

    if duration_s < 0 or minimum_s < 0 or maximum_s < 0:
        raise ValueError("durations must be non-negative")
    if minimum_s > maximum_s:
        raise ValueError("minimum_s must not exceed maximum_s")
    if not minimum_s <= duration_s <= maximum_s:
        raise ValueError("duration_s must be within the provided range")
    if minimum_s == maximum_s:
        return 1.0
    return 1.0 - (duration_s - minimum_s) / (maximum_s - minimum_s)


def score_candidate_routes(
    routes: Sequence[CandidateRoute],
    weights: ScoringWeights,
    normalization: NormalizationConfig,
    safety_weight: float,
    period: Literal["day", "night"] = "night",
) -> tuple[ScoredCandidateRoute, ...]:
    """Ocenia wszystkie kandydackie trasy wspólną konfiguracją scoringu."""

    if not routes:
        raise ValueError("at least one candidate route is required")
    if not 0 <= safety_weight <= 1:
        raise ValueError("safety_weight must be between 0 and 1")
    route_ids = [route.route_id for route in routes]
    if len(route_ids) != len(set(route_ids)):
        raise ValueError("candidate route IDs must be unique")

    minimum_duration = min(route.duration_s for route in routes)
    maximum_duration = max(route.duration_s for route in routes)
    scored_routes = []
    for route in routes:
        score = calculate_route_score(route.segments, weights, normalization, period)
        duration_score = normalize_duration(
            route.duration_s, minimum_duration, maximum_duration
        )
        combined_score = (
            safety_weight * score.score
            + (1 - safety_weight) * duration_score * 100
        )
        scored_routes.append(
            ScoredCandidateRoute(
                candidate=route,
                score=score,
                duration_score=duration_score,
                combined_score=combined_score,
            )
        )
    return tuple(scored_routes)


def select_fastest_route(routes: Sequence[ScoredCandidateRoute]) -> ScoredCandidateRoute:
    """Wybiera trasę o najkrótszym czasie przejścia."""

    if not routes:
        raise ValueError("at least one scored route is required")
    return min(routes, key=lambda route: (route.candidate.duration_s, route.candidate.route_id))


def select_safest_route(routes: Sequence[ScoredCandidateRoute]) -> ScoredCandidateRoute:
    """Wybiera trasę z najwyższym wynikiem bezpieczeństwa."""

    if not routes:
        raise ValueError("at least one scored route is required")
    return max(routes, key=lambda route: (route.safety_score, route.candidate.route_id))


def select_recommended_route(routes: Sequence[ScoredCandidateRoute]) -> ScoredCandidateRoute:
    """Wybiera wariant najlepiej łączący bezpieczeństwo i czas."""

    if not routes:
        raise ValueError("at least one scored route is required")
    return max(routes, key=lambda route: (route.combined_score, route.candidate.route_id))
