"""Repozytoria izolujące zapytania SQLAlchemy od serwisów."""
from app.repositories.camera_repository import CameraRepository
from app.repositories.crime_event_repository import CrimeEventRepository
from app.repositories.report_repository import ReportRepository
from app.repositories.road_segment_repository import RoadSegmentRepository
from app.repositories.safe_place_repository import SafePlaceRepository
from app.repositories.street_lamp_repository import StreetLampRepository
from app.repositories.user_repository import UserRepository

__all__ = [
    "CameraRepository",
    "CrimeEventRepository",
    "ReportRepository",
    "RoadSegmentRepository",
    "SafePlaceRepository",
    "StreetLampRepository",
    "UserRepository",
]