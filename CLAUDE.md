# Alok Ingots Customer Portal — Project Briefing

**Read this file at the start of every session, and again whenever the user says
"continue".** It is the single source of truth for this project so that nothing
from the plan is lost, even in a brand-new session with no memory of past work.

---

## What we're building

A standalone customer portal for **Alok Ingots**, a stainless steel bright bar
exporter. Export customers log in and see **their own** orders:

- order status
- part-shipments
- documents (Packing List, Commercial Invoice, Bill of Lading, Mill Test
  Certificates)
- shipment / vessel tracking

It is a web app, live at **https://portal.alokindia.co.in** on server
srv1427359 (beside AlokCRM, behind its nginx).

### Stack

| Layer    | Technology |
| -------- | ---------- |
| Backend  | FastAPI (Python) |
| Frontend | React |
| Database | PostgreSQL |
| Runtime  | Docker |

---

## Rules — always follow, every step, no exceptions

1. **Never work directly on `main` or `dev`.** Always a feature branch, and
   commit often. A finished, tested step is merged into `dev` straight away —
   this is a solo project, so a Pull Request nobody else reviews adds ceremony,
   not safety. **`main` is different: it means "this is what is deployed and
   working."** Nothing reaches `main` until a deployment has actually
   succeeded. (Changed 9 Sep 2026, with the user, after seven steps stacked up
   unmerged and `dev` sat empty.)
2. **Before changing existing code, commit the current state first** as a
   restore point, and tell the user the rollback command.
3. **Never commit secrets or junk:** no `.env`, no passwords, no customer
   files/PDFs, no `node_modules`, no build folders.
4. **Deploying uses `./safe-deploy.sh`** — it backs up the database *and*
   `storage/` first, and rolls back automatically if the new version does not
   answer. Never run `docker compose build` directly; it skips all of that.
5. **Test every step before saying it's done, and show the proof.** If the
   browser can't be checked, verify headlessly.
6. **Flag anything risky or broken in plain words** — don't hide it.
7. **UI is always light theme** (no dark mode), navy `#000C2E`, Alok Ingots
   header.
8. **Explain things simply, as to a non-coder.** The user does not code. Don't
   explain background concepts unless asked.
9. **The customer side is strictly read-only.** Only the Admin Console adds
   or changes data, and that is enforced in the backend, not just the UI.
   No customer-facing router gets a POST, PUT or DELETE — the exceptions
   are signing in (by email link; the password sign-in is kept but dormant)
   and changing your own password, none of which touch customer data. See
   "The two halves".
10. **Every step covers both halves.** A customer feature needs the admin
    screen that feeds it. "Documents" means the upload page *and* the
    download page, in the same step.
11. **Commit messages are plain. No attribution lines.** Never add
    `Co-Authored-By: Claude`, `Claude-Session:`, or "Generated with Claude
    Code" to a commit message or a pull request description. (Said again on
    10 Sep 2026; the same lines were stripped from the whole history once
    already, on 8 Sep — see the progress log.)

## How to work

Do **ONE step at a time**. Finish it, test it, report clearly what was done and
how it was proved — then **STOP and wait**. When the user says "continue", move
to the next step. Never run ahead through multiple steps at once.

---

## Where we are now

**Last worked on: 11 September 2026.** Steps 1–29 are built and merged to
`dev`. **The portal is live** at https://portal.alokindia.co.in on
srv1427359, and **email works there**: on 11 Sep 2026 the server's `.env`
was set to `SEND_EMAILS=true` with AWS SES SMTP (region ap-south-1, sending
from enquiries@alokindia.com), and a real sign-in link was received and
used. The user deploys to the server themselves; this PC has no SSH to it.
The live server runs an **older build** than `dev`: on 11 Sep 2026 its
sign-in page had the email link but not the usability pass or steps 28–29,
so deploying `dev` brings all of those at once. No real customer has used
it yet.

**Step 31, sign-in by email link only**, is built and tested on
`feature/magic-link-only`, not yet merged. **Step 30, "Forgot your
password", is held unmerged** on `feature/step30-password-reset`
(`a37b9b7`) on the user's decision: do not merge or delete it without
asking.

GitHub: **https://github.com/AlokIngots/Shipment-Tracker** (private). The repo
is named `Shipment-Tracker`, not `alok-customer-portal` as originally planned.

Branches, each stacked on the one before, so the last one contains everything:

| Branch | Step |
| ------ | ---- |
| `main` | empty anchor commit |
| `dev` | **everything, merged 9 Sep 2026** — this is the working trunk |
| `feature/scaffold` | 1 — login + order list |
| `feature/step2-auth` | 2 — security, customer isolation |
| `feature/step3-order-detail` | 3 — order detail, balances, shipments |
| `feature/step4-documents` | 4 — document downloads |
| `feature/step5-data-import` | 5 — CSV import pipeline |
| `feature/step6-tracking` | 6 — vessel tracking links |
| `feature/step7-notifications` | 7 — email notifications |
| `feature/step8-notification-fix` | 8 — full test pass; two bug fixes |
| `feature/step9-deployment` | 9 — containers, Caddy, `safe-deploy.sh` |
| `feature/step10-migrations` | 10 — Alembic migrations |
| `feature/step11-accounts` | 11 — real customer accounts |
| `feature/step12-sessions` | 12 — sessions survive a refresh |
| `feature/step13-staff-documents` | 13 — staff page: shipment documents |
| `feature/step14-staff-orders` | 14 — staff page: orders and shipments; frontend split into files |
| `feature/backend-tidy` | backend reorganised into `app/` and `scripts/` (tip) |

Every step is merged into `dev`, so the per-step branches above are history
now. Start the next step with a fresh branch off `dev`.

**Restore point:** tag `pre-reorg-2026-09-10` is everything through step
14, before the backend was reorganised. Roll back with
`git checkout pre-reorg-2026-09-10`.

**Restore point:** tag `pre-magic-link-login` is everything through step
25, before sign-in by email link. Undo it on `dev`, keeping history, with
`git revert --no-edit pre-magic-link-login..dev`. If it was already
deployed, first take the database back with
`docker compose -f docker-compose.prod.yml exec api python -m alembic downgrade 0007`.

**Restore point:** tag `pre-status-from-shipments` is `dev` after the
usability pass, before step 28 (order status worked out from shipments).
Once step 28 is merged, undo it on `dev` with
`git revert --no-edit pre-status-from-shipments..dev`. If it was already
deployed, first take the database back with
`docker compose -f docker-compose.prod.yml exec api python -m alembic downgrade 0008`
— that refills the old typed status from the shipments, writing Shipped
where the new code said Part shipped.

**Restore point:** tag `pre-strip-photo-details` is `dev` after step 28,
before step 29 (hidden details removed from full-size photos). Undo it on
`dev` with `git revert --no-edit pre-strip-photo-details..dev`. There is no
migration to take back. A revert does not put removed details back into any
photo: they are gone from the files for good, which is the point.

**Restore point:** tag `pre-magic-link-only` is `dev` after step 29, before
step 31 (sign-in by email link only). Undo it on `dev` with
`git revert --no-edit pre-magic-link-only..dev`. There is no migration. On a
server already running it there is a faster way back that needs no code:
add `PASSWORD_SIGN_IN=true` to `.env` and restart the API. That reopens
password sign-in in the API, but the sign-in screen has no password box
until the revert is deployed too.

**`dev` is the branch to work from.** **`main` is still the empty anchor
commit, deliberately** — it gets its first real content only when the portal
has actually been deployed to a real server and proved to work there.

### How to open the portal

There are two copies, and confusing them wastes time.

**The real one — <http://localhost>.** The deployed stack: website, API and
database in Docker, exactly as a server would run it. It restarts itself
after a reboot, so usually there is nothing to start. If the page does not
load, start Docker Desktop and try again; if it still does not, run
`./safe-deploy.sh` from the project folder. The login form does **not**
pre-fill here — that is the point, it is built without any `.env`.

**The development one — <http://localhost:5173>.** For editing code and
watching it change. It uses a *separate* database, so nothing here can hurt
the deployed copy. Four commands, the last two each needing their own
terminal window and left running:

```bash
docker compose up -d                                      # dev database
cd backend && .venv/Scripts/python.exe -m scripts.migrate         # build/update tables
.venv/Scripts/python.exe -m uvicorn main:app --port 8000  # API      (leave running)
cd ../frontend && npm run dev                             # website  (leave running)
```

`.venv/Scripts/python.exe -m scripts.seed` adds the demo orders. Stop with `Ctrl+C`
in each window.

Demo logins are in `.env` (never committed). Both `.env` and `frontend/.env`
are needed; copy each `.env.example` if they are missing. The development
copy pre-fills the login form from `frontend/.env`; that file must never
reach an image, which is what the `**/.env` rules in `.dockerignore` are for.

### Running the tests

```bash
cd backend
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt   # once
.venv/Scripts/python.exe -m pytest
```

211 tests, about a minute, with the dev database up. They build their own
database beside the development one and drop it afterwards, so the
development data is untouched — the row counts are identical before and
after. They also run on GitHub for every push.

### Staff tools (run from `backend/`)

| Command | What it does |
| ------- | ------------ |
| `python -m scripts.manage_users --list` | every customer, and who can sign in for them |
| `python -m scripts.manage_users --add-customer CODE --name N` | add a customer |
| `python -m scripts.manage_users --add-user EMAIL --customer CODE` | give somebody a login; they sign in with an email link (it still prints a temporary password, which opens nothing while password sign-in is off) |
| `python -m scripts.manage_users --add-staff EMAIL` | give an Alok Ingots colleague a staff login |
| `python -m scripts.manage_users --reset-password EMAIL` | issue a new temporary password; while password sign-in is off, what it is good for is signing them out everywhere |
| `python -m scripts.manage_users --deactivate EMAIL` | stop somebody signing in, at once |
| `python -m scripts.manage_users --activate EMAIL` | let them back in |
| `python -m scripts.migrate` | bring the database schema up to date, losing nothing |
| `python -m scripts.migrate --status` | where the schema is, and whether the code agrees |
| `python -m scripts.migrate --sql` | the SQL a migration would run, executing nothing |
| `python -m scripts.seed` | load demo data (`--reset` drops everything first) |
| `python -m scripts.import_data FILE.csv --dry-run` | check a data file, change nothing |
| `python -m scripts.import_data FILE.csv` | import orders and shipments |
| `python -m scripts.add_document --list` | show which documents are uploaded or missing |
| `python -m scripts.add_document --shipment X --type Y --file Z` | attach a document |
| `python -m scripts.notify --dry-run` | show who would be emailed |
| `python -m scripts.notify --preview` | print the full text of one email |
| `python -m scripts.notify` | send (only if `SEND_EMAILS=true`) |
| `python -m scripts.seed --schema-only` | migrate the schema only, never demo data |
| `python -m scripts.make_thumbnails --dry-run` | count the photos that have no preview yet |
| `python -m scripts.make_thumbnails` | make those previews; safe to run again |
| `python -m scripts.strip_photo_details --dry-run` | count the photos that still carry hidden details (camera, time, GPS) |
| `python -m scripts.strip_photo_details` | remove them; safe to run again |

`--dry-run` works on every `manage_users` command that changes something.

### Setting up a real customer

```bash
python -m scripts.manage_users --add-customer HANSA --name "Hansa Stahl GmbH" --country Germany
python -m scripts.manage_users --add-user einkauf@hansa-stahl.de --customer HANSA --full-name "Petra Baumann"
```

That person then opens the portal, types their email and presses **Sign in
with email link**; nothing needs sending but the portal address. The second
command still prints a temporary password once, as it always did, but while
`PASSWORD_SIGN_IN` is off (the default) it opens nothing, so do not send it.
Staff can do both from the portal instead, with the Add customer and Add
customer login quick actions.

On the server the same commands run inside the API container:

```bash
docker compose -f docker-compose.prod.yml exec api python -m scripts.manage_users --list
```

### The two halves of the portal

The system is **two halves over one database**. Every plan, every step and
every new file belongs to one of them. Confusing them is the mistake this
section exists to prevent.

#### 1. Admin Console — internal, for Alok Ingots' team

This is where data is **put in**. Screens:

| Screen | What it does |
| ------ | ------------ |
| Staff login | separate from customers; a staff account belongs to no customer |
| Customers & logins | add a customer company, create their login |
| Orders | create and edit, or auto-pull from SAP/PMS |
| Shipments | per order, each part-shipment: vessel, IMO number, container number, Bill of Lading (BL) number, ETD/ETA, quantity |
| Documents | upload Packing List (PL), Commercial Invoice (CI), Bill of Lading (BL), Mill Test Certificate (MTC) per shipment |
| Material photos | upload photos of the bars and bundles — may come from the existing Bundle Inspection app |
| Status | set In Production → Packed → Shipped → Delivered |

#### 2. Customer Portal — external, for the customer

This is **view-only**. Screens:

| Screen | What it shows |
| ------ | ------------- |
| Customer login | sees only their own orders |
| My orders | list, with status |
| Order detail | Ordered / Dispatched / Balance pending, and the part-shipments |
| Documents | download PL, CI, BL, MTC |
| Material photos | view |
| Container tracking | "View live on MarineTraffic", the vessel by IMO number |
| Notifications | email / WhatsApp on Shipped and Arrived |

#### The hard rule

**The customer side is strictly read-only. Only the Admin Console can add or
change anything, and that is enforced in the backend, not just in the UI.**

What enforcement means in this repo, concretely:

- `app/routers/orders.py` and `app/routers/documents.py` are the whole
  customer half of the API, and between them they have **no POST, PUT or
  DELETE**. If a customer-facing router ever grows one, that is the rule
  being broken.
- Everything that writes lives under `app/routers/admin/` and every route
  there depends on `StaffUser`. A customer's token cannot satisfy it.
- The one exception is `POST /api/change-password`, which changes nothing
  but the caller's own password. Signing in is not an exception so much as
  not data: `POST /api/magic-link` and `/api/magic-link/redeem` for email
  links write only sign-in bookkeeping, and `POST /api/login` (dormant while
  `PASSWORD_SIGN_IN` is off) writes nothing.
  `test_the_customer_half_of_the_api_has_no_writes` names all four.
- Staff is a flag that only `scripts/manage_users.py --add-staff` can set, on the
  server. There is no way to become staff through the portal, and no
  customer-facing page can create an account.

#### Data flow — one direction only

```
  SAP / PMS         (orders)
  Bundle app        (material photos)        →  ADMIN CONSOLE  →  DATABASE
  Bill of Lading    (vessel, IMO, container)                          │
                                                                      ↓
                                                          CUSTOMER PORTAL (reads)
```

The customer never writes to the database.

**The consequence for planning, and it matters:** most customer features
need a matching admin screen to feed them. "Documents" is not one job, it is
two — the admin upload screen *and* the customer download screen. Every step
in the roadmap below therefore covers both sides.

Uploading is the only way a browser can write a file here: PDF, JPG or PNG,
checked on both the extension and the type the browser claims, 20 MB limit
enforced while writing, stored under a random name. A photo is also opened,
to prove it really is a picture, and saved again without its hidden details
(camera, time, GPS position) before anybody can download it.

### Deploying (from the project root)

| Command | What it does |
| ------- | ------------ |
| `./safe-deploy.sh --dry-run` | show what would happen, change nothing |
| `./safe-deploy.sh --backup` | back up the database and `storage/`, stop |
| `./safe-deploy.sh` | back up, build, start, verify — roll back if it fails |
| `COMPOSE_FILES="docker-compose.prod.yml docker-compose.server.yml" ./safe-deploy.sh` | the same, on srv1427359 beside AlokCRM — **the only way to deploy there** |

Set `PORTAL_DOMAIN` in `.env`: a real domain makes Caddy obtain HTTPS
automatically; `:80` serves plain HTTP for testing on your own machine.

## What is left before a real customer can use this

Moved into the roadmap below, so there is one list and not two that drift
apart. See **"What blocks the ones that are blocked"**.

## Project structure — where code goes

So that new files land in the right place and this never becomes a pile
again. `backend/README.md` holds the same map with one line per folder;
this is the short version plus the rule for each.

```
backend/
  main.py            builds the app and includes the routers. Nothing else.
  app/core/          config, database, security, deps — what everything needs
  app/models/        the database tables, one file per thing
  app/schemas/       the shapes that cross the wire (Pydantic)
  app/routers/       the endpoints. admin/ is the half that writes.
  app/services/      the working logic, with no HTTP in it
  scripts/           one-off tools run by hand on the server
  migrations/        Alembic migration files
  Dockerfile, requirements.txt, alembic.ini    at the root

frontend/src/
  App.jsx            who is signed in, and therefore which screen. Nothing else.
  lib/               helpers with no UI: the token, formatting, error text
  components/        small pieces used by more than one screen
  screens/           one file per screen a person actually looks at
  screens/staff/     the admin console screens
  styles/            shell.css, screens.css, staff.css — in that import order
```

**The rules that keep it this way:**

- **A router contains no business logic.** It reads the request, calls a
  service or the models, and shapes the reply. If a router grows a function
  that another router would want, that function belongs in `app/services/`.
- **A service contains no HTTP.** No `HTTPException`, no `Request`, no
  status codes. A service should be callable from a script and from a
  scheduled job, not only from an endpoint. This is why
  `app/services/notifications.py` holds `pending()` and `record_outcome()`
  and `scripts/notify.py` holds only the printing.
- **Settings are read once, in `app/core/config.py`.** No other module calls
  `os.getenv` for configuration. If a new setting is needed, it goes there
  and is imported.
- **Anything that writes goes under `app/routers/admin/`** and depends on
  `StaffUser`. This is the read-only rule enforced where it counts.
- **A script is a command, not a home for logic.** `scripts/*.py` parse
  arguments and print; the work they do lives in `app/services/` or the
  models, so an endpoint could do the same work later without importing a
  script. Scripts run as modules: `python -m scripts.manage_users --list`.
- **A frontend screen owns its own data.** Each screen fetches what it
  needs and holds its own state; `App.jsx` only decides which screen is on.
- **Reserved names, so future work lands right:**
  `app/routers/photos.py` for material photos,
  `app/routers/notifications.py` if sending ever becomes an endpoint,
  `app/services/photos.py` — which now holds photo previews — for
  whatever the Bundle Inspection app needs too.

---

## Roadmap

One step each time the user says "continue".

**Every step covers both halves.** A customer feature with no admin screen to
feed it is half a step, and the half that is missing is always the one that
turns out to matter. Each row below says what the admin side needs and what
the customer side needs, and a step is done when both work.

| # | Step | Admin Console side | Customer Portal side | State |
| - | ---- | ------------------ | -------------------- | ----- |
| 1 | Skeleton | — | login → order list | **Done** |
| 2 | Real security | staff flag, customer isolation | own orders only | **Done** |
| 3 | Order detail | — | Ordered / Dispatched / Balance, part-shipments | **Done** |
| 4 | Documents | attach a document (command line first) | download PL / CI / BL / MTC | **Done** |
| 5 | Real data from SAP/PMS | CSV importer built; **mapping blocked** on how SAP/PMS exports | nothing more needed | **Admin blocked** |
| 6 | Vessel tracking | IMO number on the shipment form | "View live on MarineTraffic" | **Done** |
| 7 | Notifications — email | statuses that trigger a message | receives the email | **Done; the server sends real email since 11 Sep 2026, no customer emailed yet** |
| 9 | Deployment | — | — | **Done, live on srv1427359** |
| 10 | Migrations | — | — | **Done** |
| 11 | Customer accounts | create a login, reset a password | forced password change | **Done** |
| 12 | Sessions | — | survives a refresh | **Done** |
| 13 | Documents, on a screen | staff upload / replace / remove page | (already had download) | **Done** |
| 14 | Orders & shipments, on a screen | create and edit orders and part-shipments | (already had the read side) | **Done** |
| 15 | Material photos | upload several at once against a shipment, with a caption; remove one | a thumbnail gallery on the order detail page, click for full size | **Done** |
| 16 | Container & B/L number | two fields on the shipment form and in the CSV importer; container check-digit validated | both shown on the order detail beside the vessel, and in the notification email | **Done** |
| 17 | Customers & logins, on a screen | add a customer, create a login, reset a password, deactivate / reactivate | (nothing — this is an admin-only step) | **Done** |
| 18 | The status sequence | a dropdown of exactly the valid statuses; a move backwards must be confirmed as a correction | a progress track on each shipment, not just a word | **Done** |
| 19 | Deploy verification | `safe-deploy.sh` fixed after the reorganisation, and drilled | — | **Done** |
| 20 | Sign-in rate limiting | — | bulk password guessing is slowed to a stop | **Done** |
| 21 | A test suite that exists | 123 tests committed, run on every push | — | **Done** |
| 22 | Ready to share a server | deploy on a host that already runs nginx, without touching it | — | **Done, not yet deployed** |
| 23 | Port 8090, and the nginx site in the repo | 8080 was taken by alok-crm-frontend | — | **Done, not yet deployed** |
| 24 | Who changed what | every change recorded with who, when and before → after; an Activity tab to read it; nobody can edit or remove it | (nothing — internal only, and customers cannot reach it) | **Done** |
| 25 | Photo previews | a small preview made at upload; a file that is not really a picture refused; a command for photos uploaded before | gallery tiles load the preview, clicking opens the original | **Done** |
| 26 | Sign in with an email link | staff can sign in by link too | "Sign in with email link" beside the password; single-use 15-minute link; same answer for any address; rate limited | **Done, live: a real link received and used on 11 Sep 2026** |
| 27 | Screens that fit | on a phone the toolbar, the four tabs and every row fit; no page scrolls sideways | every order-list column visible on any screen, order cards below 880px; the whole progress track and the totals fit a phone | **Done, not seen on a real phone** |
| — | Easy for real users (`feature/easy-usability`) | quick actions above the tabs (Add customer, Add customer login, New order, Upload document); a "Start here" 1-2-3 checklist on empty screens; plain labels; no screen mentions a server command | plain labels (Order status, Your documents, Track your shipment); friendly empty and error states with Try again | **Built and tested, not yet deployed** |
| 28 | Order status from shipments | the order form shows the status instead of asking for it; a Cancelled tick on the order; a Last shipment tick on each shipment; a reminder when nearly all of an order has gone and nothing is ticked; `last_shipment` in the CSV importer | the order says Part shipped until the last lot is ticked, then follows the lot furthest behind; "final shipment" on that lot | **Done, not yet deployed** |
| 29 | Hidden details out of full-size photos | every photo saved without its camera, time and GPS position as it is uploaded; a line on the photo box says so; a command cleans photos uploaded before; phone photos with a second picture inside (MPO) accepted instead of refused; a photo cut short refused | the full-size photo they download carries only the picture | **Done** |
| 30 | Forgot your password (`feature/step30-password-reset`, `a37b9b7`) | Email reset link on each login | "Forgot your password?" on the sign-in card | **Built, held unmerged** on the user's decision, 11 Sep 2026; moot while sign-in is link-only. Do not merge or delete without asking |
| 31 | Sign in by email link only (`feature/magic-link-only`) | no Change password or Reset password button; Add customer login says "tell them to sign in with email link" instead of showing a temporary password; the four quick actions unchanged | the sign-in card has only the email box and Sign in with email link: no password box, no password Sign in button, no "or"; no Change password button | **Built and tested, not yet merged** |

### Still to build, both sides

| Step | Admin Console side | Customer Portal side |
| ---- | ------------------ | -------------------- |
| **Photos from the Bundle app** | pull photos from the existing Bundle Inspection app instead of uploading them by hand | (gallery already built in step 15) |
| **Notifications — WhatsApp** | choose which statuses message which channel | receives the WhatsApp message |
| **SAP/PMS auto-pull** | replace the hand-run CSV import with a scheduled pull | — |

### What blocks the ones that are blocked

1. ~~A server.~~ **Done:** the portal is live at https://portal.alokindia.co.in
   on srv1427359. The user deploys it.
2. **The SAP/PMS question, still unanswered.** How can order data leave
   SAP/PMS — a spreadsheet export, a readable database, an API, or not at
   all? And does SAP/PMS hold the vessel name, IMO and container number, or
   does that sit with the CHA / freight forwarder and the Bill of Lading?
   The importer is finished and waiting; only the mapping depends on this.
3. ~~Real SMTP credentials.~~ **Done 11 Sep 2026:** AWS SES SMTP
   (ap-south-1), sending from enquiries@alokindia.com, `SEND_EMAILS=true` on
   the server, and a real sign-in link received and used. Order
   notifications have still not been sent to a customer.
4. **The Bundle Inspection app.** Material photos may be better pulled from
   it than uploaded by hand — but that needs to know what it stores and
   whether anything can read it.

---

## Progress log

Update after every step: what was done, and the commit.

| Date | What was done | Commit |
| ---- | ------------- | ------ |
| 2026-09-08 | Repo initialised; `main` anchor commit, `dev` and `feature/scaffold` branches created | `9856fc3` |
| 2026-09-08 | `.gitignore` (Python, Node, build, `.env`) and `README.md` added | `cf05c19` |
| 2026-09-08 | Backend scaffold: venv, pinned `requirements.txt`, FastAPI app with `GET /api/health` | `5002947` |
| 2026-09-08 | PostgreSQL via `docker-compose.yml`, `orders` table, seed script with one example order | `7451708` |
| 2026-09-08 | `GET /api/orders` reads the orders table through SQLAlchemy | `4d3779a` |
| 2026-09-08 | Vite + React frontend with `/api` dev proxy and health-check page | `7d2c849` |
| 2026-09-08 | Demo login: `POST /api/login` (isolated in `demo_auth.py`) + login screen | `a09cdde` |
| 2026-09-08 | Order list table after sign-in (Sales Order, Grade, Description, Ordered quantity, Status) | `c1d978c` |
| 2026-09-08 | This briefing saved as `CLAUDE.md` | `1af22af` |
| 2026-09-08 | Claude attribution lines stripped from all commit messages; history force-pushed | `1af22af` |
| 2026-09-08 | Demo email + password moved out of code into `.env` (backend and frontend); credentials removed from the repo | `2ecca97` |
| 2026-09-08 | Pushed to GitHub (private): `feature/scaffold`, `dev`, `main` | `2ecca97` |
| 2026-09-08 | **Step 2 — Real security.** `customers`, `users`, `shipments`, `documents` tables; PBKDF2 password hashing; signed tokens; `/api/orders` requires sign-in and returns only the caller's own orders | `445da35` |
| 2026-09-08 | **Step 3 — Order detail page.** `GET /api/orders/{id}` with Ordered / Dispatched / Balance and part-shipments (status, vessel, IMO, ETD/ETA, documents); clickable rows and a detail screen in the UI | `46073ff` |
| 2026-09-08 | **Step 4 — Documents.** Files stored outside the repo under `storage/`; `GET /api/documents/{id}/download` with ownership checks; Download buttons in the UI; `add_document.py` for staff to attach files | `796f7da` |
| 2026-09-08 | **Step 5 (part 1) — Import pipeline.** `import_data.py` loads orders and shipments from CSV with validation (including IMO checksum), `--dry-run`, and repeat-safe upserts. Waiting on the SAP/PMS export question | `a51998f` |
| 2026-09-08 | **Step 6 — Shipment tracking.** Server-built `tracking_url` per shipment from a `.env` template (MarineTraffic by IMO); "View live on…" link in the UI, hidden when the IMO is missing or fails its checksum | `9c7ec09` |
| 2026-09-08 | **Step 7 (email) — Notifications.** `notifications` table, `notifier.py` and `notify.py`; sends once per shipment status per user, with `SEND_EMAILS` and `NOTIFY_ONLY_EMAILS` safety switches. WhatsApp and the pilot still outstanding | `aa7c5ac` |
| 2026-09-08 | **Session paused here.** Briefing brought up to date; all branches pushed to GitHub | `33af51c` |
| 2026-09-09 | **Full test pass — every feature.** 70 checks across login, tokens, customer isolation, order detail, balances, documents, IMO/tracking, CSV import, notifications, frontend build and secret hygiene. 68 passed; 2 bugs found and fixed (below) | _this commit_ |
| 2026-09-09 | **Bug fix — notifications could be silently lost.** `notify.py` treated a suppressed or failed attempt as "done", so turning `SEND_EMAILS` on would skip every shipment recorded while it was off, and a bounced email was never retried. Only an actual `sent` now counts; earlier attempts are updated in place, so the one-message-per-(shipment, status, user) guarantee is unchanged | _this commit_ |
| 2026-09-09 | **Steps 1–8 merged into `dev`** by fast-forward (no merge commit, no conflicts); `dev` pushed to GitHub. Rule 1 amended with the user: merge finished steps to `dev` directly, keep `main` for what is actually deployed | `fd0b895` |
| 2026-09-09 | **Step 9 — Deployment.** API containerised; React app built and served by Caddy, which obtains and renews HTTPS itself; production stack with the database on no published port. `safe-deploy.sh` backs up the database and `storage/`, tags the running images `:rollback`, and restores them automatically if the new version does not answer. Proved by a real deploy plus three rollback drills | _this commit_ |
| 2026-09-09 | **Security fix found by that first deploy.** `frontend/.env` was reaching the web image, so Vite baked the demo email and password into the JavaScript served to browsers. A bare `.env` in the root `.dockerignore` only matches the root file; patterns are now `**/.env`. Re-verified: no credential appears in the shipped bundle | _this commit_ |
| 2026-09-09 | **Step 10 — Database migrations.** Alembic added; migration 0001 is the existing six tables, generated against an empty database and checked back against the models. `migrate.py` wraps it (`--status`, `--sql`, `--revision`), adopts a database that predates migrations rather than rebuilding it, and reports models that have drifted from the schema. `seed.py` no longer builds tables — it calls `migrate.py`. `safe-deploy.sh` migrates instead of `create_all`, and undoes the migration if the deploy then fails | `50ad5f2` |
| 2026-09-09 | **Step 13 — The staff side.** Migration 0003 adds `is_staff` and makes `users.customer_id` optional, because staff belong to no customer. `scripts/manage_users.py --add-staff`, a staff-only `/api/staff` section (list shipments with document status, upload, remove), and a staff page in the portal replacing the customer view. Uploads restricted to PDF/JPG/PNG, 20 MB, random stored name. Proved end to end: staff uploads a Bill of Lading, the owning customer downloads it, the other customer gets a 404 | `b716357` |
| 2026-09-09 | **Step 12 — Sessions.** The sign-in token is kept in `sessionStorage`, so a refresh no longer throws the customer back to the login screen; on load the portal checks the remembered token against `/api/me` before deciding what to show. Tokens now carry the time they were issued, and one older than the account's last password change is refused — so changing a password, or a staff `--reset-password`, signs out every other session. The person changing it gets a replacement token so they stay signed in | `06204ed` |
| 2026-09-09 | **Step 11 — Real customer accounts.** `manage_users.py` for staff: add a customer, give somebody a login with a one-time temporary password, reset it, deactivate or reactivate, all with `--dry-run`. Migration 0002 adds `must_change_password`; every customer-facing endpoint now refuses anybody still holding a temporary password, while `/api/me` and the new `POST /api/change-password` stay reachable so the portal can explain why. A password screen in the portal, forced on first sign-in and available by choice afterwards. Proved end to end on the deployed stack, including that migration 0002 reached a database with rows in it and kept them | `6c82e65` |
| 2026-09-09 | **Step 10 proved by deployment.** Real deploy of the migration code: the production database, whose tables predated migrations, was adopted at 0001 with nothing created or dropped. Two failure drills — a migration followed by a failing health check, and a migration that applied then reported drifted models — both put the schema back to 0001 and restored the previous image, with all rows untouched. The second drill found a real bug in the new deploy code, now fixed | `ef76e52` |
| 2026-09-09 | **Bug fix — UI text.** The order detail page showed the literal text `Loading order…` while loading, because a JSX text node is not a JavaScript string. Now renders `Loading order…` | _this commit_ |

| 2026-09-10 | **Step 14 — Orders and shipments on a screen.** Staff get two tabs; the new one lists every order with its customer, quantities and balance, its part-shipments, and forms to create or change any of them. An order no longer has to come from `import_data.py` on the server. The screen applies the importer's rules — a sales order number and a shipment number unique portal-wide (the importer matches on those alone), the same `valid_imo`; the one new rule, an arrival not before its departure, was added to the importer in the same commit. Deleting refuses while anything hangs off the row. Proved by 43 end-to-end checks against the dev stack | `bf29da0`, `979fd44` |
| 2026-09-10 | **Frontend split into files.** `App.jsx` was 966 lines holding nine components; it is now 142 that decide which screen is showing, with `lib/`, `components/`, `screens/` and `screens/staff/`. The toolbar, the status-to-colour map and the reading of an error out of a response stopped being written three times each. `App.css` cut into three contiguous slices imported in the order they were cut — all 109 rules keep their selectors and their cascade position, checked rather than assumed | `979fd44` |
| 2026-09-10 | **Backend reorganised.** The flat `backend/` became `app/core`, `app/models`, `app/schemas`, `app/routers` (+ `admin/`), `app/services` and `scripts/`, moved with `git mv` so the history follows. New `app/core/config.py`: four modules each worked out the project root with `Path(__file__).parent.parent` and each loaded `.env` again, so moving any of them one folder deeper silently changed where it looked. `notifier.py`/`notify.py` were **not** duplicates — library and command — so nothing was deleted; the two pieces of logic stranded in the script moved into the service. Proved: the same 18 endpoints path by path, all six scripts run, 43 checks pass unchanged | `c7d06da` |

| 2026-09-10 | **Step 15 — Material photos, both halves.** New `photos` table (migration 0004) rather than a new document type: a document is one file per kind per shipment and uploading another replaces it, so photos in `documents` would have been quietly destroyed by the replace rule. Admin: several photos in one upload with a shared caption, all-or-nothing so a bad file in a batch keeps none of it, and Remove on each. Customer: a thumbnail strip per shipment on the order detail page, click for full size, Escape to close. Staff need their own image route because `/api/photos/{id}` depends on `SettledUser`, which refuses a staff account by design. Deleting a shipment now removes its photo files from disk, not just their rows. Proved by 33 new end-to-end checks, plus the 43 from step 14 re-run | _this commit_ |

| 2026-09-10 | **Step 16 — Container number and B/L number, both halves.** Migration 0005 adds both to `shipments`, nullable because an LCL consignment may have no container and a B/L number does not exist until the carrier issues it. A container number is validated against its ISO 6346 check digit — `valid_container_no` sits in `app/services/tracking.py` beside `valid_imo` and is shared with the CSV importer, so the screen and the importer cannot disagree. Stored upper case with spaces and hyphens stripped. A B/L number has no standard format and none is enforced. Both appear on the staff shipment row, on the customer's order detail beside the vessel, and in the notification email. Proved by 15 new checks plus the 43 and 33 from steps 14 and 15 re-run | _this commit_ |

| 2026-09-10 | **Step 17 — Customers & logins on a screen.** A third staff tab: add a customer, give somebody a login, reset a password, deactivate and reactivate — all of which needed a shell on the server until now. The logic moved into `app/services/accounts.py` and `scripts/manage_users.py` now calls it, so the screen and the command line cannot allow different things. **No route creates a staff account**, deliberately: `create_staff_login` exists in the service and only the script calls it. Two lockouts are refused — deactivating your own account, and deactivating the last active staff account. The customer code is not editable, because the CSV importer matches on it. Proved by 37 checks including that `is_staff` in a request body is ignored, and by the last-staff guard tested directly against a rolled-back transaction | _this commit_ |

| 2026-09-10 | **Step 18 — The status sequence.** `status` was free text: anything could be typed, nothing checked the spelling, and a shipment could go from Delivered back to Packed unremarked. `app/services/statuses.py` now holds the sequence and both the screen and the CSV importer use it, so what one accepts the other does. The forms are dropdowns instead of free-text boxes. A move backwards is refused unless the request states it is a correction, which the screen asks about first. Customers get a progress track on each shipment rather than a bare word. **No rows were rewritten** — the five existing statuses in the database were all already valid. Proved by 21 checks plus 16 unit checks of the service, and steps 14 and 15 re-run | _this commit_ |

| 2026-09-10 | **Step 19 — The deploy, verified after the reorganisation.** `safe-deploy.sh` still called `python migrate.py`, which the reorganisation had moved to `scripts/migrate.py`: **every deploy would have failed**, and it would have failed in the worst way, because the revision was read with `2>/dev/null || true`, so a command that could not run gave the same empty answer as a database with no history — and an empty answer tells `restore_schema` there is nothing to roll back to. A wrong command name had silently switched off the schema safety net. Fixed, and the read now fails loudly instead. Then proved: image builds, all six scripts run inside it, a real deploy took the production database from 0003 to **0005** with rows in it, 20 checks passed through Caddy on port 80, and two rollback drills — a migration that applied then reported drift, and a health check that never passed — both put everything back | _this commit_ |

| 2026-09-10 | **Step 20 — Rate limiting on sign-in.** Nothing had slowed bulk password guessing. Failures are now counted per (email, address) — five — and per address — twenty — in a fifteen-minute window, answering 429 with `Retry-After`. The build found two bugs in its own defence: pruning the key table ran on **every** failed login, so each attempt cost one operation per key held and the API got slower the harder it was attacked (a denial of service inside the thing meant to prevent one), and a single key's timestamp list was unbounded. Fixed with a low-water mark and a per-key cap: 20,000 keys went from over two minutes to 50,000 keys in 0.33s. Proved by 14 checks plus memory and timing measurements | _this commit_ |

| 2026-09-10 | **Step 21 — A test suite that exists.** Every check reported in steps 14 to 20 had been run and then thrown away: two files in a temp directory, the rest typed inline into shell commands. Nothing was committed, there was no pytest, and nobody could re-run any of it. There are now **123 tests** in `backend/tests/`, run on every push by GitHub Actions. They build their own PostgreSQL database — never SQLite, which disagrees with production about `Numeric`, cascades and unique constraints — using the real migrations, so a migration that will not apply fails the suite. Writing them found two bugs: `migrations/env.py` overwrote the database URL unconditionally, so Alembic could never be pointed anywhere else; and **a token issued in the same second as a password change survived it**, because both timestamps are whole seconds and the check was `<`. Both fixed | _this commit_ |

| 2026-09-10 | **Step 22 — Prepared to share srv1427359 with AlokCRM.** Three approved changes, and three more the work uncovered. `docker-compose.server.yml` moves the portal to `127.0.0.1:8090` (8080 turned out to be alok-crm-frontend) so nginx keeps 80 and 443 — with `!override`, because Compose **merges** sequences and a plain list left 80 and 443 published anyway. `COMPOSE_FILES` is overridable in `safe-deploy.sh`. Caddy's `trusted_proxies` fixes a **live bug**: Caddy replaces `X-Forwarded-For` with the peer address, so behind it every visitor looked like Docker's gateway and the whole rate limiter was one shared budget. Also found: the website health check was hardcoded to port 80 and would have rolled back a working server deploy, and `docker compose port` can answer `0` mid-start. New staff-only `GET /api/staff/whoami` reports what the server thinks your address is, because the hop count cannot be guessed. Nothing was done on the server | _this commit_ |

| 2026-09-10 | **Step 23 — Port 8090, and the nginx site committed.** srv1427359 reported 8080 already taken by `alok-crm-frontend`, so the override moves to `127.0.0.1:8090`. The nginx site had only ever existed as text in a chat message; it is now `deploy/nginx/portal.alokindia.co.in.conf`, version-controlled, with the reasoning for `client_max_body_size 25m` and for `X-Forwarded-For $remote_addr` rather than `$proxy_add_x_forwarded_for` in it. Proved by running real nginx in front of the deployed stack: the whole chain answers, the address nginx writes is the one the API uses (`hops_seen` 2), a forged `X-Forwarded-For` is overwritten at the door, and a 5 MB upload passes where nginx's 1 MB default would have refused it | _this commit_ |

| 2026-09-11 | **Step 24 — Who changed what.** Staff could create, edit and delete orders, shipments, documents, photos, customers and logins, and none of it left a trace. Now every change writes an event in the same transaction as the change: who, when, how it arrived (screen, command line, CSV import), and each field before and after. A refused change leaves nothing, a save that changed nothing records nothing, and a removal keeps what the row held so it can be typed back in. `app/services/audit.py` is the one place that writes; the screen, `manage_users.py`, `add_document.py` and the importer all go through it. Migration 0006 adds `audit_events` with a trigger that refuses UPDATE, DELETE and TRUNCATE, from SQL as well as from the portal. A fourth staff tab, **Activity**, shows it newest first with a filter; customers cannot reach it. No password or hash is ever recorded — tested by searching the whole record for them. Proved by 15 new tests (145 in all), the frontend build, migration 0006 applied to the development database with models and schema agreeing, and a drill taking it back to 0005 and forward again. **The Activity screen has not been looked at in a browser** | `264310a` + _this commit_ |

| 2026-09-11 | **Step 25 — Photo previews.** The gallery downloaded every photo at full size to draw a tile about a hundred pixels wide. Each photo now gets a small JPEG preview when it is uploaded — at most 400 pixels on its longest side, turned upright if the phone stored it sideways, and carrying none of the photo's hidden details (camera, time, GPS). The tiles on both halves load it; clicking still opens the original. A photo with no preview falls back to the full picture, so a missing one is slow, never broken. Making the preview meant opening the file, which closed a gap: a PDF renamed to `.jpg` used to pass as a photo, and is now refused; a picture is also served as what it really is, not what it is called. Migration 0007 adds `photos.thumb_path`; `scripts/make_thumbnails.py` makes previews for older photos. Removing a photo or its shipment removes the preview file too. Pillow 12.3.0 added. Proved by 9 new tests (154 in all), the frontend build, migration 0007 applied and drilled back to 0006 and forward on the development database, the command making previews for its 5 existing photos and then 0 on a second run, and a throwaway build of the API image making a JPEG preview inside it. **Not looked at in a browser** | `fbc386e` + _this commit_ |

| 2026-09-11 | **Step 26 — Sign in with an email link**, for customers and staff, beside the password sign-in, which is unchanged. The login screen gains *Sign in with email link*: type an email, and the answer is the same *Check your email* whether or not it has an account. For an active account a 32-byte random token is issued, stored only as a SHA-256 hash, valid 15 minutes, and emailed as `https://portal.alokindia.co.in/#sign-in=<token>` through the notification sender. Redeeming it is one conditional UPDATE, so it works exactly once even if clicked twice at the same moment; a newer link, a password change or reset, or deactivation also retires it; any refusal shows *This link has expired, please request a new one*. The landing page asks for one press, so a company mail scanner that opens links cannot spend it. Limits: 3 links per inbox per 15 minutes (more requests get the same answer and send nothing), 10 requests per network address per 15 minutes (then 429), and bad links count against the existing 20-failure sign-in budget per address. Migration 0008 adds `magic_links`. Found while testing: Python sent the email quoted-printable, which splits the link with a soft line break; it now goes 7bit whenever the text allows. Proved by 21 new tests (175 in all), migration 0008 applied and drilled on the development database, and a real headless-browser run on the dev site with email going to a local mail catcher: link requested, email caught carrying the real portal address, link opened and wiped from the address bar, signed in, and the same link refused a second time. **No real email has been sent** — SMTP is still not set up | `34045b2`, `bde43a8` |

| 2026-09-11 | **Step 27 — Screens that fit, both halves.** The customer's order list kept every cell on one line inside a page 880px wide, so one realistic description pushed *Ordered quantity* and *Status* out of sight — on a 1440px monitor as much as on a phone (484px of the table hidden at 1440 and 1024, 974px at 390), with no scrollbar showing to say so. Now the description and grade wrap and every column shows; below 880px each order is drawn as a small card: sales order and status, then description, then grade and quantity. On a phone the staff side scrolled sideways as a whole page, because the Change password / Sign out buttons and the four tabs ran past the edge, and shipment, document and login rows crushed their text into a column a few letters wide. Now the buttons move under the title, the tabs sit two by two, rows put their buttons underneath, and page and card margins shrink. The customer's order detail on a phone hid the end of the progress track — Delivered — and left an empty grey square beside Ordered / Dispatched / Balance; all five steps now fit and the totals stack. Styles, class names and table roles only; no backend change. Proved by a headless Edge run over the six signed-in screens of both halves at 1440, 1024, 768, 390 and 360px, measured before and after, with two long orders added to the list inside the browser only (the database untouched): before, 9 of 24 screens hid content or scrolled sideways; after, none of 30 do, apart from the photo strips, which scroll sideways by design. Frontend build passes. **Not looked at on a real phone** | _this commit_ |

| 2026-09-11 | **Easy for real users, both halves** (`feature/easy-usability`, restore tag `pre-easy-usability`). Every staff action already had a screen, but they were spread over four tabs, an empty orders screen told staff to run `manage_users.py --add-customer`, and empty screens said nothing about what to do first. Staff now get four quick actions above the tabs — Add customer, Add customer login, New order, Upload document — each opening the right tab with its form ready (Add customer login asks which customer first when there is more than one); a "Start here" checklist on an empty screen (add the customer, give someone there a login, add their order) that ticks itself; a Documents & photos button on each shipment row; "Disable login" / "Enable login" instead of Deactivate; plain field labels and hints (Vessel IMO number, Bill of Lading number, Departure date (ETD)); and "Change history" instead of Activity. No screen names a server command any more. Customers get Order number / Product / Quantity / Order status, Shipped so far / Still to ship, a "Track your shipment" section that shows only what is known, "Your documents" with "Not ready yet", and empty and error states that explain themselves with Try again or Sign in again. Two existing glitches fixed on the way: form hints were pulled 8px up across the bottom edge of their input, and each progress-track line cut into the previous dot. **No backend change**: every action still goes through the existing `/api/staff` routes behind `StaffUser`, and the scripts still work. Proved by the 175 backend tests, the frontend build, and a headless Edge pass over 16 screens of both halves (real development data, plus empty data faked inside the browser only): no browser errors, no page scrolling sideways at 390px, no server command on the checklist, only read-only controls on the customer order page, and a customer's token refused with 403 on five staff routes. **Creating a team (staff) login is still server-only, on purpose** | `5d1ed1d`, `f0748a2` + _this commit_ |

| 2026-09-11 | **Step 28 — Order status worked out from the shipments, both halves** (`feature/step28-status-from-shipments`, restore tag `pre-status-from-shipments`). An order's status was typed by hand, so an order could say In production while every shipment said Delivered. Nobody types it now; it is worked out every time it is read. On the user's decision about part-shipped orders, staff tick **Last shipment** on the final lot: until one is ticked, an order that has started to leave says **Part shipped**; once ticked, it says the step of the lot furthest behind. Cancelling stays a decision made by hand — a Cancelled tick on the order — and taking an order back out of Cancelled counts as a correction. Staff see the status on the order form instead of a dropdown, "last shipment" on the shipment row, and a reminder when 90% or more of an order has been dispatched and nothing is ticked (a hint only; the server applies no 90% rule). Customers see the worked-out status on their list and order page, and "final shipment" on that lot. The CSV importer gains `last_shipment` (blank leaves a tick alone, so one made on the screen survives the next import), accepts only blank or Cancelled for `order_status`, and now refuses a file that moves a shipment backwards — promised by the docs since step 18, and done by nothing until now. Migration 0009 adds `orders.cancelled` and `shipments.is_final` and drops `orders.status`; its downgrade refills that column from the shipments. Picked up from the paused work-in-progress commit `c628afb` on `feature/step28-order-status`, re-applied onto `dev` after the usability pass, with the clashes in two staff screens resolved. Proved by 23 new tests (198 in all), the frontend build, migration 0009 applied to the development database and drilled back to 0008 and forward with every row count unchanged, and a headless Edge run over both halves at 1440 and 390px: no browser errors, nothing scrolls sideways, a real tick saved through the shipment form turned the order from Part shipped to In transit on the staff page, the customer list and the customer order page (which has no inputs at all), and unticking put it back. The reminder was shown with the order faked to 400 MT inside the browser only. That round trip left entries in the development database's change history, which by design cannot be removed. **Not deployed** | `d8e64e2` |

| 2026-09-11 | **Step 29 — Hidden details out of full-size photos, both halves** (`feature/step29-strip-photo-details`, restore tag `pre-strip-photo-details`). Since step 25 the preview carried none of a phone photo's hidden details, but a customer who clicked a tile downloaded the original with the camera, the time and often the GPS position of the factory in it. On the user's decision of 11 Sep 2026, every photo is now saved again without them the moment it is uploaded, before anybody, staff included, can download it. What stays is only what says how to draw the picture: its colour profile and, for a PNG, its transparency. A JPEG that is already upright is saved with its own compression settings, so it looks the same (the test allows an average difference under 2 levels out of 255); a sideways one is turned upright first, because the note saying which way is up is itself one of the details, and saved at quality 95. A photo with nothing hidden in it is kept byte for byte. `scripts/strip_photo_details.py` cleans photos uploaded before; each photo is saved as it is done and its old file removed only after, so a run stopped halfway leaves everything showing. Staff see a line on the empty photo box saying details are removed. Found on the way, and fixed: **ordinary iPhone and Samsung photos with a second picture inside (MPO) were refused as "not a picture"**, because Pillow names them MPO and only JPEG and PNG were allowed; they are now accepted, and the second picture goes with the other details. And a photo cut short while copying used to pass the picture check and show as a broken tile; it is now refused with a message saying so. No migration, no new setting. Proved by 7 new tests (205 in all): the camera, the GPS position, XMP and a comment present before and absent from what the customer and staff download, with the picture the same size and look; a sideways photo stored tall; a PNG's notes gone and its transparency kept; an MPO accepted and served as one plain JPEG; a cut-short photo refused with nothing left on disk; and the command cleaning an older photo, a dry run changing nothing, and a second run doing nothing. The frontend build passes, and a dry run of the command on the development database found its 5 photos already clean. **Not looked at in a browser; not tried on a real phone photo** | _this commit_ |

| 2026-09-11 | **Step 31 — Sign in by email link only, both halves** (`feature/magic-link-only`, restore tag `pre-magic-link-only`). On the user's decision, the sign-in card keeps only the email box and **Sign in with email link**: the password box, the password Sign in button and the "or" divider are gone. (`dev` never had a "Forgot your password?" link; step 30, which adds one, is held unmerged.) The password code is **dormant, not deleted**. A new setting, `PASSWORD_SIGN_IN`, off unless `.env` says true, makes `POST /api/login` give everybody the same refusal before anything is looked up, and switches off the rule that keeps a person on a temporary password away from their orders. Without that second part, every new login would have signed in by link and then been asked for a temporary password nobody sent them. Switched back on, both work exactly as before. Staff lose the Change password and Reset password buttons; Add customer login now says "tell them to open the portal and press Sign in with email link" instead of showing a temporary password, and the Start here checklist says the same. Customers lose Change password. The four quick actions, `manage_users.py`, and the change-password and forced-password screens are all kept. The sign-in email and the too-many-links message no longer mention a password. Proved by 6 new tests (211 in all; every older test now runs with password sign-in switched on, as the proof the dormant code still works): a right password, a wrong one and an unknown address all get the same 403; a brand-new login signs in by link and sees its orders; a staff login signs in by link and adds a customer, a customer login, an order, a shipment and a document, and that customer then signs in by link and sees the order and the document; the email says nothing of a password; and switched on, the temporary-password rule is back. The frontend build passes, `manage_users --list` runs, and a headless Edge run on the development site passed 22 checks: one button on the sign-in card at desktop and phone width, no password box, no divider, no Forgot link, `/api/login` refused from the browser, no Change password or Reset password button on either half, all four quick actions open (Upload document onto Documents & photos with its Upload buttons), Add customer login shows the new note and no password, and no browser errors. The two runs left two development-only logins (`link-only-check-…@demo-customer.example`) and their change-history entries. A fresh sign-in link requested from the live server for mis@alokindia.com has **not arrived**; see Known issues. **Not merged, not deployed** | _this commit_ |

### Design decisions worth remembering

- **The tracking link is built by the server, not the browser.** The API
  returns a finished `tracking_url` plus `tracking_provider` per shipment,
  from `TRACKING_URL_TEMPLATE` in `.env`. Moving to a paid carrier tracking
  service is then a config change, and the UI does not move at all.
- **`valid_imo` lives in `backend/tracking.py`** and is shared with the
  importer, so what the API trusts and what the importer accepts can never
  drift apart.

### Design decisions worth remembering

- **Notifications default to off.** `SEND_EMAILS=false` means messages are
  recorded and printed but never sent. `NOTIFY_ONLY_EMAILS` limits real mail
  to named addresses during a pilot. Both are in `.env`, and both must be
  changed deliberately before any customer is emailed.
- **Each (shipment, status, user) is notified once**, enforced by a unique
  constraint in the database, so re-running `scripts.notify` cannot spam anyone.
- **Only a message that actually went out counts as done.** A suppressed or
  failed attempt is recorded, but is retried on the next run and its row is
  updated in place. This is what makes it safe to run `scripts.notify` from day one
  with `SEND_EMAILS=false` and switch sending on later without losing anyone.

### Design decisions worth remembering

- **`sessionStorage`, not `localStorage`, for the sign-in token.** It
  survives a refresh, which is the whole point, and is thrown away when the
  tab closes. `localStorage` would survive the browser closing and reopening:
  convenient on your own laptop, wrong on the shared machine in a shipping
  office. Every read and write is wrapped, because a browser set to block
  site data throws rather than returning nothing, and not being able to
  remember a token must never stop the portal loading.
- **A password change signs out everywhere else.** Tokens carry when they
  were issued, and anything older than the account's last password change is
  refused. This is what makes changing a password after a scare mean
  something. The person doing it gets a replacement token, or they would be
  signed out by their own change.

- **A temporary password is treated as already compromised.** Staff have seen
  it and it travelled by email or phone, so it buys nothing except the right
  to set a real one. The API refuses to return any order while it is in use,
  so the rule cannot be skipped by talking to the API instead of the website.
- **There is no web page for creating accounts**, on purpose, and the same
  reasoning as document uploads: nothing customer-facing can create an
  account, so nothing customer-facing can be tricked into creating one.
- **Password rules are short on purpose** — 12 characters and not the same
  character repeated. Length is what protects a password; rules about
  punctuation mostly teach people to write `Password1!` and reuse it.

- **A database that predates migrations is adopted, not rebuilt.** Anything
  with the portal's tables and no migration history is *marked* as being at
  0001 instead of having 0001 run against it, so nothing is created or
  dropped. Rebuilding would have been simpler and is exactly the habit
  migrations exist to break.
- **`scripts.migrate --status` compares the code against the real database** and
  names, in plain words, anything a model has that the database does not.
  Forgetting to write a migration is the mistake this will meet most often,
  and it otherwise stays silent until something breaks.

### Design decisions worth remembering

- **Photos are their own table, not a kind of document.** A document is one
  file per type per shipment and uploading another replaces it. Photos are
  many per shipment and none replaces another. Sharing the table would have
  meant inventing `doc_type` values like "Photo 3", and the
  replace-on-same-type rule would then have silently destroyed photos.
- **A photo's media type is worked out from its suffix, never from the
  browser.** The uploading browser's claim is good enough to refuse an
  upload on, and not good enough to repeat back to somebody else's browser.
  Documents were always served as `application/pdf` regardless; a gallery
  cannot get away with that.
- **The picture is fetched, not linked.** `<img src="/api/photos/3">` would
  be sent without the Authorization header and answered 401, so `AuthImage`
  fetches the image like any other request and points the `<img>` at a blob
  URL, revoking it on unmount. The same reason document downloads are not
  plain links.
- **An upload of several photos is all or nothing.** If the fourth of five
  files is a PDF, none of the five is kept and the message names the file
  that was wrong. Keeping three of five leaves somebody working out which.

### Design decisions worth remembering

- **A container number is check-digit validated; a B/L number is not.** ISO
  6346 puts a check digit on every container number precisely so a
  transposition is caught, and `valid_container_no` catches it at the one
  screen where somebody types it rather than in front of a customer trying
  to trace a box that does not exist. Bills of Lading have no standard
  format at all — every carrier numbers its own way — so validating one
  would only ever refuse a real one.
- **`valid_container_no` lives beside `valid_imo` in the tracking service**
  and is imported by the CSV importer, for the same reason `valid_imo` is:
  what the screen refuses and what the importer refuses must be the same
  thing, and the only way to guarantee that is one function.

### Design decisions worth remembering

- **A staff account can still only be created on the server.** The admin
  console creates customers and customer logins; it cannot create staff,
  and there is no route that does. Staff is the flag that unlocks every
  write in the portal, so somebody who could grant it could grant it to
  themselves twice over and no one could un-grant it. `--add-staff` needs a
  shell, and that is the point. Sending `is_staff` in a request body does
  nothing: the schema has no such field and the service never sets it.
- **Two deactivations are refused, both of which lock the door from
  inside**: your own account, and the last staff account still active.
  Either would leave the admin console reachable by nobody, undoable only
  by somebody with access to the server.
- **A customer's code cannot be edited, only its name and country.** The
  code is the join between this portal and whatever SAP/PMS exports, and
  `import_data.py` matches on it. Changing it on a screen would orphan
  every future import for that customer with nothing appearing to fail.
- **The account rules live in `app/services/accounts.py`.** Both the screen
  and `manage_users.py` call it, for the same reason `valid_imo` is shared
  with the importer: two implementations of one rule will differ eventually,
  and the difference will be found by a customer.

### Design decisions worth remembering

- **The sequence has five steps, not the four that were asked for.** In
  production → Packed → Shipped → **In transit** → Delivered. "In transit"
  was already in the demo data, in the `NOTIFY_ON_STATUSES` default, and is
  what the whole vessel-tracking feature is about. Rewriting those rows to
  "Shipped" would have thrown away a real distinction — loaded, versus
  actually at sea — to make the list shorter. It was kept and placed where
  it belongs. Say the word and it can go.
- **Moving backwards is refused, but not forbidden.** Delivered to Packed is
  almost always a misclick, and a customer told their goods arrived should
  not silently see them un-arrive. But no way back from a fat-fingered
  Delivered would be worse than the misclick, so the request can say it is a
  correction, and the screen asks before it does.
- **Cancelled is outside the numbering.** Anything can be cancelled without
  ceremony, because things do get cancelled. Coming back *out* of Cancelled
  counts as a correction, because that is somebody undoing a decision rather
  than recording one.
- **A CSV can never claim a correction.** `allow_backwards` is a field on
  the API only. An import that moves a shipment backwards is far more likely
  to be a stale export than a decision, so the importer refuses it outright.

### Design decisions worth remembering

- **A value the safety net depends on must fail loudly, never quietly.**
  `safe-deploy.sh` read the schema revision with `2>/dev/null || true`, so a
  command that could not run at all produced exactly the same empty string
  as a database with no migration history — and an empty string is what
  tells the rollback there is nothing to go back to. One typo therefore
  disabled the schema safety net for the whole deploy, silently. It now
  prints what went wrong and abandons the deploy. Worth applying to anything
  else that reads a value a safety check depends on.
- **A drill is worth more than a passing deploy.** The deploy that failed on
  purpose found more than the one that worked: it proved the drift check
  catches a migration that does not match the models, that the downgrade
  runs while the new image is still up (the old one does not contain the new
  migration), and that the rows survive both.

### Design decisions worth remembering

- **There is deliberately no limit on an email address alone.** It is the
  obvious third counter and it is a trap: anyone who knows a customer's
  address could then lock that customer out by failing five times on
  purpose. A distributed attack on one account therefore still gets through.
  That is a considered trade — the alternative hands every passer-by a way
  to shut a real customer out of their own portal.
- **The rightmost X-Forwarded-For entry is the one to trust, not the
  leftmost.** Caddy appends the peer it saw, so the last hop is ours and the
  rest is whatever the caller typed. Reading from the left would let an
  attacker spend somebody else's budget, or dodge their own by inventing a
  fresh address per request. Trusting the header at all is only safe because
  the api service publishes no ports.
- **A defence must not become the attack.** Pruning the limiter's key table
  ran on every failed login, so each attempt cost one operation per key
  held — the API got slower exactly as an attack got busier. Two fixes: a
  low-water mark, so a prune is followed by thousands of cheap inserts
  rather than another prune; and a cap on each key's list, since a key
  already at its limit is locked and more timestamps change nothing but
  memory. Anything that allocates per request needs both bounds.

### Design decisions worth remembering

- **The tests use PostgreSQL, not SQLite.** SQLite would be faster and would
  quietly disagree with production about `Numeric`, about `ON DELETE
  CASCADE` and about unique constraints — the exact class of bug a suite
  exists to catch. They build a throwaway database beside the development
  one and run the real migrations into it, so the migrations are tested too.
- **Each test rolls back rather than cleaning up.** The endpoints call
  `commit()` themselves, so the session joins the outer transaction with a
  savepoint. Tests cannot see each other's rows and the database is
  identical at the end of a run — which is checked, not assumed.
- **A warning from our own code is an error in the suite.** Library warnings
  we do not control are silenced by name, never wholesale, so a new one
  still shows up.

### Design decisions worth remembering

- **Compose merges lists; it does not replace them.** An override file that
  sets `ports:` as a plain list *adds* to the ports underneath. On a shared
  server that would have published 80 and 443 anyway and taken the other
  application off the air. `ports: !override` is what replaces them, and
  `docker compose config` is what proves it.
- **Caddy replaces X-Forwarded-For unless the peer is a trusted proxy.**
  Not appends — replaces. Every visitor therefore looked like Docker's
  gateway to the rate limiter. `trusted_proxies static private_ranges` makes
  Caddy keep what arrived; it then appends its own hop, which is why
  `TRUSTED_PROXY_HOPS` is 2 behind nginx and 1 standalone.
- **`/api/staff/whoami` exists because the hop count cannot be guessed.** It
  depends on what sits in front and what each part does to the header, and
  getting it wrong is invisible until one attacker locks out every customer.
  Open it as staff from outside and check it reports your own public
  address.

### Design decisions worth remembering

- **The nginx site lives in the repo, not in a message.** A config that
  exists only in something somebody was told is a config nobody can review,
  diff, or find again. `deploy/nginx/portal.alokindia.co.in.conf` carries
  the install commands and the reasoning in comments, and it is the file
  that was actually tested.
- **nginx must write `X-Forwarded-For $remote_addr`, not
  `$proxy_add_x_forwarded_for`.** The second appends to whatever the caller
  sent, so a visitor could put any address at the front of the list and
  spend somebody else's rate-limit budget. nginx is the first hop, so it
  states what it sees and discards the rest. Verified: a forged header sent
  from outside does not survive the door.

### Design decisions worth remembering

- **An event is written in the same transaction as its change, never
  before it.** `audit.record` adds to the session and the caller's commit
  saves both. An event committed first would survive the change failing,
  and describe something that never happened; one committed after could be
  lost if the process died in between.
- **The table guards itself, not just the code.** No route edits or
  removes an event, but that alone only protects against the portal. The
  trigger from migration 0006 refuses UPDATE, DELETE and TRUNCATE from
  anybody, including somebody at a SQL prompt — so a stolen staff session
  or a bug cannot tidy anything away.
- **No foreign key to `users`.** The email is copied onto the event at the
  time. A foreign key's `ON DELETE SET NULL` would be an UPDATE, which the
  trigger refuses, and the record should read correctly whatever later
  happens to the account.
- **Only what changed is recorded.** A form saved untouched, or the same
  CSV imported every morning, adds nothing. Otherwise the one real change
  is buried under a hundred that were not. Quantities are compared to three
  decimal places so "40" and "40.000" count as the same.
- **The fields recorded are a list, not "everything".** `ORDER_FIELDS`,
  `SHIPMENT_FIELDS` and the rest name what is kept. That is how a password
  hash stays out: not by remembering to leave it out, but by never being
  asked for.
- **A command run on the server names no person.** There is nobody signed
  in to name. The event says "command line" or "csv import" instead, which
  still separates it from anything done through the portal.

### Design decisions worth remembering

- **Previews are made at upload, not on first view.** Making one when a
  customer first opens the gallery would mean a customer's read writing to
  the database, which the read-only rule exists to prevent. Photos from
  before previews existed are handled by a command instead, and fall back
  to the full picture until it runs.
- **A missing preview falls back; an unreadable upload is refused.** If a
  real picture cannot be shrunk, the photo is kept and shown full size —
  losing a photo over a thumbnail would be the wrong trade. But a file that
  cannot be opened as a picture at all is refused, because it would only
  ever be a broken tile in front of a customer.
- **What a file is beats what it is called.** The media type stored is the
  format found by opening the file. A PNG saved as `.jpg` is served as a
  PNG.
- **The preview is stripped; the original is not.** Removing the hidden
  details from the original would mean altering the photo staff uploaded.
  That is a decision for the business, not a side effect of a thumbnail.

### Design decisions worth remembering

- **The token travels after the `#`.** A browser never sends the part of
  an address after `#` to a server, so the token cannot land in a web
  server's access log or a Referer header. The page reads it once and wipes
  it from the address bar before doing anything else.
- **The link page waits for a press.** Company mail systems — Outlook's
  Safe Links, for one — open every link in an email to scan it. A page that
  signed in on opening would have its one use spent by the scanner, and the
  customer would click a dead link. A scanner does not press buttons.
- **The same answer for every address, including under the rate limit.**
  Past three links, an inbox gets the same *Check your email* and nothing
  is sent, rather than a 429 — a 429 would tell a stranger the address is
  being asked about. Only the per-network limit answers 429, and it says
  nothing about any address. The email goes out after the answer, so an
  address with an account does not answer noticeably slower either.
- **A plain hash, not a slow one.** Passwords get PBKDF2 because people
  choose guessable ones. A token is 256 random bits; there is nothing to
  guess, and a slow hash would only slow the portal down.
- **Spent by one UPDATE, not a read then a write.** "Mark used where
  unused and unexpired, returning whose it was" lets the database guarantee
  one winner when the same link is opened twice at once.
- **A link does not skip the temporary-password rule — while password
  sign-in is on.** It proves the inbox, not that the person chose a
  password. Since step 31 the rule only applies with `PASSWORD_SIGN_IN` on;
  with it off nobody can use a password, so a temporary one opens nothing
  and there is nothing to replace.

### Design decisions worth remembering

- **Cards on a narrow screen, not a table that scrolls sideways.** A
  scrolling table hides whatever is on the right — and Status is the last
  column — while nothing on a touch screen says there is more to see.
- **880px is the switch because the page never gets wider than that.**
  From 880px up the table always has the same room, so it only ever has to
  fit one width; below it, it is cards.
- **Only the description and the grade wrap.** A sales order number or a
  quantity broken over two lines is easy to misread; a description over
  three lines is not. The grade keeps room for an ordinary value like
  `304 / 1.4301` on one line.
- **The table's roles are written into the markup.** Drawn as cards, a
  table stops being a table to a screen reader in some browsers.
  `role="table"`, `"row"` and `"cell"` keep it one, and the header row is
  hidden from sight rather than removed.
- **One padding value for a card and what reaches its edges.** The order
  table and the Ordered / Dispatched / Balance strip stretch to the card's
  edges using `--card-pad`, so shrinking it on a phone moves all three
  together instead of leaving one of them hanging over the edge.
- **The page is still 880px wide.** Widening it would give the table more
  room on a monitor, but it changes how every screen looks; not done
  without asking.

### Design decisions worth remembering

- **Staff tick the last shipment; the quantities do not decide.** The
  user's decision, 11 Sep 2026. Steel orders finish a few tonnes over or
  under, so "shipped = ordered" would leave a short order Part shipped for
  ever and call an over-shipped one finished a lot early. Only staff know
  which lot is the last.
- **The status is never stored.** It is worked out on every read from the
  shipments, so it cannot drift from them the way a typed one did. The
  price is loading an order's shipments to show its status, which the
  customer list does in one query.
- **Once finished, an order follows the lot furthest behind.** Delivered
  means all of it arrived, not some of it. A cancelled lot is left out as
  though it were never there.
- **A file can cancel an order but never un-cancel it**, and a blank
  `last_shipment` leaves a tick alone. The morning's export must not undo
  a decision somebody made on the screen.
- **An import that moves a shipment backwards stops the whole file.** The
  docs promised this since step 18; nothing enforced it until step 28. A
  file going backwards is a stale export far more often than a decision.
- **The migration carries its own copy of the rule.** A migration must go
  on doing what it did when written, whatever later happens to
  `statuses.py`; a test checks the copy still agrees.

### Design decisions worth remembering

- **Details go at upload, not when a photo is downloaded.** Cleaning on
  the way out would mean every route that serves a photo has to remember
  to do it, and one that forgot would hand over the original. Cleaned at
  the door, the file on disk has nothing left in it to leak.
- **A list of what may stay, not of what must go.** A JPEG keeps its JFIF
  header, its colour profile and Adobe's colour note, and nothing else. A
  kind of detail nobody thought of, such as a maker's own block or a second
  picture, goes too, instead of slipping past a list of known offenders.
- **A clean photo is not saved again.** Every JPEG save costs a hair of
  quality, so a photo with nothing to remove is left byte for byte, and a
  second run of the command changes nothing.
- **A photo that cannot be cleaned is refused, not kept with its
  details.** The only photos that fail are ones cut short, which would
  only ever have been a broken tile.
- **The colour profile stays.** It changes how the colours look, which
  matters for a photo of a bar's surface, and says nothing about where or
  when the photo was taken.

### Design decisions worth remembering

- **Dormant means a switch, not a hidden button.** Taking the password box
  off the screen alone would have left `POST /api/login` answering anybody
  who called it directly with a password. `PASSWORD_SIGN_IN` closes the
  door in the API too, and opening it again is one line in `.env`, not a
  code change.
- **The switch also puts the temporary-password rule to sleep.** That rule
  exists because staff have seen a temporary password. If no password can
  sign anybody in, it protects nothing, and left on it would have stopped
  every new login at a screen asking for a password nobody sent them.
- **Refused before anything is looked up.** With the switch off,
  `/api/login` gives the same 403 for a right password, a wrong one and an
  address with no account, before the rate limiter or the users table is
  touched. It cannot be used to ask whether an account exists.
- **The server still makes a temporary password for a new login.** Changing
  `accounts.create_login` would have meant changing `manage_users.py` and
  code the user asked to keep. The screen simply does not show it.
- **The older tests run with the switch on.** They are the proof the
  dormant code still works; `test_link_only.py` runs with it off and tests
  the portal as it ships.

### Known issues / risks

- **Screens that fit have been checked in an emulated browser only.**
  Headless Edge at five widths; neither an iPhone nor an Android phone has
  been looked at. The screenshot script was a scratch tool and is not in the
  repository, so the check cannot be re-run from here.
- **Only the customer order list was tried with long values.** The staff
  screens were measured with the two orders in the development database; a
  very long customer name or file name is covered by the wrapping rules but
  was not tried.
- **Email is now the only way in.** Since step 31 nobody, staff included,
  can sign in if the email does not arrive: an AWS SES problem, a link filed
  as spam or a mistyped address locks that person out until it is fixed.
  Two server settings decide who can sign in at all: `SEND_EMAILS` must stay
  true, and **`NOTIFY_ONLY_EMAILS` limits sign-in links as well as
  notifications**, so while it holds a pilot list an address not on it gets
  no link and cannot sign in. Check it before deploying step 31. The way
  back in an emergency is under the `pre-magic-link-only` restore point.
- **The 11 Sep 2026 re-check has not been confirmed.** A fresh link was
  requested from the live server for mis@alokindia.com at 11:11 UTC (answer
  202), and nothing from enquiries@alokindia.com reached that inbox in the
  next 10 minutes. The answer is the same whether or not an address has an
  account, so the likeliest reason is that mis@alokindia.com has no login on
  the live portal, or is not on `NOTIFY_ONLY_EMAILS`, rather than sending
  having broken, but that is not proven. Confirm with an address that does
  have a login before deploying step 31.
- **Email sign-in makes a staff inbox a key to the admin console.**
  Whoever can read a staff member's email can now sign in as them. Worth a
  second factor for staff if more than a few people hold staff logins.
- **The create-login answer still carries a temporary password.** The staff
  screen no longer shows it, but it still travels to the staff member's
  browser. With password sign-in off it opens nothing.
- **Link-request counts live in memory**, like the sign-in counts, and are
  lost on every restart and deploy.

- **Run `scripts.strip_photo_details` once after deploying to a server
  that already holds photos.** Until it runs, photos uploaded before step
  29 still carry their details at full size. The server holds none yet, so
  on a first deploy there is nothing to do.
- **A photo that had to be turned upright is saved at quality 95**, not
  with its own settings: a little different from the original, not so a
  person would notice. Not measured on real phone photos.
- **The second picture inside an iPhone or Samsung photo is thrown away.**
  On newer phones it can hold the extra brightness an HDR screen uses, so
  such a photo may look slightly flatter on an HDR screen than on the
  phone. Ordinary screens show no difference.
- **Data after the end of a JPEG is only removed when the photo is saved
  again.** Some phones add their own block after the picture. Every phone
  photo carries EXIF, so it is saved again and the block goes; a JPEG with
  no EXIF, XMP or comment but a block after its end would be kept as it is.
- **The development and deployed copies on this PC share `storage/`.**
  Their databases never point at the same file unless one was copied from
  the other; if one ever is, cleaning photos through one would remove files
  the other still uses.
- **Cleaning older photos is not in the activity record**, like making
  previews: the picture is the same picture.
- **Run `scripts.make_thumbnails` once after deploying to a server that
  already holds photos.** Until it runs, older photos show full size, as
  they always did. The server holds none yet, so on a first deploy there is
  nothing to do.
- **iPhone HEIC photos are refused.** Only real JPG and PNG files are
  accepted. An iPhone set to "Most Compatible" saves JPG; otherwise the
  photo must be converted before uploading.
- **Making previews adds time to a large upload.** Each photo in a batch of
  up to twenty is shrunk before the upload finishes. Not measured on real
  phone photos yet.

- **Somebody with full access to the database server can still erase the
  activity record**, by dropping the trigger first. Nothing inside a
  database can prevent that. The record protects against a stolen staff
  session, a bug or a slip — not against whoever runs the server. Backups
  are the answer to that.
- **Only changes are recorded, not sign-ins.** Who signed in and when, and
  failed attempts, are not in the activity record.
- **Nothing before step 24 has any history.** Every row already in the
  database appears only from its next change onwards.
- **The activity record is never trimmed.** Each event is small and a
  handful of staff will take years to make it large, but nothing removes
  old ones — the trigger would refuse it anyway.
- **`scripts.seed --reset` wipes the activity record** along with everything
  else, because it drops the tables. Development only, like the rest of
  `--reset`.
- **The Activity filter only searches what is loaded** — the newest 100
  changes, plus any older pages opened with "Load older changes". The page
  says so when a filter is on and older changes exist.

- **A token cannot be cancelled one at a time.** Tokens are signed and
  stateless, valid for 12 hours. What *can* be done: changing a password (or
  `--reset-password`) retires every token issued before it, and deactivating
  an account refuses them all at once. Changing `SECRET_KEY` signs everybody
  out. There is no way to end one particular session and leave the others.
- **The token is kept in `sessionStorage`**, so it survives a refresh and is
  thrown away when the tab closes. Not `localStorage`, which would survive
  the browser being closed and reopened — wrong on a shared office machine.
  It is readable by JavaScript running on the page, which is the accepted
  cost of not using cookies; an httpOnly cookie plus CSRF protection is the
  stronger answer if the portal ever handles more than read-only order data.
- **Creating logins is now possible remotely, not just from the server.**
  That is the point of step 17, but it does widen what a stolen staff token
  can do: previously an attacker needed shell access to create a login, and
  now a staff session is enough. They still cannot create staff, so they
  cannot entrench themselves, and a password change or `--deactivate`
  retires every token at once. Rate limiting on `/api/login` (still absent,
  below) matters more now than it did.
- **A forgotten password does not matter any more.** Since step 31 people
  sign in by email link. Step 30 (an emailed password reset) is built and
  held unmerged on its branch, in case passwords ever come back.
- **An account can be deactivated but not deleted.** Deactivating is nearly
  always what is actually wanted — a deleted login takes its history with it —
  but there is no tidy way to remove one created by mistake except SQL.
- **The rate limiter was measuring the wrong address behind Caddy** until
  step 22, so any deploy made before it treated every visitor as one client.
  Fixed, but worth knowing when reading anything written earlier about it.
- **The rate-limit counts live in memory, in one process.** They are lost
  whenever the API restarts, including on every deploy, so a deploy hands
  an attacker a clean slate. And if uvicorn is ever run with `--workers N`,
  each worker keeps its own counts and the effective limit silently becomes
  N times looser. Redis is the answer to both if either stops being
  acceptable; for one container in front of a handful of customers, neither
  is worth the dependency yet.
- **Only `/api/login` is limited.** `POST /api/change-password` also checks
  a password and is not counted, though it needs a valid token first, so
  guessing there means already holding one.
- **Nothing checks that an email address is real.** `--add-user` accepts
  whatever it is given, so a typo creates an account nobody can sign in to.
  Check the address before pressing enter; `--list` will show it.
- **Two demo customers still exist** so that customer isolation can be tested.
  They are created by `scripts/seed.py` from `.env` and must never be seeded onto a
  server holding real customers — that is why deploys run migrations only,
  and never `scripts.seed` without `--schema-only`.
- **Shipment and vessel data is still invented** for the demo. The importer is
  ready; real values arrive once the SAP/PMS export is settled.
- **The demo database now also holds `CUST-100` / `CUST-101`** from importing
  the template. They have no users, so nobody can sign in as them.
- **A container number that is not ISO 6346 will be refused.** Virtually
  every shipping container complies, but if a forwarder ever supplies a
  non-standard reference — some LCL and groupage paperwork does — the
  screen and the importer will both reject it and the only way through is
  to leave the field blank. Worth knowing before somebody assumes the
  portal is broken.
- **Container tracking is still vessel tracking.** The container number is
  now recorded and shown, but the "View live on..." link still points at
  MarineTraffic by IMO, which shows where the *ship* is. Nothing tracks the
  box itself. Real container-level tracking needs a paid carrier API.
- **`scripts/add_document.py` still works** and does the same thing as the
  staff page. Keep them in step: both store a random name and replace a
  document of the same type.
- **Document files live in `storage/`**, which is git-ignored and must be
  included in server backups — `safe-deploy.sh` will need to cover it.
- **`scripts.seed --reset` clears the database but leaves document files behind**
  in `storage/documents/`, so old files accumulate as orphans. Harmless while
  the data is invented; worth a tidy-up before real documents arrive.
- **`safe-deploy.sh` has only ever run against a local Docker stack.** It has
  never met a real server, a real domain, or a real HTTPS certificate. Caddy's
  certificate step in particular cannot be tested until DNS points at a real
  machine.
- **Docker Hub could not be reached from this machine on 9 Sep 2026.** Pulling
  base images failed with a TLS error through Docker Desktop's proxy, while
  the same request from Windows itself worked. The images were fetched from
  `mirror.gcr.io` and retagged instead. Worth knowing before the first deploy
  on a real server: it may be this network rather than anything in the repo.
- **A failed deploy puts the schema back, but not the rows.** If a deploy
  migrates the schema and then fails, `safe-deploy.sh` runs the migration
  backwards to where it started before restoring the old image. Rows are
  never touched, because a schema step changes the shape of the tables and
  not what is in them. If it cannot undo the migration — a migration with no
  working `downgrade()` — it says so loudly and prints the restore command
  for the backup it took minutes earlier.
- **Downgrades are only as good as the migration that was written.** Alembic
  writes a `downgrade()` automatically, but a migration that throws data away
  cannot put it back. Read the downgrade of anything that drops a column.
- **Email works on the server, but no customer has been emailed.** On 11
  Sep 2026 a real sign-in link was received and used through AWS SES. Order
  notifications (`scripts.notify`) have still not gone to a customer; one
  careful test to a colleague first is still the plan.
- **WhatsApp is not built.** It needs a WhatsApp Business account and a
  pre-approved message template through Twilio or Meta's Cloud API. The
  channel would slot into `app/services/notifications.py` alongside email.
- **Nothing triggers notifications automatically.** `python -m scripts.notify` must be run
  after each import, by hand or on a schedule.
- **Nothing stops the same photo being uploaded twice.** Documents are
  deduplicated by type; photos have no equivalent, so a double click on
  Add photos leaves two identical tiles that must be removed one at a time.
- **A photo's caption cannot be changed after upload.** It is set once for
  the whole batch. Fixing a typo means removing the photo and adding it
  again.
- **A forgotten Last shipment tick leaves an order Part shipped for
  ever.** Nothing ticks it automatically, by design. The staff reminder
  appears only once 90% of the ordered quantity has been dispatched, so an
  order that finishes further under than that gets no reminder.
- **Migration 0009 throws away every typed order status.** Only Cancelled
  survives, as the new `cancelled` tick. The activity record still holds
  each change made to the old status since step 24, and taking the
  database back to 0008 refills the column from the shipments rather than
  from what was typed.
- **An order with no shipments says In production**, even if nothing has
  started — there is no "Not started" step, and there was none before.
- **Old rows can still hold a status the sequence does not know.** Nothing
  was rewritten, and validation only runs on the way in. Every row in the
  database today is valid, but a row written before step 18 by some other
  route would survive; the customer's progress track simply does not draw
  for a status it cannot place.
- **`safe-deploy.sh` has now met the reorganised code, but still not a real
  server.** It has been run end to end locally, including two rollback
  drills, against the reorganised backend. What it has still never met is a
  real machine, a real domain, or Caddy actually obtaining an HTTPS
  certificate — that cannot be tested until DNS points somewhere.
- **The frontend has no tests.** The 211 committed tests are all backend.
  Nothing checks that the progress track draws, that the photo gallery
  revokes its blob URLs, or that a backwards status change asks before it
  saves. `npm run build` passing only means it compiles.
- **MarineTraffic shows a vessel's current position, not the cargo.** It
  cannot confirm a container or parcel is aboard, and free pages can be rate
  limited or blocked. A paid carrier API is the answer if customers need
  guaranteed, shipment-level tracking.
