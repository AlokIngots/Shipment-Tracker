"""Create and manage the people who can sign in to the portal.

    python manage_users.py --list
    python manage_users.py --add-customer CODE --name "Company Ltd" [--country Germany]
    python manage_users.py --add-user EMAIL --customer CODE [--full-name "Jane Roe"]
    python manage_users.py --add-staff EMAIL [--full-name "Your Name"]
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

Alok Ingots staff
-----------------
    python manage_users.py --add-staff exports@alokindia.com --full-name "Export Desk"

A staff login belongs to no customer and sees no customer's orders. It sees
the staff pages instead, where documents are attached to shipments. Being
staff can only be granted here, on the server - there is no way to become
staff through the portal.

There is deliberately no web page for any of this. Nothing customer-facing can
create an account, so nothing customer-facing can be tricked into creating one.
"""

import argparse
from datetime import datetime, timezone

from app.core import security
from app.services import accounts
from app.core.database import SessionLocal
from app.models import Customer, Order, User
from sqlalchemy import func, select


# Every decision below is made in app/services/accounts.py, so this script
# and the Customers & logins screen in the admin console cannot drift apart
# in what they allow. This file parses arguments and prints; that one
# decides. AccountProblem carries the reason, already phrased for a person.

find_user = accounts.find_user
find_customer = accounts.find_customer


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


def do_list(session) -> int:
    """Every customer, who signs in for them, and the staff."""
    staff = accounts.staff_users(session)
    if staff:
        print("Alok Ingots staff")
        for user in staff:
            print(f"    {describe_user(user)}")
        print()

    rows = accounts.customers_with_logins(session)
    if not rows:
        print("No customers yet. Add one with --add-customer.")
        return 0

    for customer, users, order_count in rows:
        where = f", {customer.country}" if customer.country else ""
        print(f"{customer.code} - {customer.name}{where}   "
              f"({order_count} order(s))")
        if not users:
            print("    (nobody can sign in for this customer yet)")
        for user in users:
            print(f"    {describe_user(user)}")
        print()
    return 0


def describe_user(user) -> str:
    name = f" ({user.full_name})" if user.full_name else ""
    flags = []
    if not user.is_active:
        flags.append("DEACTIVATED")
    if user.must_change_password:
        flags.append("temporary password, not yet changed")
    suffix = f"   [{', '.join(flags)}]" if flags else ""
    return f"{user.email}{name}{suffix}"


def do_add_customer(session, args) -> int:
    if not args.name:
        print("! --add-customer also needs --name.")
        return 1
    code = args.add_customer.strip()

    if args.dry_run:
        print(f"Would add customer {code} - {args.name}")
        return 0

    customer = accounts.create_customer(session, code, args.name, args.country)
    print(f"Added customer {customer.code} - {customer.name}")
    print("Now give somebody a login for it:")
    print(f"  python -m scripts.manage_users --add-user EMAIL --customer {customer.code}")
    return 0


def do_add_staff(session, args) -> int:
    email = args.add_staff.strip().lower()
    if args.dry_run:
        print(f"Would add {email} as Alok Ingots staff,")
        print("and print a temporary password once.")
        return 0

    # Only reachable from here. There is no route in the API that creates a
    # staff account, on purpose: staff is the flag that unlocks every write
    # in the portal.
    user, password = accounts.create_staff_login(session, email, args.full_name)
    print(f"Added {user.email} as Alok Ingots staff.")
    announce(user.email, password)
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

    if args.dry_run:
        print(f"Would add {email} to {customer.code} - {customer.name},")
        print("and print a temporary password once.")
        return 0

    user, password = accounts.create_login(session, customer, email, args.full_name)
    print(f"Added {user.email} to {customer.code} - {customer.name}.")
    announce(user.email, password)
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

    password = accounts.reset_password(session, user)
    print(f"Reset the password for {user.email}.")
    announce(user.email, password)
    return 0


def set_active(session, args, email: str, active: bool) -> int:
    user = find_user(session, email.strip().lower())
    if user is None:
        print(f"! Nobody signs in as {email}. See --list.")
        return 1

    word = "let back in" if active else "locked out"
    if args.dry_run:
        print(f"Would have {user.email} {word}.")
        return 0

    # acting_user is None: run from the server, there is nobody to lock out
    # of a session, and somebody with a shell can always undo it.
    if not accounts.set_active(session, user, active):
        state = "active" if active else "deactivated"
        print(f"{user.email} is already {state}. Nothing to do.")
        return 0

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
    parser.add_argument("--add-staff", metavar="EMAIL",
                        help="give an Alok Ingots colleague a staff login")
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
                          args.add_staff, args.reset_password, args.deactivate,
                          args.activate) if a]
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
        if args.add_staff:
            return do_add_staff(session, args)
        if args.reset_password:
            return do_reset_password(session, args)
        if args.deactivate:
            return set_active(session, args, args.deactivate, False)
        if args.activate:
            return set_active(session, args, args.activate, True)

    return 0


def run() -> int:
    """main(), with the service's refusals printed the way this script always
    printed its own: one line, starting with '!', and a non-zero exit."""
    try:
        return main()
    except accounts.AccountProblem as problem:
        print(f"! {problem}")
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
