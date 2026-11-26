"""Authentication request and response schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.security import MAX_PASSWORD_BYTES


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=1, repr=False)

    @field_validator("username")
    @classmethod
    def _lower_case(cls, value: str) -> str:
        return value.lower()

    @field_validator("password")
    @classmethod
    def _at_most_72_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
        return value


class UserOut(BaseModel):
    id: int
    username: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = Field(default="bearer")
    expires_in: int
    user: UserOut


class MeResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    capabilities: list[str] = Field(
        description="Capability keys the role holds in the BP 10.2 role matrix, sorted. The UI "
        "decides what to show from these only; the API still enforces every check."
    )
