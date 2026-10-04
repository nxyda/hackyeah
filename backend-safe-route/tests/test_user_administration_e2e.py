"""Administrative API security flows backed by disposable local PostGIS."""

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker


TEST_JWT_SECRET = "user-admin-e2e-signing-key-that-is-32-bytes"


@pytest.mark.integration
@pytest.mark.e2e
def test_admin_api_protects_accounts_and_resets_passwords(
    run_with_postgis_test_database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario(sessions: async_sessionmaker) -> None:
        from app import security
        from app.database.session import get_db
        from app.enums.user_role import UserRole
        from app.main import app
        from app.models.user import User
        from app.services.auth_service import password_hasher

        monkeypatch.setattr(
            security,
            "get_settings",
            lambda: SimpleNamespace(
                jwt_secret_key=SecretStr(TEST_JWT_SECRET),
                jwt_access_token_expire_minutes=15,
                jwt_issuer="user-admin-e2e",
            ),
        )

        async with sessions() as session:
            admin = await session.scalar(
                select(User).where(User.email == "route-owner@example.com")
            )
            target = await session.scalar(
                select(User).where(User.email == "route-reader@example.com")
            )
            assert admin is not None
            assert target is not None
            admin.role = UserRole.ADMIN
            target.password_hash = password_hasher.hash("old-test-password-123")
            await session.commit()
            admin_id = admin.id
            target_id = target.id

        token, _ = security.create_access_token(admin_id)
        headers = {"Authorization": f"Bearer {token}"}

        async def test_database_session():
            async with sessions() as session:
                yield session

        app.dependency_overrides[get_db] = test_database_session
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as admin_client:
                listing = await admin_client.get(
                    "/v1/admin/users",
                    headers=headers,
                )
                assert listing.status_code == 200, listing.text
                listed_target = next(
                    user for user in listing.json() if user["id"] == target_id
                )
                assert listed_target["email"] == "route-reader@example.com"
                assert "password_hash" not in listed_target
                assert "password" not in listed_target

                updated = await admin_client.patch(
                    f"/v1/admin/users/{target_id}",
                    headers=headers,
                    json={"given_name": "Updated", "role": "admin"},
                )
                assert updated.status_code == 200, updated.text
                assert updated.json()["given_name"] == "Updated"
                assert updated.json()["role"] == "admin"
                assert "password_hash" not in updated.json()

                demoted_target = await admin_client.patch(
                    f"/v1/admin/users/{target_id}",
                    headers=headers,
                    json={"role": "user"},
                )
                assert demoted_target.status_code == 200

                last_admin_demotion = await admin_client.patch(
                    f"/v1/admin/users/{admin_id}",
                    headers=headers,
                    json={"role": "user"},
                )
                self_delete = await admin_client.delete(
                    f"/v1/admin/users/{admin_id}",
                    headers=headers,
                )
                assert last_admin_demotion.status_code == 409
                assert self_delete.status_code == 409

                password_reset = await admin_client.put(
                    f"/v1/admin/users/{target_id}/password",
                    headers=headers,
                    json={"password": "new-test-password-456"},
                )
                assert password_reset.status_code == 204
                assert password_reset.content == b""

                old_password = await admin_client.post(
                    "/v1/auth/login",
                    json={
                        "email": "route-reader@example.com",
                        "password": "old-test-password-123",
                    },
                )
                new_password = await admin_client.post(
                    "/v1/auth/login",
                    json={
                        "email": "route-reader@example.com",
                        "password": "new-test-password-456",
                    },
                )
                assert old_password.status_code == 401
                assert new_password.status_code == 200

                demoted_admin = await admin_client.patch(
                    f"/v1/admin/users/{admin_id}",
                    headers=headers,
                    json={"is_active": False},
                )
                assert demoted_admin.status_code == 409

                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as anonymous_client:
                    unauthorized = await anonymous_client.get("/v1/admin/users")
                assert unauthorized.status_code == 401

            async with sessions() as session:
                stored_admin = await session.get(User, admin_id)
                stored_target = await session.get(User, target_id)
                assert stored_admin is not None
                assert stored_admin.role is UserRole.ADMIN
                assert stored_admin.is_active is True
                assert stored_target is not None
                assert stored_target.role is UserRole.USER
                assert password_hasher.verify(
                    "new-test-password-456",
                    stored_target.password_hash,
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

    run_with_postgis_test_database(scenario)
