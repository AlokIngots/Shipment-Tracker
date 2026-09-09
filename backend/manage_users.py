"""Create and manage the people who can sign in to the portal.

    python manage_users.py --list
    python manage_users.py --add-customer CODE --name "Company Ltd" [--country Germany]
    python manage_users.py --add-user EMAIL --customer CODE [--full-name "Jane Roe"]
    python manage_users.py --reset-password EMAIL
    python manage_users.py --deactivate EMAIL
    python manage_users.py --activate EMAIL

Add --dry-run to any of these to see what would happen, changing nothing.

Until now the only accounts that existed came from .env through seed.py, which
is fine for two demo logins and no use at all for a real customer. This is how
a real one gets an account.

How a new customer is set up

    python manage_users.py --add-customer HANSA --name "Hansa Stahl GmbH" --country Germany
    python manage_users.py --add-user einkauf@hansa-stahl.de --customer HANSA

The second command prints a temporary password, once. Send it to the customer
the way you would send anything else confidential, and not in the same message
as the portal address. The first time they sign in, the portal makes them
choose their own password before it will show them anything.

There is deliberately no web page for any of this. Nothing customer-facing can
create an account, so nothing customer-facing can be tricked into creating one.
"""

import argparse
from datetime import datetime, timezone

import security
from database import SessionLocal
from models import Customer, Order, User
from sqlalchemy import func, select


def find_user(session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email.strip().lower()))


def find_customer(session, code: str) -> Customer | None:
    return session.scalar(select(Customer).where(Customer.code == code.strip()))


def announce(email: str, password: str) -> None:
    """Print a temporary password. The only time it is ever readable."""
    print()
    print(f"  Temporary password for {email}:")
    print()
    print(f"      {password}")
    print()
    print("  This is the only time it can be read. It is stored as a hash, so")
    print("  nobody, including the server, can look it up again. If it gets")
    print("  lost, run --reset-password and send a new one.")
    print()
    print("  Send it the way you would send anything else confidential, and")
    print("  not in the same message as the portal address. The portal makes")
    print("  them choose their own password before showing them any orders.")


# ------------------------------------------------------------------ actions


def do_list(session) -> int:
    """Show every customer, and who can sign in for them."""
    customers = session.scalars(select(Customer).order_by(Customer.code)).all()
    if not customers:
        print("No customers yet. Add one with --add-customer.")
        return 0

    without_logins = 0
    for customer in customers:
        orders = session.scalar(
            select(func.count(Order.id)).where(Order.customer_id == customer.id)
        )
        country = f", {customer.country}" if customer.country else ""
        print(f"\n{customer.code} - {customer.name}{country}   ({orders} order(s))")

        users = session.scalars(
            select(User).where(User.customer_id == customer.id).order_by(User.email)
        ).all()
        if not users:
            without_logins += 1
            print("    (nobody can sign in for this customer yet)")
            continue

        for user in users:
            flags = []
            if not user.is_active:
                flags.append("DEACTIVATED")
            if user.must_change_password:
                flags.append("temporary password, not yet changed")
            elif user.password_changed_at:
                flags.append(f"chose their password {user.password_changed_at:%d %b %Y}")
            suffix = f"   [{'; '.join(flags)}]" if flags else ""
            name = f" ({user.full_name})" if user.full_name else ""
            print(f"    {user.email}{name}{suffix}")

    if without_logins:
        print(f"\nNote: {without_logins} customer(s) above have nobody who can sign in.")
    return 0


def do_add_customer(session, args) -> int:
    code = args.add_customer.strip()
    if not args.name:
        print("! --add-customer also needs --name.")
        return 1
    if find_customer(session, code):
        print(f"! A customer with code {code} already exists. See --list.")
        return 1

    if args.dry_run:
        print(f"Would add customer {code} - {args.name}")
        return 0

    session.add(Customer(
        code=code,
        name=args.name.strip(),
        country=(args.country or "").strip() or None,
    ))
    session.commit()
    print(f"Added customer {code} - {args.name}")
    print("Now give somebody a login for it:")
    print(f"  python manage_users.py --add-user EMAIL --customer {code}")
    return 0


def do_add_user(session, args) -> int:
    email = args.add_user.strip().lower()
    if not args.customer:
        print("! --add-user also needs --customer CODE.")
        return 1

    customer = find_customer(session, args.customer)
    if customer is None:
        print(f"! No customer with code {args.customer}. Add it first, or see --list.")
        return 1
    if find_user(session, email):
        print(f"! {email} can already sign in.")
        print("  Use --reset-password to give them a new password.")
        return 1

    if args.dry_run:
        print(f"Would add {email} to {customer.code} - {customer.name},")
        print("and print a temporary password once.")
        return 0

    password = security.temporary_password()
    session.add(User(
        customer_id=customer.id,
        email=email,
        password_hash=security.hash_password(password),
        full_name=(args.full_name or "").strip() or None,
        is_active=True,
        must_change_password=True,
    ))
    session.commit()

    print(f"Added {email} to {customer.code} - {customer.name}.")
    announce(email, password)
    return 0


def do_reset_password(session, args) -> int:
    email = args.reset_password.strip().lower()
    user = find_user(session, email)
    if user is None:
        print(f"! Nobody signs in as {email}. See --list.")
        return 1

    if args.dry_run:
        print(f"Would give {email} a new temporary password.")
        return 0

    password = security.temporary_password()
    user.password_hash = security.hash_password(password)
    user.must_change_password = True
    # Stamping this now signs out anything already holding a token for this
    # account. A password is usually reset because somebody should not be
    # signed in any more, and leaving them signed in would defeat it.
    user.password_changed_at = datetime.now(timezone.utc).replace(microsecond=0)
    session.commit()

    print(f"Reset the password for {email}.")
    announce(email, password)
    return 0


def set_active(session, args, email: str, active: bool) -> int:
    user = find_user(session, email.strip().lower())
    if user is None:
        print(f"! Nobody signs in as {email}. See --list.")
        return 1

    if user.is_active == active:
        state = "active" if active else "deactivated"
        print(f"{user.email} is already {state}. Nothing to do.")
        return 0

    word = "let back in" if active else "locked out"
    if args.dry_run:
        print(f"Would have {user.email} {word}.")
        return 0

    user.is_active = active
    session.commit()
    print(f"{user.email} has been {word}.")
    if not active:
        print("This takes effect immediately, including for a token they already hold.")
    return 0


# --------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create and manage portal logins.",
    )
    parser.add_argument("--list", action="store_true",
                        help="show every customer and who can sign in")
    parser.add_argument("--add-customer", metavar="CODE",
                        help="add a customer (needs --name)")
    parser.add_argument("--name", help="the customer's name, with --add-customer")
    parser.add_argument("--country", help="the customer's country, with --add-customer")
    parser.add_argument("--add-user", metavar="EMAIL",
                        help="give somebody a login (needs --customer)")
    parser.add_argument("--customer", metavar="CODE",
                        help="which customer the new login belongs to")
    parser.add_argument("--full-name", help="the person's name, with --add-user")
    parser.add_argument("--reset-password", metavar="EMAIL",
                        help="issue a new temporary password")
    parser.add_argument("--deactivate", metavar="EMAIL",
                        help="stop somebody signing in")
    parser.add_argument("--activate", metavar="EMAIL",
                        help="let somebody sign in again")
    parser.add_argument("--dry-run", action="store_true",
                        help="show what would happen, change nothing")
    args = parser.parse_args()

    chosen = [a for a in (args.list, args.add_customer, args.add_user,
                          args.reset_password, args.deactivate, args.activate) if a]
    if len(chosen) != 1:
        parser.print_help()
        print("\n! Choose exactly one thing to do.")
        return 2

    if args.dry_run:
        print("Dry run - nothing will be changed.\n")

    with SessionLocal() as session:
        if args.list:
            return do_list(session)
        if args.add_customer:
            return do_add_customer(session, args)
        if args.add_user:
            return do_add_user(session, args)
        if args.reset_password:
            return do_reset_password(session, args)
        if args.deactivate:
            return set_active(session, args, args.deactivate, False)
        if args.activate:
            return set_active(session, args, args.activate, True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
