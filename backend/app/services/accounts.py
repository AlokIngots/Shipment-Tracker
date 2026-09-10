"""Customers, and the people who may sign in for them.

This is the logic behind both `scripts/manage_users.py` and the admin
console's Customers & logins screen. It lived only in the script until the
screen existed; putting it here rather than importing a command-line tool
is the same move that was made for notifications, and for the same reason.

Nothing here prints, and nothing here raises an HTTPException. It raises
AccountProblem with a sentence a person can read, and the caller decides
whether that becomes a line on a terminal or a 400.

One thing this module deliberately does NOT offer to the web: creating a
staff account. `create_staff_login` exists and the script calls it; the
router does not, and must not. Staff is the flag that unlocks every write
in the portal, and the rule that it can only be granted by somebody with
access to the server is worth more than the convenience of a button.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core import security
from app.models import Customer, Order, User


class AccountProblem(Exception):
    """Something the caller asked for that cannot be done, in plain words."""


# ------------------------------------------------------------------ reading


def find_user(session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email.strip().lower()))


def find_customer(session, code: str) -> Customer | None:
    return session.scalar(select(Customer).where(Customer.code == code.strip()))


def customers_with_logins(session) -> list[tuple[Customer, list[User], int]]:
    """Every customer, who can sign in for them, and how many orders they have."""
    customers = list(
        session.scalars(
            select(Customer).options(selectinload(Customer.users)).order_by(Customer.name)
        )
    )
    counts = dict(
        session.execute(
            select(Order.customer_id, func.count(Order.id)).group_by(Order.customer_id)
        ).all()
    )
    return [
        (c, sorted(c.users, key=lambda u: u.email), counts.get(c.id, 0))
        for c in customers
    ]


def staff_users(session) -> list[User]:
    """Alok Ingots' own logins. They belong to no customer."""
    return list(
        session.scalars(
            select(User).where(User.is_staff.is_(True)).order_by(User.email)
        )
    )


def active_staff_count(session) -> int:
    return (
        session.scalar(
            select(func.count(User.id)).where(
                User.is_staff.is_(True), User.is_active.is_(True)
            )
        )
        or 0
    )


# ------------------------------------------------------------------ writing


def create_customer(session, code: str, name: str, country: str | None) -> Customer:
    """Add a customer company."""
    code = (code or "").strip()
    name = (name or "").strip()
    if not code:
        raise AccountProblem("A customer code is required.")
    if not name:
        raise AccountProblem("A customer name is required.")
    if find_customer(session, code):
        raise AccountProblem(f"A customer with code {code} already exists.")

    customer = Customer(
        code=code, name=name, country=(country or "").strip() or None
    )
    session.add(customer)
    session.commit()
    return customer


def update_customer(session, customer: Customer, name: str, country: str | None):
    """Change a customer's name or country.

    The code is deliberately not editable. It is the join between this
    portal and whatever SAP/PMS exports, and the CSV importer matches on it;
    changing it here would orphan every future import for that customer
    without anything appearing to go wrong.
    """
    name = (name or "").strip()
    if not name:
        raise AccountProblem("A customer name is required.")

    customer.name = name
    customer.country = (country or "").strip() or None
    session.commit()
    return customer


def create_login(
    session, customer: Customer, email: str, full_name: str | None
) -> tuple[User, str]:
    """Give somebody a login for a customer. Returns (user, temporary password).

    The password is returned once and never again: only its hash is stored,
    so nobody, including the server, can read it back.
    """
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise AccountProblem("That does not look like an email address.")
    if find_user(session, email):
        raise AccountProblem(
            f"{email} can already sign in. Reset their password instead of "
            "creating a second login."
        )

    password = security.temporary_password()
    user = User(
        customer_id=customer.id,
        email=email,
        password_hash=security.hash_password(password),
        full_name=(full_name or "").strip() or None,
        is_active=True,
        must_change_password=True,
    )
    session.add(user)
    session.commit()
    return user, password


def create_staff_login(
    session, email: str, full_name: str | None
) -> tuple[User, str]:
    """Give an Alok Ingots colleague a staff login.

    Called by scripts/manage_users.py only, never by a router. See the note
    at the top of this file: staff is the flag that unlocks every write in
    the portal, and granting it requires access to the server.
    """
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise AccountProblem("That does not look like an email address.")
    if find_user(session, email):
        raise AccountProblem(
            f"{email} can already sign in. A customer login cannot be turned "
            "into a staff one: they see different things, and mixing them up "
            "is how a customer ends up looking at somebody else's shipments."
        )

    password = security.temporary_password()
    user = User(
        customer_id=None,
        email=email,
        password_hash=security.hash_password(password),
        full_name=(full_name or "").strip() or None,
        is_active=True,
        is_staff=True,
        must_change_password=True,
    )
    session.add(user)
    session.commit()
    return user, password


def reset_password(session, user: User) -> str:
    """Put an account back on a fresh temporary password. Returns it once."""
    password = security.temporary_password()
    user.password_hash = security.hash_password(password)
    user.must_change_password = True
    # Stamping this now signs out anything already holding a token for this
    # account. A password is usually reset because somebody should not be
    # signed in any more, and leaving them signed in would defeat it.
    user.password_changed_at = datetime.now(timezone.utc).replace(microsecond=0)
    session.commit()
    return password


def set_active(session, user: User, active: bool, *, acting_user: User | None = None):
    """Let somebody in, or lock them out at once. Returns whether it changed.

    Two things it refuses, both of which lock somebody out of a portal that
    then cannot be unlocked from inside it:

      * deactivating the account you are signed in with
      * deactivating the last staff account that is still active
    """
    if not active and acting_user is not None:
        if user.id == acting_user.id:
            raise AccountProblem(
                "You cannot deactivate the account you are signed in with."
            )
        if user.is_staff and active_staff_count(session) <= 1:
            raise AccountProblem(
                "That is the last active staff account. Deactivating it would "
                "lock everybody out of the admin console, and only somebody "
                "with access to the server could undo it."
            )

    if user.is_active == active:
        return False

    user.is_active = active
    session.commit()
    return True
