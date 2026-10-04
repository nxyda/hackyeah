"""Schematy requestów i odpowiedzi uwierzytelniania."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserDetails(BaseModel):
    """Dobrowolne podstawowe dane profilu użytkownika."""

    given_name: str | None = Field(default=None, max_length=100)
    family_name: str | None = Field(default=None, max_length=100)

    @field_validator("given_name", "family_name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class RegisterRequest(UserDetails):
    """Dane do utworzenia konta lokalnego."""

    email: EmailStr
    password: str = Field(min_length=12, max_length=1024)


class LoginRequest(BaseModel):
    """Dane wymagane do zalogowania użytkownika."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class OAuthLoginRequest(BaseModel):
    """Token dostawcy OAuth przesłany przez aplikację mobilną."""

    credential: str = Field(min_length=1, max_length=8192)


class AuthenticatedUser(BaseModel):
    """Publiczne dane użytkownika zwracane po rejestracji lub logowaniu OAuth."""

    id: int
    email: EmailStr
    given_name: str | None
    family_name: str | None


class RegistrationResponse(BaseModel):
    """Token dostępu wraz z podstawowymi danymi utworzonego konta."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: AuthenticatedUser


class TokenResponse(BaseModel):
    """Token dostępu JWT zwracany po poprawnym logowaniu."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
