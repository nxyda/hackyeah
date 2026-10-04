"""Czyste funkcje obliczające bezpieczeństwo segmentów i całych tras."""

from collections.abc import Sequence
from math import exp
from typing import Literal

from app.scoring.scoring_models import (
    CrimeEventInput,
    NormalizationConfig,
    RouteScoreResult,
    ScoringWeights,
    SegmentSafetyInput,
    SegmentScoreBreakdown,
)


def normalize_lighting(
    lit_ratio: float | None,
    period: Literal["day", "night"] = "night",
) -> float:
    """Zwraca wynik oświetlenia; w dzień światło nie obniża oceny."""

    if period not in ("day", "night"):
        raise ValueError("period must be 'day' or 'night'")
    if period == "day":
        return 1.0
    if lit_ratio is None:
        return 0.5
    if not 0 <= lit_ratio <= 1:
        raise ValueError("lit_ratio must be between 0 and 1")
    return lit_ratio


def normalize_crime_exposure(exposure: float | None, saturation: float) -> float:
    """Zamienia historyczne narażenie kryminalne na wynik 0–1."""

    if exposure is not None and exposure < 0:
        raise ValueError("crime exposure must be non-negative")
    if saturation <= 0:
        raise ValueError("crime saturation must be positive")
    if exposure is None:
        return 0.5
    return 1.0 - min(exposure / saturation, 1.0)


def calculate_crime_exposure(
    events: Sequence[CrimeEventInput],
    category_weights: dict[str, float],
    half_life_days: float,
) -> float:
    """Sumuje ważone zdarzenia z wykładniczym zanikiem w czasie."""

    if half_life_days <= 0:
        raise ValueError("half_life_days must be positive")
    if any(weight < 0 for weight in category_weights.values()):
        raise ValueError("crime category weights must be non-negative")
    return sum(
        category_weights.get(event.category, category_weights.get("other", 0.0))
        * event.severity
        * exp(-event.age_days / half_life_days)
        for event in events
    )


def normalize_reports(reports_nearby: float, saturation_count: int) -> float:
    """Zamienia liczbę raportów na wynik z nasyceniem przy saturation_count."""

    if reports_nearby < 0:
        raise ValueError("reports_nearby must be non-negative")
    if saturation_count <= 0:
        raise ValueError("saturation_count must be positive")
    return 1.0 - min(reports_nearby / saturation_count, 1.0)


def normalize_tunnel(tunnel_m: float, penalty_distance_m: float) -> float:
    """Obniża wynik proporcjonalnie do długości tunelu."""

    if tunnel_m < 0:
        raise ValueError("tunnel_m must be non-negative")
    if penalty_distance_m <= 0:
        raise ValueError("penalty_distance_m must be positive")
    return 1.0 - min(tunnel_m / penalty_distance_m, 1.0)


def normalize_safe_places(distance_m: float | None, max_distance_m: float) -> float:
    """Zwraca wyższy wynik dla bliższego bezpiecznego miejsca."""

    if distance_m is not None and distance_m < 0:
        raise ValueError("distance_m must be non-negative")
    if max_distance_m <= 0:
        raise ValueError("max_distance_m must be positive")
    if distance_m is None:
        return 0.5
    return 1.0 - min(distance_m / max_distance_m, 1.0)


def normalize_boolean(value: bool | None) -> float:
    """Zamienia cechę logiczną na wynik, neutralizując brak danych."""

    return 0.5 if value is None else float(value)


def normalize_surveillance(
    camera_count: int,
    surveillance_nearby: bool | None,
    saturation_count: int = 3,
) -> float:
    """Normalizuje liczbę kamer, zachowując neutralność przy braku danych."""

    if camera_count < 0 or saturation_count <= 0:
        raise ValueError("camera count and saturation must be non-negative/positive")
    if camera_count:
        return min(camera_count / saturation_count, 1.0)
    return normalize_boolean(surveillance_nearby)


def calculate_segment_score(
    segment: SegmentSafetyInput,
    weights: ScoringWeights,
    normalization: NormalizationConfig,
    period: Literal["day", "night"] = "night",
) -> SegmentScoreBreakdown:
    """Oblicza wynik segmentu oraz jego rozkład na komponenty."""

    component_scores = {
        "lighting_score": normalize_lighting(segment.lit_ratio, period),
        "reports_score": normalize_reports(
            segment.reports_impact
            if segment.reports_impact is not None
            else float(segment.reports_nearby),
            normalization.reports_saturation_count,
        ),
        "crime_history_score": normalize_crime_exposure(
            segment.crime_exposure, normalization.crime_exposure_saturation
        ),
        "tunnel_score": normalize_tunnel(segment.tunnel_m, normalization.tunnel_penalty_distance_m),
        "safe_places_score": normalize_safe_places(
            segment.safe_place_distance_m, normalization.safe_place_max_distance_m
        ),
        "footway_score": normalize_boolean(segment.is_footway),
        "surveillance_score": normalize_surveillance(
            segment.camera_count,
            segment.surveillance_nearby,
        ),
        "road_type_score": normalize_boolean(segment.road_type_score),
        "stairs_score": normalize_boolean(segment.stairs_score),
        "access_score": normalize_boolean(segment.access_score),
        "surface_score": normalize_boolean(segment.surface_score),
        "incline_score": normalize_boolean(segment.incline_score),
        "crossing_score": normalize_boolean(segment.crossing_score),
    }
    score = 100.0 * sum(
        component_scores[name] * weight
        for name, weight in (
            ("lighting_score", weights.lighting),
            ("reports_score", weights.reports),
            ("crime_history_score", weights.crime_history),
            ("tunnel_score", weights.tunnels),
            ("safe_places_score", weights.safe_places),
            ("footway_score", weights.footway),
            ("surveillance_score", weights.surveillance),
            ("road_type_score", weights.road_type),
            ("stairs_score", weights.stairs),
            ("access_score", weights.access),
            ("surface_score", weights.surface),
            ("incline_score", weights.incline),
            ("crossing_score", weights.crossing),
        )
    )
    known_components = sum(
        value is not None
        for value in (
            segment.lit_ratio,
            segment.safe_place_distance_m,
            segment.is_footway,
            segment.surveillance_nearby,
            segment.crime_exposure,
            segment.road_type_score,
            segment.stairs_score,
            segment.access_score,
            segment.surface_score,
            segment.incline_score,
            segment.crossing_score,
        )
    )
    data_coverage = (known_components + 2) / 7
    return SegmentScoreBreakdown(score=score, data_coverage=data_coverage, **component_scores)


def calculate_route_score(
    segments: Sequence[SegmentSafetyInput],
    weights: ScoringWeights,
    normalization: NormalizationConfig,
    period: Literal["day", "night"] = "night",
) -> RouteScoreResult:
    """Oblicza średnią ważoną długością dla całej trasy."""

    if not segments:
        raise ValueError("route must contain at least one segment")
    segment_scores = tuple(
        calculate_segment_score(segment, weights, normalization, period)
        for segment in segments
    )
    total_length = sum(segment.length_m for segment in segments)
    if total_length <= 0:
        raise ValueError("route segment length must be greater than zero")
    route_score = sum(
        segment.length_m * scored.score for segment, scored in zip(segments, segment_scores, strict=True)
    ) / total_length
    data_coverage = sum(
        segment.length_m * scored.data_coverage
        for segment, scored in zip(segments, segment_scores, strict=True)
    ) / total_length
    return RouteScoreResult(
        score=route_score,
        segment_scores=segment_scores,
        data_coverage=data_coverage,
    )
