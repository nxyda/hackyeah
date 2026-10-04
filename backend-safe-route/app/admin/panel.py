"""Panel SQLAdmin do zarządzania encjami aplikacji."""

import asyncio
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine
from sqladmin import Admin, BaseView, ModelView, expose
from sqladmin.authentication import AuthenticationBackend
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from wtforms import (
    BooleanField,
    FloatField,
    Form,
    PasswordField,
    SelectField,
    StringField,
    TextAreaField,
    validators,
)
from wtforms.widgets import NumberInput

from app.config import get_settings
from app.database.session import SessionFactory
from app.enums.user_role import UserRole
from app.integrations.mapbox_directions_client import MapboxDirectionsError
from app.models.camera import Camera
from app.models.crime_event import CrimeEvent
from app.models.location_share import LocationShare
from app.models.report import Report
from app.models.report_confirmation import ReportConfirmation
from app.models.road_segment import RoadSegment
from app.models.safe_place import SafePlace
from app.models.street_lamp import StreetLamp
from app.models.user import User
from app.models.user_identity import UserIdentity
from app.repositories.user_repository import UserRepository
from app.schemas.route import RouteRequest
from app.services.auth_service import password_hasher
from app.services.route_service import RouteService, RouteUnavailableError

logger = logging.getLogger(__name__)
_dummy_password_hash = password_hasher.hash(secrets.token_urlsafe(32))


class GeometryWKTField(TextAreaField):
    """Edytuje kolumny PostGIS jako standardowy tekst WKT."""

    def _value(self) -> str:
        if self.raw_data:
            return str(self.raw_data[0])
        if self.data is None:
            return ""
        return to_shape(self.data).wkt


class DecimalNumberField(FloatField):
    """Pole numeryczne akceptujące wartości zmiennoprzecinkowe."""

    widget = NumberInput(step="any")


class AdminAuthenticationBackend(AuthenticationBackend):
    """Sesja SQLAdmin dostępna wyłącznie dla aktywnych kont administratorów."""

    def __init__(self, secret_key: str, *, https_only: bool) -> None:
        super().__init__(secret_key)
        self.middlewares = [
            Middleware(
                SessionMiddleware,
                secret_key=secret_key,
                https_only=https_only,
                same_site="lax",
            )
        ]

    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = str(form.get("username", "")).strip().lower()
        password = str(form.get("password", ""))
        if not email or not password:
            return False

        async with SessionFactory() as session:
            user = await UserRepository(session).get_by_email(email)
            stored_hash = (
                user.password_hash
                if user is not None and user.password_hash is not None
                else _dummy_password_hash
            )
            password_matches = await asyncio.to_thread(
                password_hasher.verify,
                password,
                stored_hash,
            )
            if (
                user is None
                or not user.is_active
                or user.role != UserRole.ADMIN
                or not password_matches
            ):
                logger.warning("Admin panel login rejected")
                return False
            request.session.clear()
            request.session["user_id"] = user.id
        logger.info("Admin panel login accepted user_id=%d", user.id)
        return True

    async def logout(self, request: Request) -> bool:
        user_id = request.session.get("user_id")
        request.session.clear()
        if isinstance(user_id, int):
            logger.info("Admin panel logout user_id=%d", user_id)
        return True

    async def authenticate(self, request: Request) -> bool:
        user_id = request.session.get("user_id")
        if not isinstance(user_id, int):
            return False
        async with SessionFactory() as session:
            user = await session.get(User, user_id)
        return bool(
            user is not None
            and user.is_active
            and user.role == UserRole.ADMIN
        )


async def _ensure_another_active_admin(user_id: int) -> None:
    async with SessionFactory() as session:
        result = await session.execute(
            select(User.id)
            .where(
                User.is_active.is_(True),
                User.role == UserRole.ADMIN,
            )
            .order_by(User.id)
            .with_for_update()
        )
        other_admins = [admin_id for admin_id in result.scalars().all() if admin_id != user_id]
    if not other_admins:
        raise ValueError("The last active administrator cannot be removed or demoted")


class UserAdmin(ModelView, model=User):
    name = "User"
    name_plural = "Users"
    column_list = [
        User.id,
        User.email,
        User.given_name,
        User.family_name,
        User.is_active,
        User.role,
        User.created_at,
    ]
    column_searchable_list = [User.email, User.given_name, User.family_name]
    column_details_list = [
        User.id,
        User.email,
        User.given_name,
        User.family_name,
        User.is_active,
        User.role,
        User.created_at,
        User.updated_at,
    ]
    form = type(
        "UserAdminForm",
        (Form,),
        {
            "email": StringField(
                "Email",
                validators=[
                    validators.DataRequired(),
                    validators.Email(),
                    validators.Length(max=320),
                ],
            ),
            "given_name": StringField(
                "Given name",
                validators=[validators.Optional(), validators.Length(max=100)],
            ),
            "family_name": StringField(
                "Family name",
                validators=[validators.Optional(), validators.Length(max=100)],
            ),
            "is_active": BooleanField("Active", default=True),
            "role": SelectField(
                "Role",
                choices=[(role.value, role.value.title()) for role in UserRole],
                default=UserRole.USER.value,
            ),
            "new_password": PasswordField(
                "Password (required on create; leave blank to keep unchanged)",
                validators=[
                    validators.Optional(),
                    validators.Length(min=12, max=1024),
                ],
            ),
        },
    )

    async def on_model_change(
        self,
        data: dict[str, Any],
        model: User,
        is_created: bool,
        request: Request,
    ) -> None:
        password = str(data.pop("new_password", "") or "")
        if is_created:
            if len(password) < 12:
                raise ValueError("A password with at least 12 characters is required")
        if password:
            data["password_hash"] = await asyncio.to_thread(
                password_hasher.hash,
                password,
            )
        if "role" in data:
            data["role"] = UserRole(data["role"])
        if is_created:
            return
        async with SessionFactory() as session:
            previous = await session.get(User, model.id)
        if (
            previous is not None
            and previous.is_active
            and previous.role == UserRole.ADMIN
            and (not model.is_active or model.role != UserRole.ADMIN)
        ):
            await _ensure_another_active_admin(model.id)

    async def on_model_delete(self, model: User, request: Request) -> None:
        if request.session.get("user_id") == model.id:
            raise ValueError("Administrators cannot delete their own account")
        if model.is_active and model.role == UserRole.ADMIN:
            await _ensure_another_active_admin(model.id)


class SpatialAdmin(ModelView):
    """Edytuje i pokazuje geometrię WKT razem z mapą Leaflet."""

    spatial_fields: tuple[str, ...] = ()
    spatial_geometry_type = "POINT"
    create_template = "admin/spatial_create.html"
    edit_template = "admin/spatial_edit.html"
    details_template = "admin/spatial_details.html"

    async def on_model_change(
        self,
        data: dict[str, Any],
        model: Any,
        is_created: bool,
        request: Request,
    ) -> None:
        for field in self.spatial_fields:
            value = data.get(field)
            if value is not None and str(value).strip():
                setattr(model, field, WKTElement(str(value).strip(), srid=4326))


class UserIdentityAdmin(ModelView, model=UserIdentity):
    name = "OAuth identity"
    name_plural = "OAuth identities"
    column_list = [
        UserIdentity.id,
        UserIdentity.user_id,
        UserIdentity.provider,
        UserIdentity.provider_user_id,
        UserIdentity.created_at,
    ]
    form_columns = [
        UserIdentity.user_id,
        UserIdentity.provider,
        UserIdentity.provider_user_id,
    ]


class ReportAdmin(SpatialAdmin, model=Report):
    name = "Report"
    name_plural = "Reports"
    spatial_fields = ("geom",)
    column_list = [
        Report.id,
        Report.user_id,
        Report.category,
        Report.status,
        Report.confirmations,
        Report.created_at,
        Report.expires_at,
    ]
    column_formatters = {
        Report.geom: lambda model, attribute: to_shape(model.geom).wkt,
    }
    column_formatters_detail = {
        Report.geom: lambda model, attribute: to_shape(model.geom).wkt,
    }
    column_searchable_list = [Report.user_id]
    form_columns = [
        Report.user_id,
        Report.category,
        Report.geom,
        Report.status,
        Report.confirmations,
        Report.expires_at,
    ]
    form_overrides = {"geom": GeometryWKTField}
    form_widget_args = {
        "geom": {"rows": 3, "placeholder": "POINT(21.01 52.23)"},
    }


class ReportConfirmationAdmin(ModelView, model=ReportConfirmation):
    name = "Report confirmation"
    name_plural = "Report confirmations"
    column_list = [
        ReportConfirmation.report_id,
        ReportConfirmation.user_id,
        ReportConfirmation.created_at,
    ]
    form_columns = [ReportConfirmation.report_id, ReportConfirmation.user_id]
    form_include_pk = True


class CameraAdmin(SpatialAdmin, model=Camera):
    name = "Camera"
    name_plural = "Cameras"
    spatial_fields = ("location",)
    column_list = [Camera.id, Camera.osm_id, Camera.location]
    column_formatters = {
        Camera.location: lambda model, attribute: to_shape(model.location).wkt,
    }
    column_formatters_detail = {
        Camera.location: lambda model, attribute: to_shape(model.location).wkt,
    }
    form_columns = [Camera.osm_id, Camera.location]
    form_overrides = {"location": GeometryWKTField}
    form_widget_args = {
        "location": {"rows": 3, "placeholder": "POINT(21.01 52.23)"},
    }


class CrimeEventAdmin(SpatialAdmin, model=CrimeEvent):
    name = "Crime event"
    name_plural = "Crime events"
    spatial_fields = ("geom",)
    column_list = [
        CrimeEvent.id,
        CrimeEvent.category,
        CrimeEvent.geom,
        CrimeEvent.occurred_at,
        CrimeEvent.source,
        CrimeEvent.severity,
    ]
    column_formatters = {
        CrimeEvent.geom: lambda model, attribute: to_shape(model.geom).wkt,
    }
    column_formatters_detail = {
        CrimeEvent.geom: lambda model, attribute: to_shape(model.geom).wkt,
    }
    form_columns = [
        CrimeEvent.category,
        CrimeEvent.geom,
        CrimeEvent.occurred_at,
        CrimeEvent.source,
        CrimeEvent.severity,
    ]
    form_overrides = {
        "geom": GeometryWKTField,
        "severity": DecimalNumberField,
    }
    form_widget_args = {
        "geom": {"rows": 3, "placeholder": "POINT(21.01 52.23)"},
    }


class RoadSegmentAdmin(SpatialAdmin, model=RoadSegment):
    name = "Road segment"
    name_plural = "Road segments"
    spatial_fields = ("geom",)
    spatial_geometry_type = "LINESTRING"
    column_list = [
        RoadSegment.id,
        RoadSegment.osm_way_id,
        RoadSegment.geom,
        RoadSegment.length_m,
        RoadSegment.road_type,
        RoadSegment.is_tunnel,
    ]
    column_formatters = {
        RoadSegment.geom: lambda model, attribute: to_shape(model.geom).wkt,
    }
    column_formatters_detail = {
        RoadSegment.geom: lambda model, attribute: to_shape(model.geom).wkt,
    }
    form_columns = [
        RoadSegment.osm_way_id,
        RoadSegment.geom,
        RoadSegment.length_m,
        RoadSegment.road_type,
        RoadSegment.is_tunnel,
        RoadSegment.is_footway,
        RoadSegment.source,
        RoadSegment.source_updated_at,
    ]
    form_overrides = {
        "geom": GeometryWKTField,
        "length_m": DecimalNumberField,
    }
    form_widget_args = {
        "geom": {
            "rows": 5,
            "placeholder": "LINESTRING(21.01 52.23, 21.02 52.24)",
        },
    }


class SafePlaceAdmin(SpatialAdmin, model=SafePlace):
    name = "Safe place"
    name_plural = "Safe places"
    spatial_fields = ("geom",)
    column_list = [
        SafePlace.id,
        SafePlace.osm_id,
        SafePlace.category,
        SafePlace.name,
        SafePlace.geom,
        SafePlace.is_24_7,
        SafePlace.source,
    ]
    column_formatters = {
        SafePlace.geom: lambda model, attribute: to_shape(model.geom).wkt,
    }
    column_formatters_detail = {
        SafePlace.geom: lambda model, attribute: to_shape(model.geom).wkt,
    }
    column_searchable_list = [SafePlace.name]
    form_columns = [
        SafePlace.osm_id,
        SafePlace.category,
        SafePlace.name,
        SafePlace.geom,
        SafePlace.opening_hours_raw,
        SafePlace.is_24_7,
        SafePlace.source,
        SafePlace.source_updated_at,
    ]
    form_overrides = {"geom": GeometryWKTField}
    form_widget_args = {
        "geom": {"rows": 3, "placeholder": "POINT(21.01 52.23)"},
    }


class StreetLampAdmin(SpatialAdmin, model=StreetLamp):
    name = "Street lamp"
    name_plural = "Street lamps"
    spatial_fields = ("location",)
    column_list = [StreetLamp.id, StreetLamp.osm_id, StreetLamp.location]
    column_formatters = {
        StreetLamp.location: lambda model, attribute: to_shape(model.location).wkt,
    }
    column_formatters_detail = {
        StreetLamp.location: lambda model, attribute: to_shape(model.location).wkt,
    }
    form_columns = [StreetLamp.osm_id, StreetLamp.location]
    form_overrides = {"location": GeometryWKTField}
    form_widget_args = {
        "location": {"rows": 3, "placeholder": "POINT(19.945 50.0647)"},
    }


class LocationShareAdmin(SpatialAdmin, model=LocationShare):
    name = "Location share"
    name_plural = "Location shares"
    spatial_fields = ("location",)
    can_create = False
    can_edit = False
    can_delete = False
    can_export = False
    column_list = [
        LocationShare.id,
        LocationShare.owner_user_id,
        LocationShare.code,
        LocationShare.location,
        LocationShare.created_at,
        LocationShare.updated_at,
        LocationShare.expires_at,
        LocationShare.revoked_at,
    ]
    column_details_list = column_list
    column_formatters = {
        LocationShare.location: lambda model, attribute: to_shape(model.location).wkt,
    }
    column_formatters_detail = {
        LocationShare.location: lambda model, attribute: to_shape(model.location).wkt,
    }
    form_columns = [LocationShare.location]
    form_overrides = {"location": GeometryWKTField}


class LocationShareOperationsAdmin(BaseView):
    """Monitors active location shares and lets admins revoke them safely."""

    name = "Location sharing"
    icon = "fa-solid fa-location-dot"

    @expose("/location-shares/operations", methods=["GET", "POST"])
    async def operations(self, request: Request) -> Response:
        if request.method == "POST":
            form = await request.form()
            submitted_token = str(form.get("csrf_token", ""))
            expected_token = request.session.get("location_share_csrf_token")
            if (
                not isinstance(expected_token, str)
                or not submitted_token
                or not secrets.compare_digest(submitted_token, expected_token)
            ):
                raise HTTPException(status_code=403, detail="Invalid CSRF token")

            try:
                share_id = int(str(form.get("share_id", "")))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid location share",
                ) from None
            if share_id <= 0:
                raise HTTPException(status_code=400, detail="Invalid location share")

            now = datetime.now(timezone.utc)
            async with SessionFactory() as session:
                result = await session.execute(
                    update(LocationShare)
                    .where(
                        LocationShare.id == share_id,
                        LocationShare.code.is_not(None),
                        LocationShare.revoked_at.is_(None),
                        LocationShare.expires_at > now,
                    )
                    .values(code=None, revoked_at=now)
                )
                if result.rowcount == 0:
                    raise HTTPException(
                        status_code=404,
                        detail="Active location share not found",
                    )
                await session.commit()

            return RedirectResponse(
                request.url_for("admin:operations").include_query_params(
                    result="revoked"
                ),
                status_code=303,
            )

        token = request.session.get("location_share_csrf_token")
        if not isinstance(token, str):
            token = secrets.token_urlsafe(32)
            request.session["location_share_csrf_token"] = token

        now = datetime.now(timezone.utc)
        async with SessionFactory() as session:
            result = await session.execute(
                select(
                    LocationShare.id.label("id"),
                    User.email.label("owner_email"),
                    LocationShare.code.label("code"),
                    func.ST_Y(LocationShare.location).label("latitude"),
                    func.ST_X(LocationShare.location).label("longitude"),
                    LocationShare.created_at.label("created_at"),
                    LocationShare.updated_at.label("updated_at"),
                    LocationShare.expires_at.label("expires_at"),
                )
                .join(User, User.id == LocationShare.owner_user_id)
                .where(
                    LocationShare.code.is_not(None),
                    LocationShare.revoked_at.is_(None),
                    LocationShare.expires_at > now,
                )
                .order_by(LocationShare.expires_at)
            )
            shares = result.all()

        return await self.templates.TemplateResponse(
            request,
            "admin/location_share_operations.html",
            {
                "shares": shares,
                "csrf_token": token,
                "result": request.query_params.get("result"),
            },
        )


class RoutePlannerAdmin(BaseView):
    """Lets administrators preview safety-scored routes without persisting them."""

    name = "Route planner"
    icon = "fa-solid fa-route"

    @expose("/routes", methods=["GET", "POST"], identity="routes")
    async def route_planner(self, request: Request) -> Response:
        defaults = {
            "start_lat": "50.0647",
            "start_lon": "19.9450",
            "end_lat": "50.0614",
            "end_lon": "19.9366",
            "departure_time": datetime.now().astimezone().isoformat(timespec="minutes"),
            "safety_weight": "0.5",
        }
        values = defaults.copy()
        error = None
        result = None
        token = request.session.get("route_planner_csrf_token")
        if not isinstance(token, str):
            token = secrets.token_urlsafe(32)
            request.session["route_planner_csrf_token"] = token

        if request.method == "POST":
            form = await request.form()
            values.update({key: str(form.get(key, "")) for key in defaults})
            submitted_token = str(form.get("csrf_token", ""))
            if (
                not submitted_token
                or not secrets.compare_digest(token, submitted_token)
            ):
                raise HTTPException(status_code=403, detail="Invalid CSRF token")

            try:
                route_request = RouteRequest.model_validate(
                    {
                        "start": {
                            "lat": values["start_lat"],
                            "lon": values["start_lon"],
                        },
                        "end": {
                            "lat": values["end_lat"],
                            "lon": values["end_lon"],
                        },
                        "departure_time": values["departure_time"],
                        "safety_weight": values["safety_weight"],
                        "profile": "walking",
                    }
                )
                if route_request.departure_time.utcoffset() is None:
                    raise ValueError("Departure time must include a timezone offset")
            except (ValidationError, ValueError) as exc:
                error = str(exc)
            else:
                async with SessionFactory() as session:
                    try:
                        route_result = await RouteService(session).calculate_route(route_request)
                    except (MapboxDirectionsError, RouteUnavailableError, ValueError) as exc:
                        error = str(exc)
                    else:
                        result = route_result.model_dump(mode="json")

        return await self.templates.TemplateResponse(
            request,
            "admin/route_planner.html",
            {
                "csrf_token": token,
                "values": values,
                "error": error,
                "result": result,
            },
        )


MODEL_VIEWS = (
    UserAdmin,
    UserIdentityAdmin,
    ReportAdmin,
    ReportConfirmationAdmin,
    CameraAdmin,
    CrimeEventAdmin,
    RoadSegmentAdmin,
    SafePlaceAdmin,
    StreetLampAdmin,
    LocationShareAdmin,
    LocationShareOperationsAdmin,
    RoutePlannerAdmin,
)


def register_admin_panel(app: FastAPI, engine: AsyncEngine) -> Admin | None:
    """Montuje SQLAdmin, jeśli skonfigurowano osobny klucz sesji panelu."""

    settings = get_settings()
    secret = settings.admin_session_secret.get_secret_value()
    if not secret:
        logger.warning("Admin panel disabled: ADMIN_SESSION_SECRET is not configured")
        return None
    if len(secret.encode("utf-8")) < 32:
        raise ValueError("ADMIN_SESSION_SECRET must contain at least 32 bytes")
    if secret == settings.jwt_secret_key.get_secret_value():
        raise ValueError("ADMIN_SESSION_SECRET must differ from JWT_SECRET_KEY")

    panel = Admin(
        app=app,
        engine=engine,
        base_url="/admin",
        title="Safe Route Admin",
        templates_dir=str(Path(__file__).parent / "templates"),
        authentication_backend=AdminAuthenticationBackend(
            secret_key=secret,
            https_only=settings.admin_cookie_secure,
        ),
    )
    for view in MODEL_VIEWS:
        panel.add_view(view)
    return panel
