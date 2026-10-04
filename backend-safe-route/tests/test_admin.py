"""Testy dostępu administracyjnego i konfiguracji panelu."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.applications import Starlette
from sqladmin import Admin
from pydantic import SecretStr

from app.admin import panel as admin_panel
from app.api.v1.dependencies import get_current_admin_user, get_current_user
from app.admin.panel import (
    MODEL_VIEWS,
    CameraAdmin,
    CrimeEventAdmin,
    DecimalNumberField,
    LocationShareAdmin,
    ReportAdmin,
    RoadSegmentAdmin,
    RoutePlannerAdmin,
    StreetLampAdmin,
    UserAdmin,
    password_hasher,
)
from app.database.session import engine
from app.enums.user_role import UserRole
from app.main import app
from app.schemas.admin import AdminUserUpdate


def test_admin_dependency_rejects_regular_users() -> None:
    user = SimpleNamespace(role=UserRole.USER)

    with pytest.raises(HTTPException) as error:
        asyncio.run(get_current_admin_user(user))

    assert error.value.status_code == 403


def test_admin_dependency_accepts_administrator() -> None:
    user = SimpleNamespace(role=UserRole.ADMIN)

    assert asyncio.run(get_current_admin_user(user)) is user


def test_admin_user_update_requires_non_null_role_and_a_change() -> None:
    with pytest.raises(ValidationError):
        AdminUserUpdate.model_validate({})
    with pytest.raises(ValidationError):
        AdminUserUpdate.model_validate({"role": None})


def test_user_admin_form_has_a_password_field_but_no_hash_field() -> None:
    form = UserAdmin.form

    assert "new_password" in form.__dict__
    assert "password_hash" not in form.__dict__


def test_user_admin_hashes_password_and_requires_it_on_create() -> None:
    view = UserAdmin()
    model = SimpleNamespace()
    request = SimpleNamespace()
    form_data = {
        "email": "admin@example.com",
        "role": UserRole.ADMIN.value,
        "new_password": "a-long-new-password",
    }

    asyncio.run(view.on_model_change(form_data, model, True, request))

    assert "new_password" not in form_data
    assert password_hasher.verify("a-long-new-password", form_data["password_hash"])
    assert form_data["role"] == UserRole.ADMIN

    with pytest.raises(ValueError, match="password"):
        asyncio.run(
            view.on_model_change(
                {"email": "user@example.com", "new_password": ""},
                SimpleNamespace(),
                True,
                request,
            )
        )


def test_admin_api_requires_authentication() -> None:
    response = TestClient(app).get("/v1/admin/users")

    assert response.status_code == 401


def test_admin_password_api_requires_authentication() -> None:
    response = TestClient(app).put(
        "/v1/admin/users/42/password",
        json={"password": "a-long-new-password"},
    )

    assert response.status_code == 401


def test_admin_api_rejects_regular_users() -> None:
    user = SimpleNamespace(
        id=8,
        is_active=True,
        role=UserRole.USER,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = TestClient(app).get("/v1/admin/users")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_admin_panel_registers_crud_views_for_all_models() -> None:
    assert len(MODEL_VIEWS) == 12
    assert CameraAdmin.form_overrides["location"].__name__ == "GeometryWKTField"
    assert StreetLampAdmin.form_overrides["location"].__name__ == "GeometryWKTField"
    assert ReportAdmin.form_overrides["geom"].__name__ == "GeometryWKTField"
    assert LocationShareAdmin.can_create is False
    assert LocationShareAdmin.can_edit is False
    assert LocationShareAdmin.can_delete is False
    assert LocationShareAdmin.can_export is False


def test_admin_panel_can_build_forms_for_all_entities() -> None:
    async def build_forms() -> None:
        panel = Admin(Starlette(), engine=engine)
        for view_type in MODEL_VIEWS:
            panel.add_view(view_type)
        for view in panel._views:
            if view.is_model:
                await view.scaffold_form()

    asyncio.run(build_forms())


def test_admin_float_fields_render_as_decimal_number_inputs() -> None:
    async def check_float_fields() -> None:
        for view_type, field_names in (
            (CrimeEventAdmin, ("severity",)),
            (
                RoadSegmentAdmin,
                ("length_m",),
            ),
        ):
            view = view_type()
            form_type = await view.scaffold_form()
            form = form_type()
            for field_name in field_names:
                field = form[field_name]
                assert isinstance(field, DecimalNumberField)
                assert field.widget.input_type == "number"
                assert field.widget.step == "any"

    asyncio.run(check_float_fields())


def test_spatial_create_form_renders_map_and_wkt_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        admin_session_secret=SecretStr("test-admin-session-secret-at-least-32-bytes"),
        jwt_secret_key=SecretStr("a-different-test-jwt-secret-at-least-32-bytes"),
        admin_cookie_secure=False,
    )
    monkeypatch.setattr(admin_panel, "get_settings", lambda: settings)
    test_app = Starlette()
    sql_admin = admin_panel.register_admin_panel(test_app, engine)
    assert sql_admin is not None

    async def authenticated(_: object) -> bool:
        return True

    sql_admin.authentication_backend.authenticate = authenticated
    for template in (
        "admin/spatial_create.html",
        "admin/spatial_edit.html",
        "admin/spatial_details.html",
        "admin/location_share_operations.html",
        "admin/route_planner.html",
    ):
        sql_admin.templates.env.get_template(template)
    client = TestClient(test_app)
    spatial_forms = {
        "/admin/camera/create": ('data-geometry-type="POINT"', 'name="location"'),
        "/admin/report/create": ('data-geometry-type="POINT"', 'name="geom"'),
        "/admin/safe-place/create": ('data-geometry-type="POINT"', 'name="geom"'),
        "/admin/crime-event/create": ('data-geometry-type="POINT"', 'name="geom"'),
        "/admin/road-segment/create": ('data-geometry-type="LINESTRING"', 'name="geom"'),
        "/admin/street-lamp/create": ('data-geometry-type="POINT"', 'name="location"'),
    }
    for path, expected in spatial_forms.items():
        response = client.get(path)
        assert response.status_code == 200, path
        assert "data-spatial-map" in response.text
        assert "OpenStreetMap" in response.text
        assert "50.0647, 19.9450" in response.text
        assert all(value in response.text for value in expected), path

    assert "Lokalizacja na mapie" in response.text
    assert ReportAdmin.column_formatters_detail


def test_location_share_operations_list_and_revoke_require_csrf_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        admin_session_secret=SecretStr("test-admin-session-secret-at-least-32-bytes"),
        jwt_secret_key=SecretStr("a-different-test-jwt-secret-at-least-32-bytes"),
        admin_cookie_secure=False,
    )
    monkeypatch.setattr(admin_panel, "get_settings", lambda: settings)

    class StubSession:
        def __init__(self) -> None:
            self.committed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return None

        async def execute(self, statement):
            return SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(
                        id=1,
                        owner_email="owner@example.com",
                        code="1234",
                        latitude=50.06,
                        longitude=19.94,
                        updated_at="now",
                        expires_at="later",
                    )
                ],
                rowcount=1,
            )

        async def commit(self) -> None:
            self.committed = True

    stub_session = StubSession()
    monkeypatch.setattr(admin_panel, "SessionFactory", lambda: stub_session)
    test_app = Starlette()
    sql_admin = admin_panel.register_admin_panel(test_app, engine)
    assert sql_admin is not None
    client = TestClient(test_app)
    unauthenticated = client.get(
        "/admin/location-shares/operations",
        follow_redirects=False,
    )
    assert unauthenticated.status_code == 302
    assert unauthenticated.headers["location"].endswith("/admin/login")

    async def authenticated(_: object) -> bool:
        return True

    sql_admin.authentication_backend.authenticate = authenticated

    listing = client.get("/admin/location-shares/operations")
    assert listing.status_code == 200
    assert "owner@example.com" in listing.text
    csrf_token = listing.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]

    rejected = client.post(
        "/admin/location-shares/operations",
        data={"csrf_token": "invalid", "share_id": "1"},
    )
    assert rejected.status_code == 403
    assert stub_session.committed is False

    revoked = client.post(
        "/admin/location-shares/operations",
        data={"csrf_token": csrf_token, "share_id": "1"},
        follow_redirects=False,
    )
    assert revoked.status_code == 303
    assert revoked.headers["location"].endswith("?result=revoked")
    assert stub_session.committed is True


def test_route_planner_requires_csrf_and_shows_scored_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        admin_session_secret=SecretStr("test-admin-session-secret-at-least-32-bytes"),
        jwt_secret_key=SecretStr("a-different-test-jwt-secret-at-least-32-bytes"),
        admin_cookie_secure=False,
    )
    monkeypatch.setattr(admin_panel, "get_settings", lambda: settings)

    class StubSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return None

    monkeypatch.setattr(admin_panel, "SessionFactory", StubSession)
    request_calls = []

    class StubRouteService:
        def __init__(self, session) -> None:
            assert isinstance(session, StubSession)

        async def calculate_route(self, route_request):
            request_calls.append(route_request)
            return SimpleNamespace(
                model_dump=lambda mode: {
                    "fastest": {
                        "distance_m": 1200,
                        "duration_s": 900,
                        "safety_score": 72.5,
                        "explanation": "coverage 80%",
                        "geometry": {
                            "coordinates": [[19.945, 50.0647], [19.9366, 50.0614]]
                        },
                    },
                    "safest": {
                        "distance_m": 1300,
                        "duration_s": 1000,
                        "safety_score": 88.0,
                        "explanation": "coverage 95%",
                        "geometry": {
                            "coordinates": [[19.945, 50.0647], [19.9366, 50.0614]]
                        },
                    },
                    "alternatives": [],
                }
            )

    monkeypatch.setattr(admin_panel, "RouteService", StubRouteService)
    test_app = Starlette()
    sql_admin = admin_panel.register_admin_panel(test_app, engine)
    assert sql_admin is not None

    async def authenticated(_: object) -> bool:
        return True

    sql_admin.authentication_backend.authenticate = authenticated
    client = TestClient(test_app)
    listing = client.get("/admin/routes")
    assert listing.status_code == 200
    csrf_token = listing.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]

    payload = {
        "csrf_token": csrf_token,
        "start_lat": "50.0647",
        "start_lon": "19.9450",
        "end_lat": "50.0614",
        "end_lon": "19.9366",
        "departure_time": "2026-10-04T18:30+02:00",
        "safety_weight": "0.75",
    }
    rejected = client.post("/admin/routes", data={**payload, "csrf_token": "bad"})
    assert rejected.status_code == 403
    assert not request_calls

    response = client.post("/admin/routes", data=payload)
    assert response.status_code == 200
    assert "72.5/100" in response.text
    assert "route-map" in response.text
    assert len(request_calls) == 1
    assert (request_calls[0].start.lat, request_calls[0].start.lon) == (50.0647, 19.945)
    assert request_calls[0].safety_weight == 0.75
    assert request_calls[0].departure_time.utcoffset().total_seconds() == 7200
