"""Router agregujący endpointy wersji v1."""

from fastapi import APIRouter

from app.api.v1.auth_router import auth_router
from app.api.v1.admin_router import admin_router
from app.api.v1.location_share_router import location_share_router
from app.api.v1.report_router import report_router
from app.api.v1.safe_places_router import safe_place_router
from app.api.v1.camera_router import camera_router
from app.api.v1.crime_event_router import crime_event_router
from app.api.v1.street_lamp_router import street_lamp_router
from app.api.v1.route_router import route_router

v1_router = APIRouter()
v1_router.include_router(auth_router)
v1_router.include_router(admin_router)
v1_router.include_router(location_share_router)
v1_router.include_router(report_router)
v1_router.include_router(safe_place_router)
v1_router.include_router(camera_router)
v1_router.include_router(crime_event_router)
v1_router.include_router(street_lamp_router)
v1_router.include_router(route_router)