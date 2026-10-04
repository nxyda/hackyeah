"""Testy porównywania wielu kandydackich tras na sztucznych danych."""

import pytest

from app.scoring.multi_route_scoring import (
    normalize_duration,
    score_candidate_routes,
    select_fastest_route,
    select_recommended_route,
    select_safest_route,
)
from app.scoring.route_models import CandidateRoute
from app.scoring.scoring_config import load_scoring_config
from app.scoring.scoring_models import SegmentSafetyInput


def make_route(
    route_id: str,
    duration_s: float,
    segments: tuple[SegmentSafetyInput, ...],
) -> CandidateRoute:
    """Tworzy sztuczną trasę z prostą geometrią testową."""

    return CandidateRoute(
        route_id=route_id,
        geometry=((21.0, 52.0), (21.001, 52.001)),
        duration_s=duration_s,
        distance_m=sum(segment.length_m for segment in segments),
        segments=segments,
    )


def test_fastest_and_safest_can_be_different_routes() -> None:
    """Szybszy wariant nie musi być najbezpieczniejszy."""

    profiles, normalization = load_scoring_config()
    routes = (
        make_route(
            "fast",
            600,
            (SegmentSafetyInput(500, 0.0, 3, 0, 500, False, False, 3.0),),
        ),
        make_route(
            "safe",
            780,
            (SegmentSafetyInput(500, 1.0, 0, 0, 50, True, True, 0.0),),
        ),
        make_route(
            "middle",
            700,
            (SegmentSafetyInput(500, 0.8, 1, 0, 150, True, None, 0.5),),
        ),
    )
    scored = score_candidate_routes(
        routes, profiles["walking"]["day"], normalization, safety_weight=0.8, period="day"
    )

    assert select_fastest_route(scored).candidate.route_id == "fast"
    assert select_safest_route(scored).candidate.route_id == "safe"
    assert select_recommended_route(scored).candidate.route_id == "safe"


def test_one_route_is_returned_without_creating_duplicates() -> None:
    """Jedna trasa pozostaje jednym wariantem."""

    profiles, normalization = load_scoring_config()
    route = make_route(
        "only",
        600,
        (SegmentSafetyInput(500, 1.0, 0, 0, 0, True, True, 0.0),),
    )
    scored = score_candidate_routes(
        (route,), profiles["walking"]["day"], normalization, safety_weight=0.5, period="day"
    )

    assert len(scored) == 1
    assert select_fastest_route(scored) is scored[0]
    assert select_safest_route(scored) is scored[0]


def test_duration_normalization_prefers_shorter_route() -> None:
    """Najkrótsza trasa otrzymuje wynik czasu równy jeden."""

    assert normalize_duration(600, 600, 900) == pytest.approx(1.0)
    assert normalize_duration(750, 600, 900) == pytest.approx(0.5)
    assert normalize_duration(900, 600, 900) == pytest.approx(0.0)
    assert normalize_duration(600, 600, 600) == pytest.approx(1.0)


def test_candidate_route_validation_and_selection_errors() -> None:
    """Niepoprawne wejście jest odrzucane jawnie."""

    with pytest.raises(ValueError):
        CandidateRoute("", (), 600, 500, ())
    with pytest.raises(ValueError):
        CandidateRoute("invalid", (), -1, 500, ())
    with pytest.raises(ValueError):
        normalize_duration(600, 900, 600)


def test_duplicate_route_ids_are_rejected() -> None:
    """Identyfikatory tras muszą być jednoznaczne."""

    profiles, normalization = load_scoring_config()
    route = make_route(
        "duplicate",
        600,
        (SegmentSafetyInput(100, 1.0, 0, 0, 0),),
    )
    with pytest.raises(ValueError):
        score_candidate_routes(
            (route, route),
            profiles["walking"]["day"],
            normalization,
            safety_weight=0.5,
            period="day",
        )
