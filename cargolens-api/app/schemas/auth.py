import re
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.user import UserRole


class LoginRequest(BaseModel):
    email: str = Field(..., description="User corporate email address")
    password: str = Field(..., min_length=6, description="User password")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class TokenRefreshRequest(BaseModel):
    refresh_token: Optional[str] = Field(None, description="Optional refresh token string if not using cookie")


class UserResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class UserCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    role: UserRole = Field(default=UserRole.DOCUMENTATION_EXECUTIVE)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class ManagerBootstrapRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)
    bootstrap_secret: str = Field(..., description="Secret configured in server environment to allow bootstrap")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255, description="Full Name")
    email: EmailStr = Field(..., description="Corporate or work email address")
    password: str = Field(..., min_length=8, max_length=128, description="Secure corporate password")
    confirm_password: Optional[str] = Field(None, description="Password confirmation for validation")
    role: Optional[str] = Field(None, description="Requested role (must be omitted or DOCUMENTATION_EXECUTIVE)")

    model_config = ConfigDict(extra="ignore")

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError("Full Name must be at least 2 characters")
        return cleaned

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter (A-Z)")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter (a-z)")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit (0-9)")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_=+[\]\\/`~;']", v):
            raise ValueError("Password must contain at least one special character")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            normalized = v.strip().upper()
            if normalized in ("DOCUMENTATION_MANAGER", "MANAGER", "ADMIN", "SUPERUSER", "ADMINISTRATOR"):
                raise ValueError("Selecting or submitting Manager or Administrator roles during registration is strictly forbidden.")
            if normalized != UserRole.DOCUMENTATION_EXECUTIVE.value:
                raise ValueError(f"Invalid role '{v}'. Only DOCUMENTATION_EXECUTIVE is permitted for self-registration.")
        return v

    @model_validator(mode="after")
    def check_passwords_match(self) -> "RegisterRequest":
        if self.confirm_password is not None and self.confirm_password != self.password:
            raise ValueError("Confirm Password does not match Password")
        return self
