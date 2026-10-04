"""Budowanie lokalnego grafu i wyszukiwanie zróżnicowanych tras."""

from dataclasses import dataclass
from math import cos, hypot, radians
from typing import Callable, Iterable, Literal

import networkx as nx
from app.scoring.scoring_models import SegmentSafetyInput
from app.scoring.scoring_models import NormalizationConfig, ScoringWeights
from app.scoring.route_scoring import calculate_segment_score


CoordinatePair = tuple[float, float]
GraphNode = tuple[float, float]


@dataclass(frozen=True)
class RoadGraphSegment:
    """Segment bazy używany jako krawędź lokalnego grafu."""

    segment_id: int
    geometry: tuple[CoordinatePair, ...]
    length_m: float
    safety: SegmentSafetyInput


@dataclass(frozen=True)
class LocalRoute:
    """Trasa znaleziona w lokalnym grafie."""

    segment_ids: tuple[int, ...]
    geometry: tuple[CoordinatePair, ...]
    distance_m: float
    duration_s: float
    segment_geometries: tuple[tuple[CoordinatePair, ...], ...]


# Lista ewaluatorów czynników bezpieczeństwa (krawędź -> ocena 0.0–1.0 lub None)
# Aby dodać nowy czynnik, wystarczy dopisać jedną linijkę do tej krotki!
SAFETY_FACTORS: tuple[Callable[[SegmentSafetyInput], float | None], ...] = (
    lambda s: s.lit_ratio,
    lambda s: 1.0 - min(s.reports_nearby / 5.0, 1.0),
    lambda s: (
        None
        if s.crime_exposure is None
        else 1.0 - min(s.crime_exposure / 5.0, 1.0)
    ),
    lambda s: 1.0 - min(s.tunnel_m / 100.0, 1.0),
    lambda s: (
        None
        if s.safe_place_distance_m is None
        else 1.0 - min(s.safe_place_distance_m / 250.0, 1.0)
    ),
    lambda s: float(s.is_footway) if s.is_footway is not None else 0.5,
    lambda s: float(s.surveillance_nearby) if s.surveillance_nearby is not None else 0.5,
)


def calculate_safety_score(
    safety: SegmentSafetyInput,
    weights: ScoringWeights | None = None,
    normalization: NormalizationConfig | None = None,
    period: Literal["day", "night"] = "night",
) -> float:
    """Oblicza uśrednioną ocenę bezpieczeństwa odcinka z aktywnych czynników."""
    if weights is not None and normalization is not None:
        return calculate_segment_score(
            safety, weights, normalization, period
        ).score / 100.0
    scores = [factor(safety) for factor in SAFETY_FACTORS]
    known = [val for val in scores if val is not None]
    return sum(known) / len(known) if known else 0.5


class LocalRouteFinder:
    """Wyszukuje trasy piesze po lokalnym grafie NetworkX."""

    walking_speed_m_s = 1.4
    node_snap_tolerance = 0.00015
    max_endpoint_snap_distance_m = 40.0

    def __init__(
        self,
        segments: Iterable[RoadGraphSegment],
        weights: ScoringWeights | None = None,
        normalization: NormalizationConfig | None = None,
        period: Literal["day", "night"] = "night",
    ) -> None:
        """Buduje graf z segmentów szosowych."""
        self.segments = tuple(segments)
        self.weights = weights
        self.normalization = normalization
        self.period = period
        self.graph = self._build_graph(self.segments)

    def _build_graph(self, segments: Iterable[RoadGraphSegment]) -> nx.MultiGraph:
        """Tworzy węzły i krawędzie grafu, scalając nakładające się punkty skrzyżowań."""
        graph = nx.MultiGraph()
        raw_edges: list[tuple[GraphNode, GraphNode, RoadGraphSegment]] = []

        for segment in segments:
            if len(segment.geometry) < 2:
                continue
            for left, right in zip(segment.geometry, segment.geometry[1:]):
                start, end = self._node(left), self._node(right)
                if start != end:
                    raw_edges.append((start, end, segment))

        if not raw_edges:
            return graph

        snapped = self._snap_nodes({node for edge in raw_edges for node in edge[:2]})
        for start, end, segment in raw_edges:
            snapped_start, snapped_end = snapped[start], snapped[end]
            if snapped_start != snapped_end:
                graph.add_edge(
                    snapped_start,
                    snapped_end,
                    key=segment.segment_id,
                    segment=segment,
                    geometry=(start, end),
                )
        return graph

    def find_routes(
        self,
        start: CoordinatePair,
        end: CoordinatePair,
        safety_weight: float,
        limit: int = 3,
    ) -> tuple[LocalRoute, ...]:
        """Zwraca do limitu zróżnicowanych tras z karą za wspólne krawędzie."""

        if not 0 <= safety_weight <= 1:
            raise ValueError("safety_weight must be between 0 and 1")
        if limit <= 0:
            raise ValueError("limit must be positive")
        if self.graph.number_of_edges() == 0:
            return ()

        source = self._nearest_node(start)
        target = self._nearest_node(end)
        if (
            self._distance_m(start, source) > self.max_endpoint_snap_distance_m
            or self._distance_m(end, target) > self.max_endpoint_snap_distance_m
        ):
            return ()
        if source == target:
            return ()

        routes: list[LocalRoute] = []
        penalized_ids: set[int] = set()

        for _ in range(limit):
            try:
                nodes = nx.shortest_path(
                    self.graph,
                    source,
                    target,
                    weight=lambda _u, _v, data: self._parallel_edge_cost(
                        data, safety_weight, penalized_ids
                    ),
                )
            except nx.NetworkXNoPath:
                break
            route = self._path_to_route(nodes, safety_weight, penalized_ids)

            if not route.segment_ids or route.segment_ids in {
                r.segment_ids for r in routes
            }:
                break

            routes.append(route)
            penalized_ids.update(route.segment_ids)

        return tuple(routes)

    def _edge_cost(
        self,
        data: dict[int, object],
        safety_weight: float,
        penalized_ids: set[int],
    ) -> float:
        """Oblicza koszt krawędzi uwzględniający dystans, bezpieczeństwo oraz karę za ponowne użycie."""
        segment = data["segment"]
        assert isinstance(segment, RoadGraphSegment)

        base_time = segment.length_m / self.walking_speed_m_s
        safety_penalty = 1.0 - calculate_safety_score(
            segment.safety,
            self.weights,
            self.normalization,
            self.period,
        )
        overlap_penalty = 2.5 if segment.segment_id in penalized_ids else 0.0

        return base_time * (1.0 + safety_weight * safety_penalty + overlap_penalty)

    def _parallel_edge_cost(
        self,
        data: dict[int, dict[str, object]],
        safety_weight: float,
        penalized_ids: set[int],
    ) -> float:
        """Zwraca najniższy koszt spośród równoległych krawędzi."""

        return min(
            self._edge_cost(edge, safety_weight, penalized_ids)
            for edge in data.values()
        )

    def _path_to_route(
        self,
        nodes: list[GraphNode],
        safety_weight: float,
        penalized_ids: set[int],
    ) -> LocalRoute:
        edges: list[
            tuple[RoadGraphSegment, tuple[CoordinatePair, CoordinatePair]]
        ] = []
        for left, right in zip(nodes, nodes[1:]):
            edge_options = self.graph.get_edge_data(left, right)
            if not edge_options:
                raise RuntimeError("graph path contains no edge")
            edge_data = min(
                edge_options.values(),
                key=lambda data: self._edge_cost(data, safety_weight, penalized_ids),
            )
            segment = edge_data["segment"]
            geometry = edge_data["geometry"]
            if not isinstance(geometry, tuple) or len(geometry) != 2:
                raise RuntimeError("graph edge contains invalid geometry")
            if self._distance(left, geometry[0]) > self._distance(left, geometry[1]):
                geometry = (geometry[1], geometry[0])
            edges.append((segment, geometry))

        coordinates: list[CoordinatePair] = []
        segment_geometries: list[tuple[CoordinatePair, ...]] = []
        distance = 0.0
        for segment, geometry_pair in edges:
            geometry = list(geometry_pair)
            if coordinates and coordinates[-1] != geometry[0]:
                coordinates.append(geometry[0])
            if coordinates and coordinates[-1] == geometry[0]:
                coordinates.extend(geometry[1:])
            else:
                coordinates.extend(geometry)
            segment_geometries.append(tuple(geometry))
            segment_length = sum(
                self._distance(left, right)
                for left, right in zip(segment.geometry, segment.geometry[1:])
            )
            edge_length = self._distance(*geometry_pair)
            distance += segment.length_m * edge_length / max(segment_length, 1e-12)

        return LocalRoute(
            segment_ids=tuple(segment.segment_id for segment, _ in edges),
            geometry=tuple(coordinates),
            distance_m=distance,
            duration_s=distance / self.walking_speed_m_s,
            segment_geometries=tuple(segment_geometries),
        )

    def _nearest_node(self, point: CoordinatePair) -> GraphNode:
        return min(self.graph.nodes, key=lambda node: self._distance(point, node))

    @staticmethod
    def _node(point: CoordinatePair) -> GraphNode:
        return round(point[0], 5), round(point[1], 5)

    @staticmethod
    def _snap_nodes(nodes: set[GraphNode]) -> dict[GraphNode, GraphNode]:
        """Scalaj końce segmentów rozjechane przez zaokrąglenia importu OSM."""

        tolerance = LocalRouteFinder.node_snap_tolerance
        buckets: dict[tuple[int, int], list[GraphNode]] = {}
        snapped: dict[GraphNode, GraphNode] = {}
        for node in sorted(nodes):
            bucket = (round(node[0] / tolerance), round(node[1] / tolerance))
            representative = next(
                (
                    candidate
                    for candidate in buckets.get(bucket, [])
                    if LocalRouteFinder._distance(node, candidate) <= tolerance
                ),
                None,
            )
            if representative is None:
                representative = node
                buckets.setdefault(bucket, []).append(node)
            snapped[node] = representative
        return snapped

    @staticmethod
    def _distance(left: CoordinatePair, right: CoordinatePair) -> float:
        return hypot(left[0] - right[0], left[1] - right[1])

    @staticmethod
    def _distance_m(left: CoordinatePair, right: CoordinatePair) -> float:
        """Szacuje odległość dwóch punktów WGS84 w metrach."""

        latitude_scale = 111_320.0
        longitude_scale = latitude_scale * cos(radians((left[1] + right[1]) / 2))
        return hypot(
            (left[0] - right[0]) * longitude_scale,
            (left[1] - right[1]) * latitude_scale,
        )
