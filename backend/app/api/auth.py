import re

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db import repository

router = APIRouter(prefix="/api")

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignUpRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def email_looks_valid(cls, value: str) -> str:
        if not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("Enter a valid email address.")
        return value.lower()


def current_user(authorization: str | None = Header(default=None)) -> dict:
    """Find the signed-in user from an 'Authorization: Bearer <token>' header."""
    scheme, _, token = (authorization or "").partition(" ")
    user = None

    if scheme.lower() == "bearer" and token:
        user = repository.get_user_by_token(token)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


@router.post("/users", status_code=201)
def create_user(body: SignUpRequest):
    user, token = repository.create_user(body.name, body.email)
    return {"user": user, "token": token}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return user