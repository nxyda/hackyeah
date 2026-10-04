from app.routing.local_graph import (
    LocalRouteFinder,
    RoadGraphSegment,
    calculate_safety_score,
)
from app.scoring.scoring_models import SegmentSafetyInput


def segment(
    segment_id: int,
    geometry: tuple[tuple[float, float], ...],
    length_m: float,
    lit_ratio: float | None,
) -> RoadGraphSegment:
    return RoadGraphSegment(
        segment_id=segment_id,
        geometry=geometry,
        length_m=length_m,
        safety=SegmentSafetyInput(
            length_m=length_m,
            lit_ratio=lit_ratio,
            reports_nearby=0,
            tunnel_m=0,
            safe_place_distance_m=50,
            is_footway=True,
            surveillance_nearby=True,
        ),
    )


def test_local_graph_returns_three_distinct_routes() -> None:
    finder = LocalRouteFinder(
        [
            segment(1, ((0, 0), (1, 0)), 100, 1),
            segment(2, ((1, 0), (2, 0)), 100, 1),
            segment(3, ((0, 0), (0, 1)), 130, 0.2),
            segment(4, ((0, 1), (1, 1)), 130, 0.2),
            segment(5, ((1, 1), (2, 0)), 130, 0.2),
            segment(6, ((0, 0), (0.5, 0.5)), 150, 1),
            segment(7, ((0.5, 0.5), (1.5, 0.5)), 150, 1),
            segment(8, ((1.5, 0.5), (2, 0)), 150, 1),
        ]
    )

    routes = finder.find_routes((0, 0), (2, 0), safety_weight=0.5)

    assert len(routes) == 3
    assert len({route.segment_ids for route in routes}) == 3
    assert routes[0].geometry[0] == (0, 0)
    assert routes[0].geometry[-1] == (2, 0)


def test_empty_graph_returns_no_routes() -> None:
    assert LocalRouteFinder(()).find_routes((0, 0), (1, 1), 0.5) == ()


def test_graph_rejects_endpoints_far_from_road_data() -> None:
    finder = LocalRouteFinder(
        [segment(1, ((0, 0), (0.001, 0)), 100, 1)]
    )

    assert finder.find_routes((0.01, 0.01), (0.001, 0), 0.5) == ()


def test_missing_crime_and_safe_place_data_is_neutral() -> None:
    safety = SegmentSafetyInput(
        length_m=100,
        lit_ratio=None,
        reports_nearby=0,
        tunnel_m=0,
        safe_place_distance_m=None,
        is_footway=None,
        surveillance_nearby=None,
        crime_exposure=None,
    )

    assert calculate_safety_score(safety) == 0.75
