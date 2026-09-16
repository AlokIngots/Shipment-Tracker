"""Signing in, and saying who you are."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    """Credentials submitted by the login form."""

    email: str
    password: str


class CustomerOut(BaseModel):
    """The customer a signed-in user belongs to."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    country: str | None


class LoginResponse(BaseModel):
    """Returned on a successful sign-in."""

    token: str
    email: str
    full_name: str | None
    # Null for staff, who belong to no customer.
    customer: CustomerOut | None
    # True when the user is still on the password staff gave them. The portal
    # shows nothing else until they have chosen their own.
    must_change_password: bool = False
    is_staff: bool = False


class MagicLinkRequest(BaseModel):
    """Asking for a sign-in link: an email address and nothing else."""

    email: str


class MagicLinkRedeem(BaseModel):
    """The token from a sign-in link, sent back to be spent."""

    token: str


class ChangePasswordRequest(BaseModel):
    """A user setting their own password."""

    current_password: str
    new_password: str


# ------------------------------------------------------- the customer's side
