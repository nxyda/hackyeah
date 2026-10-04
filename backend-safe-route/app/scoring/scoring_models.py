"""Niezależne od frameworków modele danych wejściowych i wyników scoringu."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SegmentSafetyInput:
    """Dane bezpieczeństwa jednego segmentu trasy."""

    length_m: float
    lit_ratio: float | None
    reports_nearby: int
    tunnel_m: float
    safe_place_distance_m: float | None
    is_footway: bool | None = None
    surveillance_nearby: bool | None = None
    crime_exposure: float | None = None
    camera_count: int = 0
    road_type: str | None = None
    stairs_score: float | None = None
    access_score: float | None = None
    road_type_score: float | None = None
    reports_impact: float | None = None
    surface_score: float | None = None
    incline_score: float | None = None
    crossing_score: float | None = None

    def __post_init__(self) -> None:
        """Sprawdza zakresy danych przed rozpoczęciem obliczeń."""

        if self.length_m < 0:
            raise ValueError("length_m must be non-negative")
        if self.lit_ratio is not None and not 0 <= self.lit_ratio <= 1:
            raise ValueError("lit_ratio must be between 0 and 1")
        if self.reports_nearby < 0:
            raise ValueError("reports_nearby must be non-negative")
        if self.tunnel_m < 0:
            raise ValueError("tunnel_m must be non-negative")
        if self.safe_place_distance_m is not None and self.safe_place_distance_m < 0:
            raise ValueError("safe_place_distance_m must be non-negative")
        if self.crime_exposure is not None and self.crime_exposure < 0:
            raise ValueError("crime_exposure must be non-negative")
        if self.camera_count < 0:
            raise ValueError("camera_count must be non-negative")
        for name in (
            "stairs_score",
            "access_score",
            "road_type_score",
            "surface_score",
            "incline_score",
            "crossing_score",
        ):
            value = getattr(self, name)
            if value is not None and not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class ScoringWeights:
    """Wagi komponentów jednego profilu i okresu dnia."""

    lighting: float
    reports: float
    crime_history: float
    tunnels: float
    safe_places: float
    footway: float
    surveillance: float
    road_type: float = 0.0
    stairs: float = 0.0
    access: float = 0.0
    surface: float = 0.0
    incline: float = 0.0
    crossing: float = 0.0

    def __post_init__(self) -> None:
        """Wymusza nieujemne wagi sumujące się do jedynki."""

        values = (
            self.lighting,
            self.reports,
            self.crime_history,
            self.tunnels,
            self.safe_places,
            self.footway,
            self.surveillance,
            self.road_type,
            self.stairs,
            self.access,
            self.surface,
            self.incline,
            self.crossing,
        )
        if any(value < 0 for value in values):
            raise ValueError("scoring weights must be non-negative")
        if abs(sum(values) - 1.0) > 1e-9:
            raise ValueError("scoring weights must sum to 1.0")


@dataclass(frozen=True)
class NormalizationConfig:
    """Parametry zamiany danych surowych na wartości 0–1."""

    reports_saturation_count: int
    crime_exposure_saturation: float
    safe_place_max_distance_m: float
    tunnel_penalty_distance_m: float
    crime_half_life_days: float
    crime_category_weights: dict[str, float]

    def __post_init__(self) -> None:
        """Sprawdza, czy parametry normalizacji są dodatnie."""

        if self.reports_saturation_count <= 0:
            raise ValueError("reports_saturation_count must be positive")
        if self.crime_exposure_saturation <= 0:
            raise ValueError("crime_exposure_saturation must be positive")
        if self.safe_place_max_distance_m <= 0:
            raise ValueError("safe_place_max_distance_m must be positive")
        if self.tunnel_penalty_distance_m <= 0:
            raise ValueError("tunnel_penalty_distance_m must be positive")
        if self.crime_half_life_days <= 0:
            raise ValueError("crime_half_life_days must be positive")
        if not self.crime_category_weights:
            raise ValueError("crime_category_weights must not be empty")
        if any(weight < 0 for weight in self.crime_category_weights.values()):
            raise ValueError("crime category weights must be non-negative")


@dataclass(frozen=True)
class CrimeEventInput:
    """Uproszczone dane historycznego zdarzenia kryminalnego."""

    category: str
    age_days: float
    severity: float = 1.0

    def __post_init__(self) -> None:
        """Sprawdza, czy wiek zdarzenia jest poprawny."""

        if self.age_days < 0:
            raise ValueError("age_days must be non-negative")
        if self.severity < 0:
            raise ValueError("severity must be non-negative")


@dataclass(frozen=True)
class SegmentScoreBreakdown:
    """Wynik segmentu wraz z wynikami poszczególnych komponentów."""

    score: float
    lighting_score: float
    reports_score: float
    crime_history_score: float
    tunnel_score: float
    safe_places_score: float
    footway_score: float
    surveillance_score: float
    data_coverage: float
    road_type_score: float = 0.5
    stairs_score: float = 0.5
    access_score: float = 0.5
    surface_score: float = 0.5
    incline_score: float = 0.5
    crossing_score: float = 0.5


@dataclass(frozen=True)
class RouteScoreResult:
    """Wynik scoringu trasy i jej segmentów."""

    score: float
    segment_scores: tuple[SegmentScoreBreakdown, ...]
    data_coverage: float
