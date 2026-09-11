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

It is a web app. It will live at **portal.alokindia.co.in** (address to be set
up later).

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
   No customer-facing router gets a POST, PUT or DELETE — the single
   exception is changing your own password. See "The two halves".
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

**Last worked on: 9 September 2026.** All seven roadmap steps are built, plus
deployment, database migrations, customer accounts, sessions that survive a
refresh, and the first staff page. Every feature has been tested end to end,
and
the earlier full pass of 70 checks found and fixed two bugs. Nothing is
deployed on a real server, and no real customer has ever used it or been
emailed by it.

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

145 tests, about a minute, with the dev database up. They build their own
database beside the development one and drop it afterwards, so the
development data is untouched — the row counts are identical before and
after. They also run on GitHub for every push.

### Staff tools (run from `backend/`)

| Command | What it does |
| ------- | ------------ |
| `python -m scripts.manage_users --list` | every customer, and who can sign in for them |
| `python -m scripts.manage_users --add-customer CODE --name N` | add a customer |
| `python -m scripts.manage_users --add-user EMAIL --customer CODE` | give somebody a login; prints a temporary password once |
| `python -m scripts.manage_users --add-staff EMAIL` | give an Alok Ingots colleague a staff login |
| `python -m scripts.manage_users --reset-password EMAIL` | issue a new temporary password |
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

`--dry-run` works on every `manage_users` command that changes something.

### Setting up a real customer

```bash
python -m scripts.manage_users --add-customer HANSA --name "Hansa Stahl GmbH" --country Germany
python -m scripts.manage_users --add-user einkauf@hansa-stahl.de --customer HANSA --full-name "Petra Baumann"
```

The second command prints a temporary password **once** — it is stored as a
hash, so nobody, including the server, can read it back. Send it the way you
would send anything else confidential, and not in the same message as the
portal address. The portal then makes that person choose their own password
before it will show them a single order, and the API enforces that, not just
the screen.

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
  but the caller's own password.
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
enforced while writing, stored under a random name.

### Deploying (from the project root)

| Command | What it does |
| ------- | ------------ |
| `./safe-deploy.sh --dry-run` | show what would happen, change nothing |
| `./safe-deploy.sh --backup` | back up the database and `storage/`, stop |
| `./safe-deploy.sh` | back up, build, start, verify — roll back if it fails |

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
  `app/services/photos.py` for whatever the Bundle Inspection app needs.

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
| 7 | Notifications — email | statuses that trigger a message | receives the email | **Done, never sent for real** |
| 9 | Deployment | — | — | **Done, no server yet** |
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

### Still to build, both sides

| Step | Admin Console side | Customer Portal side |
| ---- | ------------------ | -------------------- |
| **Photos from the Bundle app** | pull photos from the existing Bundle Inspection app instead of uploading them by hand | (gallery already built in step 15) |
| **Notifications — WhatsApp** | choose which statuses message which channel | receives the WhatsApp message |
| **Self-service password reset** | — | "forgot password" email; blocked on real SMTP |
| **SAP/PMS auto-pull** | replace the hand-run CSV import with a scheduled pull | — |

### What blocks the ones that are blocked

1. **A server.** `safe-deploy.sh` exists and has been proved end to end on a
   local Docker stack, including five rollback drills. What is missing is a
   machine to run it on and a DNS record pointing portal.alokindia.co.in at
   it. Both need the user, or whoever runs alokindia.co.in.
2. **The SAP/PMS question, still unanswered.** How can order data leave
   SAP/PMS — a spreadsheet export, a readable database, an API, or not at
   all? And does SAP/PMS hold the vessel name, IMO and container number, or
   does that sit with the CHA / freight forwarder and the Bill of Lading?
   The importer is finished and waiting; only the mapping depends on this.
3. **Real SMTP credentials**, then one careful test email to a colleague,
   before any customer address goes on the list. This also unblocks
   self-service password reset.
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

### Known issues / risks

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
- **A customer who forgets their password must ask staff.** There is no
  "forgot password" email, because there is no working SMTP yet.
  `scripts.manage_users --reset-password` is the answer today, and it puts the
  account back on a temporary password that must be changed on next sign-in.
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
- **Nobody has received a real email yet.** Sending was proved against a
  local test mail server only. Real SMTP credentials and one careful test to
  a colleague are needed before any customer is on the list.
- **WhatsApp is not built.** It needs a WhatsApp Business account and a
  pre-approved message template through Twilio or Meta's Cloud API. The
  channel would slot into `app/services/notifications.py` alongside email.
- **Nothing triggers notifications automatically.** `python -m scripts.notify` must be run
  after each import, by hand or on a schedule.
- **Photos are served at full size, every time.** There are no thumbnails:
  the gallery downloads each photo in full to draw a 116-pixel tile. A
  shipment with twenty 4 MB photos from a phone will be slow on a bad
  connection, and an export customer is usually on one. Generating
  thumbnails needs an image library (Pillow), which is not installed.
- **Nothing stops the same photo being uploaded twice.** Documents are
  deduplicated by type; photos have no equivalent, so a double click on
  Add photos leaves two identical tiles that must be removed one at a time.
- **A photo's caption cannot be changed after upload.** It is set once for
  the whole batch. Fixing a typo means removing the photo and adding it
  again.
- **An order's status is set by hand and not derived from its shipments.**
  Nothing stops an order reading "In production" while every shipment
  against it says Delivered. Deriving it would be better, and is a
  judgement call about part-shipped orders that has not been made yet.
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
- **The frontend has no tests.** The 145 committed tests are all backend.
  Nothing checks that the progress track draws, that the photo gallery
  revokes its blob URLs, or that a backwards status change asks before it
  saves. `npm run build` passing only means it compiles.
- **MarineTraffic shows a vessel's current position, not the cargo.** It
  cannot confirm a container or parcel is aboard, and free pages can be rate
  limited or blocked. A paid carrier API is the answer if customers need
  guaranteed, shipment-level tracking.
