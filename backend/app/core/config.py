"""Everything the portal reads from the environment, in one place.

Before this existed, four modules each worked out where the project root was
with ``Path(__file__).parent.parent`` and each called ``load_dotenv`` again.
That was quietly fragile: moving any one of those files one directory deeper
changed where it looked for ``.env``, and nothing would say so until a
setting silently came back empty.

Now the paths are worked out once, from this file's own known position, and
every setting is read here. A module that needs a setting imports it; no
module reads ``os.getenv`` for configuration on its own.

Nothing here has a default that would be dangerous in production: the two
settings that must never be guessed — the database address and the secret
key — refuse to be absent.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# This file is backend/app/core/config.py, so:
#   parents[0] backend/app/core   parents[1] backend/app
#   parents[2] backend            parents[3] the project root
BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# .env lives at the project root, beside docker-compose.yml. Loaded once.
load_dotenv(PROJECT_ROOT / ".env")


def _flag(name: str, default: str = "false") -> bool:
    """An environment variable read as a yes/no switch."""
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


# ------------------------------------------------------------------ database

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy .env.example to .env and fill it in."
    )


# ------------------------------------------------------------------ security

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise RuntimeError(
        "SECRET_KEY must be set in .env and at least 32 characters long. "
        'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
    )

TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", "43200"))  # 12 hours


# --------------------------------------------------------------- rate limits

# Nothing slowed down bulk password guessing before. These are deliberately
# generous for a real person -- five wrong passwords in a quarter of an hour
# is already a bad day -- and mean, a script.
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))

# The same address failing against many different accounts.
LOGIN_ADDRESS_MAX_ATTEMPTS = int(os.getenv("LOGIN_ADDRESS_MAX_ATTEMPTS", "20"))

LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "900"))     # 15 min
LOGIN_LOCKOUT_SECONDS = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "900"))   # 15 min

# How many keys the limiter will hold before it starts forgetting the least
# recently active. Somebody inventing a new email on every attempt must not
# be able to grow it until the container runs out of memory.
RATE_LIMIT_MAX_KEYS = int(os.getenv("RATE_LIMIT_MAX_KEYS", "10000"))

# How many entries at the END of X-Forwarded-For were put there by our own
# infrastructure, and are therefore the ones to look past to find the real
# client.
#
#   1  Caddy is the front door          XFF: "<client>"
#   2  nginx in front of Caddy          XFF: "<client>, <nginx>"
#
# Counting rather than pattern-matching, because it is the only thing that
# is true regardless of what addresses the proxies happen to have. Get it
# wrong and every visitor looks like the same address to the rate limiter:
# too low and one shared proxy address absorbs everybody's budget, too high
# and a caller can spend somebody else's by prepending their own header.
TRUSTED_PROXY_HOPS = max(1, int(os.getenv("TRUSTED_PROXY_HOPS", "1")))

# Whether to believe X-Forwarded-For. True is correct for this deployment:
# the api service publishes no ports, so Caddy is the only thing that can
# reach it, and the address Caddy appends is therefore the real one. Set it
# false if the API is ever exposed directly, or a caller could put any
# address it liked in the header and spend somebody else's budget.
TRUST_PROXY_HEADER = _flag("TRUST_PROXY_HEADER", "true")


# ----------------------------------------------------- sign-in by email link

# How long an emailed sign-in link works.
#
# 24 hours since 12 Sep 2026, on Alok's decision, replacing 15 minutes. The
# short window was correct on security grounds and wrong on practical ones:
# a customer who read the email the next morning found a dead link and had
# to work out for themselves that asking again was the answer.
#
# For as long as it lives the link is as good as a password and it is sitting
# in an inbox, so this is a real trade-off and not a free one. What limits
# the damage is that asking for a new link retires the old one, a password
# change or reset kills any link already sent, and only the newest link for
# an account ever works.
MAGIC_LINK_TTL_SECONDS = int(os.getenv("MAGIC_LINK_TTL_SECONDS", "86400"))  # 24 h

# Whether a link stops working the moment it is used.
#
# False, the default since 12 Sep 2026 on Alok's decision: the link keeps
# working until it expires, however many times it is opened.
#
# Set it true to go back to a link that is spent on first use. That is the
# safer setting, and it needs no code change and no deploy -- one environment
# variable and a restart of the api container, the same way PASSWORD_SIGN_IN
# works.
MAGIC_LINK_SINGLE_USE = _flag("MAGIC_LINK_SINGLE_USE")

# Asking for a link sends an email, so EVERY request is counted, not only
# failed ones -- otherwise anybody could fill a customer's inbox.
#
# Per inbox: past this many in the window, the same "check your email"
# answer comes back and nothing is sent. Deliberately not a 429, so the limit
# can never be used to ask whether an address has an account.
MAGIC_LINK_MAX_PER_EMAIL = int(os.getenv("MAGIC_LINK_MAX_PER_EMAIL", "3"))

# Per network address, across every inbox it asks for: past this, a 429.
MAGIC_LINK_MAX_PER_ADDRESS = int(os.getenv("MAGIC_LINK_MAX_PER_ADDRESS", "10"))

MAGIC_LINK_WINDOW_SECONDS = int(os.getenv("MAGIC_LINK_WINDOW_SECONDS", "900"))  # 15 min


# --------------------------------------------------- sign-in with a password

# Off by default: the portal signs people in by emailed link only (decided
# 11 Sep 2026). The password code is kept, dormant, not deleted -- POST
# /api/login, temporary passwords and the "choose your own password" rule.
# True switches them back on without a code change, and the sign-in screen,
# which asks GET /api/sign-in-options each time it loads, shows the password
# box again. That is the way back in if email ever fails.
PASSWORD_SIGN_IN = _flag("PASSWORD_SIGN_IN")


# ------------------------------------------------------------------- storage

# Customer documents live outside the repository. Every stored file gets a
# random name; the name the customer supplied is kept in the database and
# used only to label the download.
STORAGE_DIR = Path(
    os.getenv("DOCUMENT_STORAGE_DIR") or (PROJECT_ROOT / "storage" / "documents")
).resolve()


# ------------------------------------------------------------------ tracking

# The portal never hard-codes a tracking link: the server builds it from this
# template, so moving to a paid carrier API is a configuration change and the
# UI does not move at all.
TRACKING_URL_TEMPLATE = os.getenv(
    "TRACKING_URL_TEMPLATE",
    "https://www.marinetraffic.com/en/ais/details/ships/imo:{imo}",
).strip()

TRACKING_PROVIDER_NAME = os.getenv("TRACKING_PROVIDER_NAME", "MarineTraffic").strip()


# ------------------------------------------------------------- notifications

# Off by default, deliberately. With SEND_EMAILS false, messages are built
# and recorded but never sent, so notify.py is safe to run from day one.
SEND_EMAILS = _flag("SEND_EMAILS")

# During a pilot, only these addresses receive real mail however many
# customers are in the database.
NOTIFY_ONLY_EMAILS = [
    address.strip().lower()
    for address in os.getenv("NOTIFY_ONLY_EMAILS", "").split(",")
    if address.strip()
]

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = _flag("SMTP_USE_TLS", "true")
SMTP_FROM = os.getenv("SMTP_FROM", "").strip() or "portal@alokindia.co.in"

PORTAL_URL = os.getenv("PORTAL_URL", "https://portal.alokindia.co.in").strip()

# How often the API sends whatever is waiting, by itself, in minutes.
#
# Before this existed nothing sent anything unless somebody remembered to run
# `python -m scripts.notify` on the server, which meant a customer heard about
# their shipment when a person got round to it and not when it moved.
#
# 0 turns the automatic sender off and leaves the command and the Send now
# button as the only ways. Turning it off does not lose anything: what is
# waiting stays waiting.
#
# This is only about WHEN sending is attempted. Whether a real email leaves
# the building is still SEND_EMAILS and NOTIFY_ONLY_EMAILS below, so an
# automatic sender on a machine with SEND_EMAILS off mails nobody.
NOTIFY_EVERY_MINUTES = max(0, int(os.getenv("NOTIFY_EVERY_MINUTES", "15")))

# How long after the API starts before the first automatic run, in seconds.
# Not zero: a deploy restarts the container, and sending should not race the
# database coming back up.
NOTIFY_FIRST_RUN_DELAY_SECONDS = max(
    0, int(os.getenv("NOTIFY_FIRST_RUN_DELAY_SECONDS", "60"))
)

# Shipment statuses worth telling a customer about.
NOTIFIABLE_STATUSES = [
    status.strip()
    for status in os.getenv(
        "NOTIFY_ON_STATUSES", "Shipped,In transit,Delivered"
    ).split(",")
    if status.strip()
]

