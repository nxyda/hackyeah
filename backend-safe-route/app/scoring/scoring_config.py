"""Wczytywanie i walidacja konfiguracji scoringu z pliku YAML."""

from pathlib import Path
from typing import Any

import yaml

from app.scoring.scoring_models import NormalizationConfig, ScoringWeights


def load_scoring_config(
    path: Path | str = Path(__file__).resolve().parents[1] / "scoring.yaml",
) -> tuple[dict[str, dict[str, ScoringWeights]], NormalizationConfig]:
    """Wczytuje wagi profili oraz parametry normalizacji z YAML."""

    config_path = Path(path)
    raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw_config, dict):
        raise ValueError("scoring configuration must contain a YAML mapping")

    profiles = raw_config.get("profiles")
    normalization = raw_config.get("normalization")
    if not isinstance(profiles, dict) or not isinstance(normalization, dict):
        raise ValueError("scoring configuration requires profiles and normalization")

    parsed_profiles: dict[str, dict[str, ScoringWeights]] = {}
    for profile_name, periods in profiles.items():
        if not isinstance(profile_name, str) or not isinstance(periods, dict):
            raise ValueError("each scoring profile must contain day and night mappings")
        parsed_profiles[profile_name] = {
            period_name: _parse_weights(period_name, values)
            for period_name, values in periods.items()
        }

    return parsed_profiles, _parse_normalization(normalization)


def _parse_weights(period_name: Any, values: Any) -> ScoringWeights:
    """Tworzy wagi okresu i zgłasza brakujące lub niepoprawne pola."""

    if not isinstance(period_name, str) or not isinstance(values, dict):
        raise ValueError("scoring period must contain a mapping of weights")
    required_fields = (
        "lighting",
        "reports",
        "crime_history",
        "tunnels",
        "safe_places",
        "footway",
        "surveillance",
        "road_type",
        "stairs",
        "access",
        "surface",
        "incline",
        "crossing",
    )
    if any(field not in values for field in required_fields):
        raise ValueError(f"scoring period {period_name!r} has missing weights")
    return ScoringWeights(*(float(values[field]) for field in required_fields))


def _parse_normalization(values: dict[str, Any]) -> NormalizationConfig:
    """Tworzy parametry normalizacji z sekcji YAML."""

    required_fields = (
        "reports_saturation_count",
        "crime_exposure_saturation",
        "safe_place_max_distance_m",
        "tunnel_penalty_distance_m",
        "crime_half_life_days",
        "crime_category_weights",
    )
    if any(field not in values for field in required_fields):
        raise ValueError("normalization configuration has missing fields")
    return NormalizationConfig(
        reports_saturation_count=int(values["reports_saturation_count"]),
        crime_exposure_saturation=float(values["crime_exposure_saturation"]),
        safe_place_max_distance_m=float(values["safe_place_max_distance_m"]),
        tunnel_penalty_distance_m=float(values["tunnel_penalty_distance_m"]),
        crime_half_life_days=float(values["crime_half_life_days"]),
        crime_category_weights={
            str(category): float(weight)
            for category, weight in _require_mapping(
                values, "crime_category_weights"
            ).items()
        },
    )


def _require_mapping(values: dict[str, Any], field_name: str) -> dict[Any, Any]:
    """Zwraca mapę konfiguracji albo zgłasza czytelny błąd."""

    value = values.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a mapping")
    return value
