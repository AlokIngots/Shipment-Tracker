"""Admin console: customer companies, and the people who may sign in.

Everything here was `scripts/manage_users.py` on the server until now. The
decisions still are: this router calls app/services/accounts.py, which the
script calls too, so a rule can only be changed in one place.

What is deliberately NOT here, and must not be added:

  * Creating a staff account. `accounts.create_staff_login` exists and the
    script calls it. Staff is the flag that unlocks every write in the
    portal, and the rule that granting it needs access to the server is
    worth more than a button. A staff member who could make more staff
    could not be un-made by anyone but themselves.
  * Deleting anything. An account is deactivated, never deleted, because a
    deleted login takes its history with it. Same rule the command line has
    always had.
"""

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.core.deps import ClientAddress, DbSession, StaffUser, bad_request, not_found
from app.models import Customer, User
from app.schemas import (
    ActiveIn,
    CustomerEditIn,
    CustomerIn,
    LoginIn,
    StaffAccountsOut,
    StaffCustomerAccountOut,
    StaffLoginOut,
    TemporaryPasswordOut,
)
from app.core.config import TRUST_PROXY_HEADER, TRUSTED_PROXY_HOPS
from app.services import accounts

router = APIRouter(prefix="/api/staff")


def refuse(problem: accounts.AccountProblem):
    """The service already phrased it for a person; pass it straight through."""
    return bad_request(str(problem))


def accounts_response(db) -> StaffAccountsOut:
    return StaffAccountsOut(
        customers=[
            StaffCustomerAccountOut(
                id=customer.id,
                code=customer.code,
                name=customer.name,
                country=customer.country,
                order_count=order_count,
                logins=[StaffLoginOut.model_validate(u) for u in logins],
            )
            for customer, logins, order_count in accounts.customers_with_logins(db)
        ],
        staff=[StaffLoginOut.model_validate(u) for u in accounts.staff_users(db)],
    )


def load_customer(customer_id: int, db) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise not_found("Customer not found.")
    return customer


def load_login(user_id: int, db) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("That login does not exist.")
    return user


@router.get("/accounts", response_model=StaffAccountsOut)
def staff_accounts(staff: StaffUser, db: DbSession) -> StaffAccountsOut:
    """Every customer, who can sign in for them, and the staff list."""
    return accounts_response(db)


@router.post("/customers", response_model=StaffAccountsOut, status_code=201)
def staff_create_customer(
    body: CustomerIn, staff: StaffUser, db: DbSession
) -> StaffAccountsOut:
    """Add a customer company. It has no logins until one is created for it."""
    try:
        accounts.create_customer(db, body.code, body.name, body.country, actor=staff)
    except accounts.AccountProblem as problem:
        raise refuse(problem) from problem
    return accounts_response(db)


@router.put("/customers/{customer_id}", response_model=StaffAccountsOut)
def staff_update_customer(
    customer_id: int, body: CustomerEditIn, staff: StaffUser, db: DbSession
) -> StaffAccountsOut:
    """Change a customer's name or country.

    Not the code: it is what the CSV importer matches on, so changing it
    here would quietly orphan every future import for that customer.
    """
    customer = load_customer(customer_id, db)
    try:
        accounts.update_customer(db, customer, body.name, body.country, actor=staff)
    except accounts.AccountProblem as problem:
        raise refuse(problem) from problem
    return accounts_response(db)


@router.post(
    "/customers/{customer_id}/logins",
    response_model=TemporaryPasswordOut,
    status_code=201,
)
def staff_create_login(
    customer_id: int, body: LoginIn, staff: StaffUser, db: DbSession
) -> TemporaryPasswordOut:
    """Give somebody a login for a customer.

    The temporary password comes back in this response and nowhere else,
    ever. Only its hash is stored. The portal then refuses to show that
    person a single order until they have replaced it.
    """
    customer = load_customer(customer_id, db)
    try:
        user, password = accounts.create_login(
            db, customer, body.email, body.full_name, actor=staff
        )
    except accounts.AccountProblem as problem:
        raise refuse(problem) from problem

    return TemporaryPasswordOut(
        detail=f"{user.email} can now sign in for {customer.code}.",
        email=user.email,
        temporary_password=password,
    )


@router.post("/logins/{user_id}/reset-password", response_model=TemporaryPasswordOut)
def staff_reset_password(
    user_id: int, staff: StaffUser, db: DbSession
) -> TemporaryPasswordOut:
    """Issue a new temporary password, and sign that account out everywhere."""
    user = load_login(user_id, db)
    password = accounts.reset_password(db, user, actor=staff)
    return TemporaryPasswordOut(
        detail=(
            f"{user.email} has a new temporary password, and every session "
            "they had open has been signed out."
        ),
        email=user.email,
        temporary_password=password,
    )


@router.post("/logins/{user_id}/active", response_model=StaffAccountsOut)
def staff_set_active(
    user_id: int, body: ActiveIn, staff: StaffUser, db: DbSession
) -> StaffAccountsOut:
    """Let somebody back in, or lock them out at once.

    Locking out takes effect immediately, including for a token they are
    already holding. The service refuses the two cases that would lock the
    admin console against everybody.
    """
    user = load_login(user_id, db)
    try:
        accounts.set_active(db, user, body.active, acting_user=staff)
    except accounts.AccountProblem as problem:
        raise refuse(problem) from problem
    return accounts_response(db)


@router.get("/whoami")
def staff_whoami(
    request: Request, staff: StaffUser, address: ClientAddress
) -> dict:
    """What the server thinks your address is, and how it worked that out.

    This exists because TRUSTED_PROXY_HOPS cannot be guessed. It depends on
    how many proxies sit in front of the API and what each of them does to
    X-Forwarded-For, which differs between a machine of its own and a
    machine shared with something else behind nginx. Get it wrong and every
    visitor looks like one address to the rate limiter, so one attacker
    locks out every customer at once -- and nothing about the portal looks
    broken until that happens.

    Open it as staff from the outside world and check that `client_address`
    is your own public address. If it is not, `forwarded_for` shows the
    chain and `hops_seen` says what to set TRUSTED_PROXY_HOPS to.

    Staff only, and it reveals nothing but the caller's own connection.
    """
    forwarded = request.headers.get("x-forwarded-for")
    hops = [h.strip() for h in (forwarded or "").split(",") if h.strip()]
    return {
        "client_address": address,
        "forwarded_for": forwarded,
        "hops_seen": len(hops),
        "trusted_proxy_hops": TRUSTED_PROXY_HOPS,
        "trust_proxy_header": TRUST_PROXY_HEADER,
        "direct_peer": request.client.host if request.client else None,
        "hint": (
            "client_address should be your own public IP. If it is not, set "
            "TRUSTED_PROXY_HOPS so that counting that many entries back from "
            "the end of forwarded_for lands on it."
        ),
    }
