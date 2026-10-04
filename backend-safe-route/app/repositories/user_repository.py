# app/repositories/user_repository.py

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.oauth_provider import OAuthProvider
from app.models.user import User
from app.models.user_identity import UserIdentity
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(self, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)

        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(func.lower(User.email) == email.strip().lower())

        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_by_identity(
        self,
        provider: OAuthProvider,
        provider_user_id: str,
    ) -> User | None:
        stmt = (
            select(User)
            .join(UserIdentity, UserIdentity.user_id == User.id)
            .where(
                UserIdentity.provider == provider,
                UserIdentity.provider_user_id == provider_user_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        email: str,
        password_hash: str | None,
        given_name: str | None = None,
        family_name: str | None = None,
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            given_name=given_name,
            family_name=family_name,
        )

        self.session.add(user)

        await self.session.flush()

        return user

    async def create_identity(
        self,
        *,
        user_id: int,
        provider: OAuthProvider,
        provider_user_id: str,
    ) -> UserIdentity:
        identity = UserIdentity(
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
        )
        self.session.add(identity)
        await self.session.flush()
        return identity

    async def update(self, user: User) -> User:
        await self.session.flush()

        return user