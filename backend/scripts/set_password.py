"""Set anybody's password on the server, typed in and never shown.

    python -m scripts.set_password --email you@alokindia.com

On the live server, from the project folder:

    docker compose -f docker-compose.prod.yml -f docker-compose.server.yml \\
        exec api python -m scripts.set_password --email you@alokindia.com

It asks for the new password twice. Nothing appears as you type, which is
on purpose: the password never reaches the screen, the shell history or any
log. Only its hash is stored.

This is the way in when email is down -- a staff member can set their own
password here and sign in with it straight away. It works for customer
logins too, though the admin console's Set password does the same thing
without needing the server.

The person is not made to change it afterwards: somebody chose it on
purpose. Every session they had open is signed out, and any sign-in link
already in their inbox stops working.
"""

import argparse
import getpass
import sys

from app.core import config, security
from app.core.database import SessionLocal
from app.services import accounts

TRIES = 3

EXAMPLE = (
    "example:\n"
    "  python -m scripts.set_password --email you@alokindia.com\n\n"
    "on the server:\n"
    "  docker compose -f docker-compose.prod.yml -f docker-compose.server.yml \\\n"
    "      exec api python -m scripts.set_password --email you@alokindia.com\n\n"
    f"The password must be at least {security.PASSWORD_MIN_LENGTH} characters. "
    "You are asked for it twice and nothing shows as you type."
)


def ask_for_password() -> str | None:
    """Ask twice, without echo. None after too many mistakes."""
    for attempt in range(1, TRIES + 1):
        first = getpass.getpass("  New password: ")
        problem = security.password_problem(first)
        if problem:
            print(f"! {problem.replace('Your password', 'The password')}")
            continue
        if getpass.getpass("  Type it again: ") != first:
            print("! The two did not match.")
            continue
        return first
    print(f"! Gave up after {TRIES} tries. Nothing was changed.")
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.set_password",
        description="Set the password for one portal login. "
        "Prompts for it; nothing is shown as you type.",
        epilog=EXAMPLE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--email", required=True, metavar="EMAIL",
                        help="the login to set the password for")
    args = parser.parse_args(argv)

    if not sys.stdin.isatty():
        # getpass would fall back to reading a visible line, or hang. With
        # docker compose exec that means -T was used; without it there is a
        # terminal.
        print("! This needs a terminal to type the password into. On the "
              "server, run it with docker compose exec (without -T).")
        return 2

    with SessionLocal() as session:
        user = accounts.find_user(session, args.email)
        if user is None:
            print(f"! No login for {args.email.strip().lower()}. "
                  "See who has one with: python -m scripts.manage_users --list")
            return 1

        kind = "staff login" if user.is_staff else "customer login"
        print(f"Setting the password for {user.email} ({kind}).")
        password = ask_for_password()
        if password is None:
            return 1

        accounts.set_password(session, user, password)

    print()
    print(f"  Done. {user.email} can sign in with this password now,")
    print(f"  at {config.PORTAL_URL}, and stays signed in for "
          f"{config.SESSION_TTL_DAYS} days.")
    print("  Anything they had open elsewhere has been signed out.")
    if not user.is_active:
        print()
        print("! This login is disabled, so the password opens nothing until")
        print(f"  it is enabled: python -m scripts.manage_users --activate {user.email}")
    if not config.PASSWORD_SIGN_IN:
        print()
        print("! Password sign-in is switched OFF on this server, so the")
        print("  password will not work yet. Set PASSWORD_SIGN_IN=true in .env")
        print("  and recreate the api container.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nStopped. Nothing was changed.")
        raise SystemExit(130)
