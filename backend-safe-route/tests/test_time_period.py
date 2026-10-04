"""Testy zamiany czasu wyjazdu na porę dnia i datę."""

from datetime import date, datetime, time, timezone

import pytest

from app.scoring.time_period import build_route_time_context, determine_period


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    (
        (0, 0, "night"),
        (5, 59, "night"),
        (6, 0, "day"),
        (19, 59, "day"),
        (20, 0, "night"),
        (23, 59, "night"),
    ),
)
def test_determine_period_uses_day_boundaries(
    hour: int,
    minute: int,
    expected: str,
) -> None:
    """Granice 06:00 i 20:00 są przypisane do właściwych okresów."""

    assert determine_period(datetime(2026, 10, 3, hour, minute)) == expected


def test_context_keeps_departure_datetime_and_calendar_date() -> None:
    """Kontekst przechowuje pełny czas oraz datę dnia wyjazdu."""

    departure_time = datetime(2026, 10, 3, 21, 15, tzinfo=timezone.utc)
    context = build_route_time_context(departure_time)

    assert context.departure_time == departure_time
    assert context.departure_date == date(2026, 10, 3)
    assert context.period == "night"


def test_custom_boundaries_can_be_used() -> None:
    """Granice pory dnia można zmienić bez modyfikowania algorytmu."""

    departure_time = datetime(2026, 10, 3, 7, 0)

    assert determine_period(departure_time, time(7, 0), time(19, 0)) == "day"
    assert determine_period(datetime(2026, 10, 3, 6, 59), time(7, 0), time(19, 0)) == "night"


def test_invalid_boundaries_are_rejected() -> None:
    """Niepoprawne granice nie są akceptowane."""

    with pytest.raises(ValueError):
        determine_period(datetime(2026, 10, 3, 12), time(20), time(6))
