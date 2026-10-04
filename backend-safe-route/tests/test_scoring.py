"""Testy czystych funkcji scoringu segmentów i tras."""

import pytest

from app.scoring.route_scoring import (
    calculate_crime_exposure,
    calculate_route_score,
    calculate_segment_score,
    normalize_lighting,
    normalize_reports,
    normalize_safe_places,
    normalize_tunnel,
)
from app.scoring.scoring_config import load_scoring_config
from app.scoring.scoring_models import CrimeEventInput, NormalizationConfig, SegmentSafetyInput


@pytest.fixture
def scoring_config() -> tuple[dict, NormalizationConfig]:
    """Udostępnia konfigurację produkcyjną scoringu."""

    return load_scoring_config()


def test_scoring_yaml_contains_valid_day_and_night_weights(scoring_config: tuple[dict, NormalizationConfig]) -> None:
    """Wagi obu okresów są poprawne i sumują się do jedynki."""

    profiles, _ = scoring_config
    assert set(profiles["walking"]) == {"day", "night"}
    for weights in profiles["walking"].values():
        assert sum(vars(weights).values()) == pytest.approx(1.0)


def test_healthy_segment_scores_high(scoring_config: tuple[dict, NormalizationConfig]) -> None:
    """Kompletny, bezpieczny segment otrzymuje wysoki wynik."""

    profiles, normalization = scoring_config
    segment = SegmentSafetyInput(100, 1.0, 0, 0, 0, True, True, 0)
    result = calculate_segment_score(segment, profiles["walking"]["day"], normalization, "day")
    assert result.score == pytest.approx(97.5)
    assert result.data_coverage == pytest.approx(1.0)


def test_risky_segment_scores_low(scoring_config: tuple[dict, NormalizationConfig]) -> None:
    """Nieoświetlony segment z raportami i tunelem otrzymuje niski wynik."""

    profiles, normalization = scoring_config
    segment = SegmentSafetyInput(100, 0.0, 5, 100, 500, False, False, 5)
    result = calculate_segment_score(segment, profiles["walking"]["night"], normalization, "night")
    assert result.score == pytest.approx(5.0)


def test_unknown_values_are_neutral_and_reduce_coverage(
    scoring_config: tuple[dict, NormalizationConfig],
) -> None:
    """Brak danych nie wywraca obliczeń, ale obniża informację o pokryciu."""

    profiles, normalization = scoring_config
    segment = SegmentSafetyInput(100, None, 0, 0, None)
    result = calculate_segment_score(segment, profiles["walking"]["day"], normalization, "day")
    assert result.score == pytest.approx(69.0)
    assert result.data_coverage == pytest.approx(2 / 7)


def test_route_score_is_weighted_by_segment_length(scoring_config: tuple[dict, NormalizationConfig]) -> None:
    """Długi segment ma większy wpływ na wynik trasy niż krótki."""

    profiles, normalization = scoring_config
    segments = [
        SegmentSafetyInput(100, 1.0, 0, 0, 0, True, True, 0),
        SegmentSafetyInput(900, 0.0, 5, 100, 500, False, False, 5),
    ]
    result = calculate_route_score(segments, profiles["walking"]["day"], normalization, "day")
    assert result.score == pytest.approx(12.0)


def test_normalizers_validate_inputs() -> None:
    """Normalizatory odrzucają wartości spoza swoich dziedzin."""

    with pytest.raises(ValueError):
        normalize_lighting(1.1)
    with pytest.raises(ValueError):
        normalize_reports(1, 0)
    with pytest.raises(ValueError):
        normalize_tunnel(-1, 100)
    with pytest.raises(ValueError):
        normalize_safe_places(-1, 500)


def test_daytime_lighting_is_always_maximum(
    scoring_config: tuple[dict, NormalizationConfig],
) -> None:
    """W dzień brak oświetlenia nie obniża oceny."""

    profiles, normalization = scoring_config
    dark = SegmentSafetyInput(100, 0.0, 0, 0, 0, True, True, 0)
    bright = SegmentSafetyInput(100, 1.0, 0, 0, 0, True, True, 0)
    dark_result = calculate_segment_score(dark, profiles["walking"]["day"], normalization, "day")
    bright_result = calculate_segment_score(
        bright, profiles["walking"]["day"], normalization, "day"
    )
    assert dark_result.lighting_score == 1.0
    assert dark_result.score == pytest.approx(bright_result.score)


def test_crime_exposure_uses_category_weight_and_time_decay(
    scoring_config: tuple[dict, NormalizationConfig],
) -> None:
    """Poważniejsze i świeższe zdarzenia mają większy wpływ."""

    _, normalization = scoring_config
    events = [
        CrimeEventInput("assault", 0),
        CrimeEventInput("theft", normalization.crime_half_life_days),
    ]
    exposure = calculate_crime_exposure(
        events, normalization.crime_category_weights, normalization.crime_half_life_days
    )
    assert exposure == pytest.approx(1.0 + 0.5 * 2.718281828459045**-1)


def test_empty_or_zero_length_route_is_rejected(
    scoring_config: tuple[dict, NormalizationConfig],
) -> None:
    """Scoring odrzuca trasę bez segmentów i bez długości."""

    profiles, normalization = scoring_config
    with pytest.raises(ValueError):
        calculate_route_score([], profiles["walking"]["day"], normalization)
    with pytest.raises(ValueError):
        calculate_route_score(
            [SegmentSafetyInput(0, 1.0, 0, 0, 0)],
            profiles["walking"]["day"],
            normalization,
        )
