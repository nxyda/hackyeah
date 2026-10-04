"""Niezależny moduł scoringu bezpieczeństwa tras."""

from app.scoring.route_scoring import (
    calculate_crime_exposure,
    calculate_route_score,
    calculate_segment_score,
)
from app.scoring.multi_route_scoring import (
    score_candidate_routes,
    select_fastest_route,
    select_recommended_route,
    select_safest_route,
)
from app.scoring.route_models import CandidateRoute, ScoredCandidateRoute
from app.scoring.time_period import (
    RouteTimeContext,
    build_route_time_context,
    determine_period,
)

__all__ = [
    "CandidateRoute",
    "ScoredCandidateRoute",
    "calculate_crime_exposure",
    "calculate_route_score",
    "calculate_segment_score",
    "score_candidate_routes",
    "select_fastest_route",
    "select_recommended_route",
    "select_safest_route",
    "RouteTimeContext",
    "build_route_time_context",
    "determine_period",
]