"""Wyznaczanie pory dnia i daty na podstawie czasu rozpoczęcia trasy."""

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Literal

Period = Literal["day", "night"]


@dataclass(frozen=True)
class RouteTimeContext:
    """Czas wyjazdu zapisany jako datetime, data kalendarzowa i pora dnia."""

    departure_time: datetime
    departure_date: date
    period: Period


def determine_period(
    departure_time: datetime,
    day_start: time = time(6, 0),
    night_start: time = time(20, 0),
) -> Period:
    """Zamienia czas wyjazdu na ``day`` albo ``night``."""

    if day_start >= night_start:
        raise ValueError("day_start must be earlier than night_start")
    departure_clock = departure_time.timetz().replace(tzinfo=None)
    return "day" if day_start <= departure_clock < night_start else "night"


def build_route_time_context(departure_time: datetime) -> RouteTimeContext:
    """Tworzy niemutowalny kontekst czasu trasy z datą wyjazdu."""

    return RouteTimeContext(
        departure_time=departure_time,
        departure_date=departure_time.date(),
        period=determine_period(departure_time),
    )
