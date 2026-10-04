from geoalchemy2 import Geography
from geoalchemy2.shape import to_shape
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.road_segment import RoadSegment
from app.models.safe_place import SafePlace
from app.repositories.base_repository import BaseRepository
from app.schemas.road_segment import RoadSegmentDTO
from app.spatial import metric_route_corridor


class RoadSegmentRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    @staticmethod
    def _safe_place_distance_query():
        return (
            select(
                func.min(
                    func.ST_Distance(
                        cast(RoadSegment.geom, Geography(srid=4326)),
                        cast(SafePlace.geom, Geography(srid=4326)),
                    )
                )
            )
            .select_from(SafePlace)
            .correlate(RoadSegment)
            .scalar_subquery()
        )

    async def list_with_safety_data(self) -> list[RoadSegmentDTO]:
        """Zwraca segmenty z aktualną odległością do najbliższego safe place."""

        result = await self.session.execute(
            select(
                RoadSegment,
                self._safe_place_distance_query().label("dist_to_safe_place_m"),
            ).order_by(RoadSegment.id)
        )
        return [
            self._to_dto(segment, distance)
            for segment, distance in result.all()
        ]

    async def get_safety_data_by_ids(
        self,
        segment_ids: list[int],
    ) -> list[RoadSegmentDTO]:
        """Zwraca wybrane segmenty z odległością liczoną dla bieżących danych."""

        if not segment_ids:
            return []
        result = await self.session.execute(
            select(
                RoadSegment,
                self._safe_place_distance_query().label("dist_to_safe_place_m"),
            )
            .where(RoadSegment.id.in_(segment_ids))
            .order_by(RoadSegment.id)
        )
        return [
            self._to_dto(segment, distance)
            for segment, distance in result.all()
        ]

    @staticmethod
    def _to_dto(
        segment: RoadSegment,
        distance: float | None,
    ) -> RoadSegmentDTO:
        return RoadSegmentDTO(
            id=segment.id,
            osm_way_id=segment.osm_way_id,
            geometry_wkt=to_shape(segment.geom).wkt,
            length_m=segment.length_m,
            road_type=segment.road_type,
            is_tunnel=segment.is_tunnel,
            is_footway=segment.is_footway,
            source=segment.source,
            source_updated_at=segment.source_updated_at,
            dist_to_safe_place_m=distance,
        )

    async def get_by_id(
        self,
        segment_id: int,
    ) -> RoadSegment | None:
        stmt = select(RoadSegment).where(
            RoadSegment.id == segment_id
        )

        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_by_osm_way_id(
        self,
        osm_way_id: int,
    ) -> RoadSegment | None:
        stmt = (
            select(RoadSegment)
            .where(RoadSegment.osm_way_id == osm_way_id)
        )

        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_by_ids(
        self,
        segment_ids: list[int],
    ) -> list[RoadSegment]:
        if not segment_ids:
            return []

        stmt = select(RoadSegment).where(
            RoadSegment.id.in_(segment_ids)
        )

        result = await self.session.execute(stmt)

        return list(result.scalars().all())

    async def get_in_corridor(
        self,
        route_wkt: str,
        buffer_m: float = 3000.0,
    ) -> list[RoadSegment]:
        """Pobiera segmenty przecinające bufor metryczny wokół trasy."""

        corridor = metric_route_corridor(route_wkt, buffer_m)
        stmt = select(RoadSegment).where(func.ST_Intersects(RoadSegment.geom, corridor))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())