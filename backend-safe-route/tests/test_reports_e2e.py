"""Report API scenarios backed by seeded local PostGIS data."""

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.enums.report import ReportCategory
from app.models.report import Report


@pytest.mark.integration
@pytest.mark.e2e
def test_nearby_reports_filter_by_active_status_expiry_and_distance(
    run_with_postgis_test_database,
) -> None:
    async def scenario(sessions: async_sessionmaker) -> None:
        from app.api.v1.dependencies import get_current_user
        from app.database.session import get_db
        from app.main import app

        async def current_user():
            return SimpleNamespace(id=1)

        async def test_database_session():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_current_user] = current_user
        app.dependency_overrides[get_db] = test_database_session
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get(
                    "/v1/reports/nearby",
                    params={"lat": 50.058, "lon": 19.936, "radius_m": 500},
                )

            assert response.status_code == 200, response.text
            rows = response.json()
            assert {row["category"] for row in rows} == {
                "danger",
                "poor_lighting",
            }
            assert all(row["status"] == "active" for row in rows)
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

    run_with_postgis_test_database(scenario)


@pytest.mark.integration
@pytest.mark.e2e
def test_report_crud_is_scoped_to_authenticated_owner(
    run_with_postgis_test_database,
) -> None:
    async def scenario(sessions: async_sessionmaker) -> None:
        from app.api.v1.dependencies import get_current_user
        from app.database.session import get_db
        from app.main import app

        principal = SimpleNamespace(id=1)

        async def current_user():
            return principal

        async def test_database_session():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_current_user] = current_user
        app.dependency_overrides[get_db] = test_database_session
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                created = await client.post(
                    "/v1/reports",
                    json={
                        "category": "blocked_path",
                        "lat": 50.0582,
                        "lon": 19.9362,
                    },
                )
                assert created.status_code == 201, created.text
                report_id = created.json()["id"]
                assert created.json()["lat"] == pytest.approx(50.0582)

                own_reports = await client.get("/v1/reports")
                assert own_reports.status_code == 200
                assert report_id in {row["id"] for row in own_reports.json()}
                assert all(
                    row["status"] in {"active", "resolved", "expired", "rejected"}
                    for row in own_reports.json()
                )

                principal.id = 2
                foreign_patch = await client.patch(
                    f"/v1/reports/{report_id}",
                    json={"category": "other"},
                )
                foreign_delete = await client.delete(f"/v1/reports/{report_id}")
                assert foreign_patch.status_code == 404
                assert foreign_delete.status_code == 404

                principal.id = 1
                updated = await client.patch(
                    f"/v1/reports/{report_id}",
                    json={
                        "category": "other",
                        "lat": 50.0583,
                        "lon": 19.9363,
                    },
                )
                assert updated.status_code == 200, updated.text
                assert updated.json()["category"] == "other"
                assert updated.json()["lat"] == pytest.approx(50.0583)

                deleted = await client.delete(f"/v1/reports/{report_id}")
                assert deleted.status_code == 204
                missing = await client.patch(
                    f"/v1/reports/{report_id}",
                    json={"category": "danger"},
                )
                assert missing.status_code == 404
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

    run_with_postgis_test_database(scenario)


@pytest.mark.integration
@pytest.mark.e2e
def test_report_confirmation_is_idempotent_and_rejects_ineligible_reports(
    run_with_postgis_test_database,
) -> None:
    async def scenario(sessions: async_sessionmaker) -> None:
        from app.api.v1.dependencies import get_current_user
        from app.database.session import get_db
        from app.main import app

        async with sessions() as session:
            own_report_id = await session.scalar(
                select(Report.id).where(
                    Report.user_id == 1,
                    Report.category == ReportCategory.DANGER,
                )
            )
            other_report_id = await session.scalar(
                select(Report.id).where(
                    Report.user_id == 2,
                    Report.category == ReportCategory.POOR_LIGHTING,
                )
            )
            expired_report_id = await session.scalar(
                select(Report.id).where(
                    Report.user_id == 2,
                    Report.category == ReportCategory.HARASSMENT,
                )
            )

        async def current_user():
            return SimpleNamespace(id=1)

        async def test_database_session():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_current_user] = current_user
        app.dependency_overrides[get_db] = test_database_session
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                first = await client.post(f"/v1/reports/{other_report_id}/confirm")
                second = await client.post(f"/v1/reports/{other_report_id}/confirm")
                self_confirmation = await client.post(
                    f"/v1/reports/{own_report_id}/confirm"
                )
                expired_confirmation = await client.post(
                    f"/v1/reports/{expired_report_id}/confirm"
                )

            assert first.status_code == 200, first.text
            assert second.status_code == 200, second.text
            assert first.json()["confirmations"] == 1
            assert second.json()["confirmations"] == 1
            assert self_confirmation.status_code == 404
            assert expired_confirmation.status_code == 404

            async with sessions() as session:
                report = await session.get(Report, other_report_id)
                assert report is not None
                assert report.confirmations == 1
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

    run_with_postgis_test_database(scenario)
