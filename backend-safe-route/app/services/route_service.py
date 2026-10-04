"""Orkiestracja Mapboxa, lokalnego grafu i scoringu bezpieczeństwa."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from math import log1p

from geoalchemy2.elements import WKBElement, WKTElement
from geoalchemy2.shape import to_shape
from shapely.geometry import LineString, Point
from shapely.ops import transform
from shapely.strtree import STRtree
from pyproj import Transformer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.integrations.mapbox_directions_client import MapboxDirectionsClient
from app.repositories.road_segment_repository import RoadSegmentRepository
from app.repositories.crime_event_repository import CrimeEventRepository
from app.repositories.street_lamp_repository import StreetLampRepository
from app.repositories.camera_repository import CameraRepository
from app.repositories.safe_place_repository import SafePlaceRepository
from app.repositories.report_repository import ReportRepository
from app.routing.local_graph import LocalRouteFinder, RoadGraphSegment
from app.schemas.route import (
    GeoJSONLineString,
    RouteComponents,
    RouteOption,
    RouteRequest,
    RouteResponse,
    RouteSegment,
)
from app.scoring.multi_route_scoring import (
    score_candidate_routes,
    select_fastest_route,
    select_safest_route,
)
from app.scoring.route_models import CandidateRoute, ScoredCandidateRoute
from app.scoring.scoring_config import load_scoring_config
from app.scoring.route_scoring import calculate_crime_exposure
from app.scoring.scoring_models import (
    CrimeEventInput,
    NormalizationConfig,
    SegmentSafetyInput,
)
from app.scoring.time_period import build_route_time_context
from app.spatial import METRIC_SRID, WGS84_SRID

logger = logging.getLogger(__name__)
_WGS84_TO_METRIC = Transformer.from_crs(
    WGS84_SRID,
    METRIC_SRID,
    always_xy=True,
)


class RouteUnavailableError(RuntimeError):
    """Raised when the routing provider does not return a usable route."""


@dataclass(frozen=True)
class _SpatialPointIndex:
    """Metryczny indeks punktów infrastruktury dla jednego requestu."""

    tree: STRtree
    points: tuple[Point, ...]

    def count_near(self, line: LineString, radius_m: float) -> int:
        return len(self.tree.query(line.buffer(radius_m)))

    def nearest_distance(self, line: LineString) -> float | None:
        candidates = self.tree.query(line.buffer(500.0))
        if len(candidates) == 0:
            return None
        return min(float(line.distance(self.points[int(index)])) for index in candidates)


def _average_optional(values: object) -> float | None:
    """Uśrednia znane wartości opcjonalnej cechy segmentów."""

    known = [float(value) for value in values if value is not None]
    return sum(known) / len(known) if known else None


class RouteService:
    """Koordynuje dane z repozytorium i przyszły scoring trasy."""

    def __init__(self, session: AsyncSession) -> None:
        """Tworzy serwis dla jednej sesji bazy danych."""

        self.session = session

    async def calculate_route(self, request: RouteRequest) -> RouteResponse:
        """Wyznacza, porównuje i opisuje warianty trasy."""

        settings = get_settings()
        mapbox = MapboxDirectionsClient(
            settings.mapbox_secret_token.get_secret_value()
        )
        try:
            mapbox_routes = await asyncio.to_thread(
                mapbox.get_walking_routes,
                request.start,
                request.end,
                True,
            )
        finally:
            mapbox.close()
        if not mapbox_routes:
            raise RouteUnavailableError("Mapbox returned no walking routes")

        base_route = mapbox_routes[0]
        repository = RoadSegmentRepository(self.session)
        corridor_wkt = LineString(base_route.geometry).wkt
        corridor_buffer_m = settings.routing_corridor_buffer_m
        database_segments = await repository.get_in_corridor(
            corridor_wkt,
            buffer_m=corridor_buffer_m,
        )
        crime_events = await CrimeEventRepository(self.session).get_in_corridor(
            corridor_wkt,
            buffer_m=corridor_buffer_m,
        )
        lamps = await StreetLampRepository(self.session).get_in_corridor(
            corridor_wkt,
            buffer_m=corridor_buffer_m,
        )
        cameras = await CameraRepository(self.session).get_in_corridor(
            corridor_wkt,
            buffer_m=corridor_buffer_m,
        )
        safe_places = await SafePlaceRepository(self.session).get_in_corridor(
            corridor_wkt,
            buffer_m=corridor_buffer_m,
        )
        reports = await ReportRepository(self.session).get_active_in_corridor(
            corridor_wkt,
            buffer_m=corridor_buffer_m,
            departure_time=request.departure_time,
        )
        spatial_indexes = self._build_spatial_indexes(
            lamps,
            cameras,
            [
                place for place in safe_places
                if self._safe_place_is_open(place, request.departure_time)
            ],
            reports,
        )
        profiles, normalization = load_scoring_config()
        time_context = build_route_time_context(request.departure_time)
        weights = profiles[request.profile][time_context.period]
        graph_segments = tuple(
            self._to_graph_segment(
                segment,
                crime_events,
                time_context.departure_time,
                normalization,
                lamps,
                cameras,
                safe_places,
                reports,
                spatial_indexes,
            )
            for segment in database_segments
        )
        finder = LocalRouteFinder(
            graph_segments,
            weights=weights,
            normalization=normalization,
            period=time_context.period,
        )
        local_routes = []
        for route_weight in (0.0, request.safety_weight, 1.0):
            local_routes.extend(
                finder.find_routes(
                    (request.start.lon, request.start.lat),
                    (request.end.lon, request.end.lat),
                    route_weight,
                )
            )

        candidates = [
            self._mapbox_candidate(route, graph_segments)
            for route in mapbox_routes
        ]
        candidates.extend(
            self._local_candidate(index, route, graph_segments)
            for index, route in enumerate(local_routes)
        )
        candidates = self._unique_candidates(candidates)
        scored = self._score_candidates(candidates, request)
        fastest = select_fastest_route(scored)
        safest = select_safest_route(scored)
        logger.info(
            "Route calculated candidates=%d alternatives=%d mode=%s coverage=%s",
            len(scored),
            max(len(scored) - 2, 0),
            settings.api_mode,
            "segment_data" if graph_segments else "mapbox_only",
        )
        return RouteResponse(
            fastest=self._to_response(fastest),
            safest=self._to_response(safest),
            alternatives=[
                self._to_response(route)
                for route in scored
                if route.candidate.route_id not in {fastest.candidate.route_id, safest.candidate.route_id}
            ],
            meta={
                "mode": settings.api_mode,
                "version": "0.1.0",
                "data_coverage": "segment_data" if graph_segments else "mapbox_only",
            },
        )

    @classmethod
    def _to_graph_segment(
        cls,
        segment: object,
        crime_events: list[object] | tuple[object, ...] = (),
        departure_time: datetime | None = None,
        normalization: NormalizationConfig | None = None,
        lamps: list[object] | tuple[object, ...] = (),
        cameras: list[object] | tuple[object, ...] = (),
        safe_places: list[object] | tuple[object, ...] = (),
        reports: list[object] | tuple[object, ...] = (),
        spatial_indexes: dict[str, _SpatialPointIndex] | None = None,
    ) -> RoadGraphSegment:
        geometry = RouteService._geometry_coordinates(segment.geom)
        crime_exposure = cls._crime_exposure_for_segment(
            geometry,
            crime_events,
            departure_time,
            normalization,
        )
        safety = SegmentSafetyInput(
            length_m=float(segment.length_m),
            lit_ratio=cls._lighting_ratio(
                geometry,
                segment.length_m,
                lamps,
                spatial_indexes.get("lamps") if spatial_indexes else None,
            ),
            reports_nearby=cls._nearby_report_impact(
                geometry,
                reports,
                50.0,
                spatial_indexes.get("reports") if spatial_indexes else None,
            ),
            reports_impact=cls._nearby_report_float_impact(
                geometry,
                reports,
                50.0,
                spatial_indexes.get("reports") if spatial_indexes else None,
            ),
            tunnel_m=float(segment.length_m) if segment.is_tunnel else 0.0,
            safe_place_distance_m=cls._nearest_distance(
                geometry,
                safe_places,
                spatial_indexes.get("safe_places") if spatial_indexes else None,
            ),
            is_footway=segment.is_footway,
            surveillance_nearby=bool(
                cls._nearby_count(
                    geometry,
                    cameras,
                    75.0,
                    spatial_indexes.get("cameras") if spatial_indexes else None,
                )
            ),
            crime_exposure=crime_exposure,
            camera_count=cls._nearby_count(
                geometry,
                cameras,
                75.0,
                spatial_indexes.get("cameras") if spatial_indexes else None,
            ),
            road_type=str(getattr(segment, "road_type", "")).lower() or None,
            stairs_score=cls._stairs_score(getattr(segment, "road_type", None)),
            access_score=cls._access_score(getattr(segment, "road_type", None)),
            road_type_score=cls._road_type_score(getattr(segment, "road_type", None)),
            surface_score=cls._surface_score(getattr(segment, "surface", None)),
            incline_score=cls._incline_score(getattr(segment, "incline", None)),
            crossing_score=cls._crossing_score(getattr(segment, "crossing", None)),
        )
        return RoadGraphSegment(
            segment_id=int(segment.id),
            geometry=geometry,
            length_m=float(segment.length_m),
            safety=safety,
        )

    @classmethod
    def _metric_line(cls, geometry: tuple[tuple[float, float], ...]) -> LineString:
        return transform(_WGS84_TO_METRIC.transform, LineString(geometry))

    @classmethod
    def _metric_point(cls, geometry: object) -> Point:
        return transform(_WGS84_TO_METRIC.transform, cls._point_geometry(geometry))

    @classmethod
    def _nearby_count(
        cls,
        geometry: tuple[tuple[float, float], ...],
        objects: list[object] | tuple[object, ...],
        radius_m: float,
        index: _SpatialPointIndex | None = None,
    ) -> int:
        if not objects:
            return 0
        line = cls._metric_line(geometry)
        if index is not None:
            return index.count_near(line, radius_m)
        points = [
            cls._metric_point(getattr(item, "location", getattr(item, "geom", None)))
            for item in objects
        ]
        tree = STRtree(points)
        return len(tree.query(line.buffer(radius_m)))

    @classmethod
    def _nearby_report_impact(
        cls,
        geometry: tuple[tuple[float, float], ...],
        reports: list[object] | tuple[object, ...],
        radius_m: float,
        index: _SpatialPointIndex | None = None,
    ) -> int:
        if not reports:
            return 0
        if index is None:
            line = cls._metric_line(geometry)
            return sum(
                int(round(1 + log1p(max(0, int(getattr(report, "confirmations", 0))))))
                for report in reports
                if line.distance(
                    cls._metric_point(getattr(report, "geom"))
                ) <= radius_m
            )
        line = cls._metric_line(geometry)
        indices = index.tree.query(line.buffer(radius_m))
        return sum(
            int(round(cls._report_impact(reports[int(i)])))
            for i in indices
        )

    @classmethod
    def _nearby_report_float_impact(
        cls,
        geometry: tuple[tuple[float, float], ...],
        reports: list[object] | tuple[object, ...],
        radius_m: float,
        index: _SpatialPointIndex | None = None,
    ) -> float:
        if not reports:
            return 0.0
        line = cls._metric_line(geometry)
        if index is not None:
            indices = index.tree.query(line.buffer(radius_m))
            return sum(cls._report_impact(reports[int(i)]) for i in indices)
        return sum(
            cls._report_impact(report)
            for report in reports
            if line.distance(cls._metric_point(getattr(report, "geom"))) <= radius_m
        )

    @staticmethod
    def _report_impact(report: object) -> float:
        confirmations = max(0, int(getattr(report, "confirmations", 0)))
        return 1.0 + log1p(confirmations)

    @classmethod
    def _nearest_distance(
        cls,
        geometry: tuple[tuple[float, float], ...],
        objects: list[object] | tuple[object, ...],
        index: _SpatialPointIndex | None = None,
    ) -> float | None:
        if not objects:
            return None
        line = cls._metric_line(geometry)
        if index is not None:
            return index.nearest_distance(line)
        points = [
            cls._metric_point(getattr(item, "geom", None))
            for item in objects
        ]
        tree = STRtree(points)
        candidates = tree.query(line.buffer(500.0))
        if len(candidates) == 0:
            return None
        return min(float(line.distance(points[int(index)])) for index in candidates)

    @classmethod
    def _lighting_ratio(
        cls,
        geometry: tuple[tuple[float, float], ...],
        length_m: float,
        lamps: list[object] | tuple[object, ...],
        index: _SpatialPointIndex | None = None,
    ) -> float | None:
        if not lamps:
            return None
        lamp_count = cls._nearby_count(geometry, lamps, 25.0, index)
        return min(1.0, lamp_count / max(length_m / 35.0, 1.0))

    @classmethod
    def _build_spatial_indexes(
        cls,
        lamps: list[object],
        cameras: list[object],
        safe_places: list[object],
        reports: list[object],
    ) -> dict[str, _SpatialPointIndex]:
        """Buduje indeksy R-tree po jednorazowej transformacji punktów do metrów."""

        def build(objects: list[object], attribute: str) -> _SpatialPointIndex:
            points = tuple(
                cls._metric_point(getattr(item, attribute))
                for item in objects
            )
            return _SpatialPointIndex(STRtree(points), points)

        return {
            "lamps": build(lamps, "location"),
            "cameras": build(cameras, "location"),
            "safe_places": build(safe_places, "geom"),
            "reports": build(reports, "geom"),
        }

    @classmethod
    def _crime_exposure_for_segment(
        cls,
        geometry: tuple[tuple[float, float], ...],
        crime_events: list[object] | tuple[object, ...],
        departure_time: datetime | None,
        normalization: NormalizationConfig | None,
    ) -> float | None:
        """Sumuje świeże zdarzenia położone blisko segmentu."""

        if not crime_events or departure_time is None or normalization is None:
            return None
        metric_line = cls._metric_line(geometry)
        inputs: list[CrimeEventInput] = []
        for event in crime_events:
            if metric_line.distance(cls._metric_point(event.geom)) > 50.0:
                continue
            age_days = max(
                0.0,
                (departure_time - event.occurred_at).total_seconds() / 86_400,
            )
            category = getattr(event.category, "value", event.category)
            inputs.append(
                CrimeEventInput(
                    category=str(category).lower(),
                    age_days=age_days,
                    severity=max(0.0, float(getattr(event, "severity", None) or 1.0)),
                )
            )
        if not inputs:
            return None
        return calculate_crime_exposure(
            inputs,
            normalization.crime_category_weights,
            normalization.crime_half_life_days,
        )

    @staticmethod
    def _geometry_coordinates(geometry: object) -> tuple[tuple[float, float], ...]:
        if isinstance(geometry, (WKBElement, WKTElement)):
            shape = to_shape(geometry)
        elif isinstance(geometry, LineString):
            shape = geometry
        else:
            raise ValueError("road segment geometry must be a LineString")
        if not isinstance(shape, LineString):
            raise ValueError("road segment geometry must be a LineString")
        return tuple((float(x), float(y)) for x, y in shape.coords)

    @staticmethod
    def _point_geometry(geometry: object) -> Point:
        if isinstance(geometry, (WKBElement, WKTElement)):
            shape = to_shape(geometry)
        elif isinstance(geometry, Point):
            shape = geometry
        else:
            raise ValueError("spatial value must be a Point")
        if not isinstance(shape, Point):
            raise ValueError("spatial value must be a Point")
        return shape

    @staticmethod
    def _safe_place_is_open(place: object, departure_time: datetime) -> bool:
        if bool(getattr(place, "is_24_7", False)):
            return True
        raw = str(getattr(place, "opening_hours_raw", "") or "").strip().lower()
        if not raw:
            return False
        if raw in {"24/7", "24 hours", "always", "open 24 hours"}:
            return True
        clock = departure_time.timetz().replace(tzinfo=None)
        weekday_names = ("mo", "tu", "we", "th", "fr", "sa", "su")
        for part in raw.replace(";", ",").split(","):
            if "-" not in part or ":" not in part:
                continue
            day_and_times = part.rsplit(" ", 1)
            times = day_and_times[-1]
            day_expression = day_and_times[0] if len(day_and_times) == 2 else ""
            if day_expression and not RouteService._opening_day_matches(
                day_expression,
                departure_time.weekday(),
                weekday_names,
            ):
                continue
            start, end = times.split("-", 1)
            try:
                start_time = datetime.strptime(start.strip(), "%H:%M").time()
                end_time = (
                    datetime.strptime(end.strip(), "%H:%M").time()
                    if end.strip() != "24:00"
                    else datetime.max.time()
                )
            except ValueError:
                continue
            if start_time <= end_time and start_time <= clock <= end_time:
                return True
            if start_time > end_time and (clock >= start_time or clock <= end_time):
                return True
        return False

    @staticmethod
    def _opening_day_matches(
        expression: str,
        weekday: int,
        weekday_names: tuple[str, ...],
    ) -> bool:
        """Sprawdza prosty zapis dni OSM, np. ``Mo-Fr`` albo ``Sa,Su``."""

        normalized = expression.lower().replace(" ", "")
        for item in normalized.split(","):
            if "-" in item:
                start, end = item.split("-", 1)
                if start in weekday_names and end in weekday_names:
                    start_index = weekday_names.index(start)
                    end_index = weekday_names.index(end)
                    if start_index <= end_index and start_index <= weekday <= end_index:
                        return True
                    if start_index > end_index and (
                        weekday >= start_index or weekday <= end_index
                    ):
                        return True
            elif item in weekday_names and weekday_names.index(item) == weekday:
                return True
        return False

    @staticmethod
    def _road_type_score(road_type: object) -> float | None:
        value = str(road_type or "").lower()
        if not value:
            return None
        return {
            "pedestrian": 1.0,
            "footway": 0.9,
            "path": 0.7,
            "residential": 0.7,
            "service": 0.5,
            "steps": 0.3,
        }.get(value, 0.5)

    @staticmethod
    def _stairs_score(road_type: object) -> float | None:
        value = str(road_type or "").lower()
        return 0.0 if value in {"steps", "stairway"} else (1.0 if value else None)

    @staticmethod
    def _access_score(road_type: object) -> float | None:
        value = str(road_type or "").lower()
        if not value:
            return None
        if value in {"private", "no", "restricted"}:
            return 0.0
        return 1.0

    @staticmethod
    def _surface_score(surface: object) -> float | None:
        value = str(surface or "").lower()
        if not value:
            return None
        return {
            "paved": 1.0,
            "asphalt": 1.0,
            "concrete": 0.95,
            "sett": 0.8,
            "cobblestone": 0.65,
            "unpaved": 0.45,
            "gravel": 0.4,
            "ground": 0.3,
            "sand": 0.2,
        }.get(value, 0.5)

    @staticmethod
    def _incline_score(incline: object) -> float | None:
        if incline is None:
            return None
        try:
            percentage = abs(float(incline))
        except (TypeError, ValueError):
            return None
        return max(0.0, 1.0 - min(percentage / 15.0, 1.0))

    @staticmethod
    def _crossing_score(crossing: object) -> float | None:
        value = str(crossing or "").lower()
        if not value:
            return None
        return {
            "traffic_signals": 0.85,
            "marked": 0.7,
            "unmarked": 0.4,
            "no": 0.5,
        }.get(value, 0.5)

    @classmethod
    def _mapbox_candidate(
        cls,
        route: object,
        segments: tuple[RoadGraphSegment, ...],
    ) -> CandidateRoute:
        route_geometry = tuple(route.geometry)
        metric_route = cls._metric_line(route_geometry)
        matched = tuple(
            (segment.safety, segment.geometry)
            for segment in segments
            if metric_route.buffer(25.0).intersects(
                cls._metric_line(segment.geometry)
            )
        )
        return CandidateRoute(
            route_id=f"mapbox-{route.route_index}",
            geometry=route_geometry,
            duration_s=route.duration_s,
            distance_m=route.distance_m,
            segments=tuple(safety for safety, _ in matched)
            or (cls._fallback_segment(route.distance_m),),
            segment_geometries=(
                tuple(geometry for _, geometry in matched) or (route_geometry,)
            ),
        )

    @staticmethod
    def _local_candidate(
        index: int,
        route: object,
        segments: tuple[RoadGraphSegment, ...],
    ) -> CandidateRoute:
        by_id = {segment.segment_id: segment.safety for segment in segments}
        return CandidateRoute(
            route_id=f"local-{index}",
            geometry=route.geometry,
            duration_s=route.duration_s,
            distance_m=route.distance_m,
            segments=tuple(by_id[segment_id] for segment_id in route.segment_ids),
            segment_geometries=route.segment_geometries,
        )

    @staticmethod
    def _fallback_segment(distance_m: float) -> SegmentSafetyInput:
        return SegmentSafetyInput(
            length_m=max(distance_m, 1.0),
            lit_ratio=None,
            reports_nearby=0,
            tunnel_m=0.0,
            safe_place_distance_m=None,
            is_footway=None,
            surveillance_nearby=None,
            crime_exposure=None,
        )

    @staticmethod
    def _unique_candidates(candidates: list[CandidateRoute]) -> list[CandidateRoute]:
        unique: list[CandidateRoute] = []
        seen: set[tuple[tuple[float, float], ...]] = set()
        for candidate in candidates:
            if candidate.geometry not in seen:
                unique.append(candidate)
                seen.add(candidate.geometry)
        return unique

    @staticmethod
    def _score_candidates(
        candidates: list[CandidateRoute],
        request: RouteRequest,
    ) -> tuple[ScoredCandidateRoute, ...]:
        profiles, normalization = load_scoring_config()
        context = build_route_time_context(request.departure_time)
        weights = profiles[request.profile][context.period]
        return score_candidate_routes(
            candidates,
            weights,
            normalization,
            request.safety_weight,
            context.period,
        )

    @staticmethod
    def _to_response(route: ScoredCandidateRoute) -> RouteOption:
        coordinates = list(route.candidate.geometry)
        components = RouteComponents(
            lit_ratio=(
                sum(segment.lit_ratio for segment in route.candidate.segments if segment.lit_ratio is not None)
                / max(sum(segment.lit_ratio is not None for segment in route.candidate.segments), 1)
                if any(segment.lit_ratio is not None for segment in route.candidate.segments)
                else None
            ),
            reports_nearby=sum(segment.reports_nearby for segment in route.candidate.segments),
            reports_impact=sum(
                segment.reports_impact or segment.reports_nearby
                for segment in route.candidate.segments
            ),
            crime_exposure=(
                sum(
                    segment.crime_exposure or 0.0
                    for segment in route.candidate.segments
                )
                if any(segment.crime_exposure is not None for segment in route.candidate.segments)
                else None
            ),
            tunnel_m=sum(segment.tunnel_m for segment in route.candidate.segments),
            safe_places_nearby=sum(
                segment.safe_place_distance_m is not None
                and segment.safe_place_distance_m <= 500
                for segment in route.candidate.segments
            ),
            cameras_nearby=sum(
                segment.camera_count for segment in route.candidate.segments
            ),
            surface_score=_average_optional(
                segment.surface_score for segment in route.candidate.segments
            ),
            incline_score=_average_optional(
                segment.incline_score for segment in route.candidate.segments
            ),
            crossing_score=_average_optional(
                segment.crossing_score for segment in route.candidate.segments
            ),
            road_type_score=_average_optional(
                segment.road_type_score for segment in route.candidate.segments
            ),
            stairs_score=_average_optional(
                segment.stairs_score for segment in route.candidate.segments
            ),
            access_score=_average_optional(
                segment.access_score for segment in route.candidate.segments
            ),
        )
        segment_responses = [
            RouteSegment(
                geometry=GeoJSONLineString(
                    coordinates=list(segment_geometry),
                ),
                risk_level=max(0.0, min(100.0, 100.0 - score.score)),
            )
            for segment_geometry, score in zip(
                route.candidate.segment_geometries or (tuple(coordinates),),
                route.score.segment_scores,
            )
        ]
        return RouteOption(
            geometry=GeoJSONLineString(coordinates=coordinates),
            duration_s=route.candidate.duration_s,
            distance_m=route.candidate.distance_m,
            safety_score=route.safety_score,
            components=components,
            segments=segment_responses,
            explanation=RouteService._build_explanation(route, components),
        )

    @staticmethod
    def _build_explanation(
        route: ScoredCandidateRoute,
        components: RouteComponents,
    ) -> str:
        """Buduje krótkie, konkretne wyjaśnienie wyniku trasy."""

        strengths: list[str] = []
        risks: list[str] = []
        if components.lit_ratio is not None and components.lit_ratio >= 0.7:
            strengths.append(f"good lighting ({components.lit_ratio:.0%})")
        if components.cameras_nearby:
            strengths.append(f"{components.cameras_nearby} nearby cameras")
        if components.safe_places_nearby:
            strengths.append(f"{components.safe_places_nearby} segments near safe places")
        if components.reports_impact:
            risks.append(f"report impact {components.reports_impact:.1f}")
        if components.crime_exposure:
            risks.append(f"crime exposure {components.crime_exposure:.2f}")
        if components.tunnel_m:
            risks.append(f"{components.tunnel_m:.0f} m in tunnels")
        if components.stairs_score is not None and components.stairs_score < 0.5:
            risks.append("stairs or difficult access")
        if components.surface_score is not None and components.surface_score < 0.5:
            risks.append("poor surface quality")
        details = []
        if strengths:
            details.append("strengths: " + ", ".join(strengths))
        if risks:
            details.append("risks: " + ", ".join(risks))
        if not details:
            details.append("no dominant positive or negative factor detected")
        return (
            f"Safety score {route.safety_score:.1f}/100; "
            f"data coverage {route.score.data_coverage:.0%}; "
            + "; ".join(details)
            + "."
        )
