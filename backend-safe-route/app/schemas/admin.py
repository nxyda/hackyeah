"""Schematy bezpiecznych operacji administracyjnych."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.enums.user_role import UserRole


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    given_name: str | None
    family_name: str | None
    is_active: bool
    role: UserRole
    created_at: datetime
    updated_at: datetime


class AdminUserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
    given_name: str | None = Field(default=None, max_length=100)
    family_name: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def require_changes(self) -> "AdminUserUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        if "role" in self.model_fields_set and self.role is None:
            raise ValueError("Role cannot be null")
        if "is_active" in self.model_fields_set and self.is_active is None:
            raise ValueError("is_active cannot be null")
        return self


class AdminPasswordUpdate(BaseModel):
    password: str = Field(min_length=12, max_length=1024)
