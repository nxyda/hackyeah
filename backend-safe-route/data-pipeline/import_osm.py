"""Szkielet importu OSM: pobranie danych, filtracja, normalizacja i zapis PostGIS."""


def import_osm(source: str, database_url: str) -> None:
    """Importuje dane OSM do tabel road_segments i safe_places."""

    raise NotImplementedError


# TODO: Dodać pobieranie przez osmnx, transformację geometrii i idempotentny import.
