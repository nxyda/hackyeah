"""Location-sharing API scenarios using real local PostGIS persistence."""

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.location_share import LocationShare


@pytest.mark.integration
@pytest.mark.e2e
def test_owner_and_reader_location_share_lifecycle(
    run_with_postgis_test_database,
    monkeypatch: pytest.MonkeyPatch,
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

        monkeypatch.setattr(
            "app.services.location_share_service.secrets.choice",
            lambda available: "0000",
        )
        app.dependency_overrides[get_current_user] = current_user
        app.dependency_overrides[get_db] = test_database_session
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                created = await client.post(
                    "/v1/location-shares",
                    json={
                        "lat": 50.0614,
                        "lon": 19.9366,
                        "duration_seconds": 600,
                    },
                )
                assert created.status_code == 201, created.text
                share = created.json()
                assert share["code"] == "0000"
                assert share["expires_at"] > share["created_at"]

                duplicate = await client.post(
                    "/v1/location-shares",
                    json={
                        "lat": 50.0614,
                        "lon": 19.9366,
                        "duration_seconds": 600,
                    },
                )
                assert duplicate.status_code == 409

                principal.id = 2
                reader_result = await client.get(
                    f"/v1/location-shares/{share['code']}"
                )
                assert reader_result.status_code == 200
                assert reader_result.json()["owner_user_id"] == 1

                principal.id = 1
                owner_read = await client.get(
                    f"/v1/location-shares/{share['code']}"
                )
                current = await client.get("/v1/location-shares/current")
                assert owner_read.status_code == 404
                assert current.status_code == 200

                updated = await client.put(
                    "/v1/location-shares/current/location",
                    json={"lat": 50.07, "lon": 19.95},
                )
                assert updated.status_code == 200, updated.text
                assert updated.json()["code"] == share["code"]
                assert updated.json()["expires_at"] == share["expires_at"]

                principal.id = 2
                latest_location = await client.get(
                    f"/v1/location-shares/{share['code']}"
                )
                unauthorized_update = await client.put(
                    "/v1/location-shares/current/location",
                    json={"lat": 50.08, "lon": 19.96},
                )
                unauthorized_revoke = await client.delete(
                    "/v1/location-shares/current"
                )
                malformed_code = await client.get("/v1/location-shares/abcd")
                assert latest_location.json()["lat"] == pytest.approx(50.07)
                assert latest_location.json()["lon"] == pytest.approx(19.95)
                assert unauthorized_update.status_code == 404
                assert unauthorized_revoke.status_code == 404
                assert malformed_code.status_code == 422

                principal.id = 1
                revoked = await client.delete("/v1/location-shares/current")
                assert revoked.status_code == 204

                principal.id = 2
                after_revoke = await client.get(
                    f"/v1/location-shares/{share['code']}"
                )
                assert after_revoke.status_code == 404
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

        async with sessions() as session:
            expired_share = await session.scalar(
                select(LocationShare).where(LocationShare.code.is_(None))
            )
            active_share = await session.scalar(
                select(LocationShare).where(LocationShare.code == "0000")
            )
            reserved_code = await session.scalar(
                select(LocationShare).where(LocationShare.code == "0001")
            )
            assert expired_share is not None
            assert expired_share.owner_user_id == 1
            assert active_share is None
            assert reserved_code is not None
            assert reserved_code.owner_user_id == 3

    run_with_postgis_test_database(scenario)
