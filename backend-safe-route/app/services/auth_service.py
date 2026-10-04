"""Logika uwierzytelniania użytkownika i wydawania tokenów dostępu."""

import asyncio
import secrets

from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError

from app.enums.oauth_provider import OAuthProvider
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    AuthenticatedUser,
    LoginRequest,
    RegisterRequest,
    RegistrationResponse,
    TokenResponse,
)
from app.security import AuthConfigurationError, create_access_token
from app.services.oauth_provider_service import verify_oauth_credential

password_hasher = PasswordHash.recommended()
_DUMMY_PASSWORD_HASH = password_hasher.hash(secrets.token_urlsafe(32))


class InvalidCredentialsError(Exception):
    """Podane dane logowania nie są poprawne."""


class DuplicateAccountError(Exception):
    """Adres e-mail jest już przypisany do innego konta."""


class AuthService:
    """Uwierzytelnia użytkowników przez repository i wystawia JWT."""

    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    async def login(self, credentials: LoginRequest) -> TokenResponse:
        """Weryfikuje hasło i wystawia krótko żyjący token dostępu."""

        email = str(credentials.email).strip().lower()
        user = await self.user_repository.get_by_email(email)
        stored_password_hash = (
            user.password_hash
            if user is not None and user.password_hash is not None
            else _DUMMY_PASSWORD_HASH
        )
        password_valid = await asyncio.to_thread(
            password_hasher.verify,
            credentials.password,
            stored_password_hash,
        )

        if user is None or not user.is_active or not password_valid:
            raise InvalidCredentialsError

        token, expires_in = create_access_token(user.id)

        return TokenResponse(
            access_token=token,
            expires_in=expires_in,
        )

    async def register(self, details: RegisterRequest) -> RegistrationResponse:
        """Tworzy konto lokalne, hashuje hasło i loguje nowego użytkownika."""

        email = str(details.email).strip().lower()
        if await self.user_repository.get_by_email(email) is not None:
            raise DuplicateAccountError

        try:
            user = await self.user_repository.create(
                email=email,
                password_hash=await asyncio.to_thread(password_hasher.hash, details.password),
                given_name=details.given_name,
                family_name=details.family_name,
            )
            response = self._registration_response(user)
            await self.user_repository.session.commit()
        except IntegrityError:
            await self.user_repository.session.rollback()
            if await self.user_repository.get_by_email(email) is not None:
                raise DuplicateAccountError from None
            raise
        return response

    async def login_with_oauth(
        self,
        provider: OAuthProvider,
        credential: str,
    ) -> RegistrationResponse:
        """Weryfikuje konto u dostawcy OAuth i loguje lub tworzy użytkownika."""

        profile = await verify_oauth_credential(provider, credential)
        user = await self.user_repository.get_by_identity(
            profile.provider,
            profile.provider_user_id,
        )
        if user is not None:
            if not user.is_active:
                raise InvalidCredentialsError
            return self._registration_response(user)

        email = profile.email.strip().lower()
        if await self.user_repository.get_by_email(email) is not None:
            raise DuplicateAccountError

        try:
            user = await self.user_repository.create(
                email=email,
                password_hash=None,
                given_name=profile.given_name,
                family_name=profile.family_name,
            )
            await self.user_repository.create_identity(
                user_id=user.id,
                provider=profile.provider,
                provider_user_id=profile.provider_user_id,
            )
            response = self._registration_response(user)
            await self.user_repository.session.commit()
        except IntegrityError:
            await self.user_repository.session.rollback()
            user = await self.user_repository.get_by_identity(
                profile.provider,
                profile.provider_user_id,
            )
            if user is not None and user.is_active:
                return self._registration_response(user)
            if await self.user_repository.get_by_email(email) is not None:
                raise DuplicateAccountError from None
            raise

        return self._registration_response(user)

    @staticmethod
    def _registration_response(user: User) -> RegistrationResponse:
        token, expires_in = create_access_token(user.id)
        return RegistrationResponse(
            access_token=token,
            expires_in=expires_in,
            user=AuthenticatedUser(
                id=user.id,
                email=user.email,
                given_name=user.given_name,
                family_name=user.family_name,
            ),
        )
