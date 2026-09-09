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

## How to work

Do **ONE step at a time**. Finish it, test it, report clearly what was done and
how it was proved — then **STOP and wait**. When the user says "continue", move
to the next step. Never run ahead through multiple steps at once.

---

## Where we are now

**Last worked on: 9 September 2026.** All seven roadmap steps are built, plus
deployment, database migrations and customer accounts. Every feature has been
tested end to end, and
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
| `feature/step11-accounts` | 11 — real customer accounts (tip) |

Every step is merged into `dev`, so the per-step branches above are history
now. Start the next step with a fresh branch off `dev`.

**`dev` is the branch to work from.** **`main` is still the empty anchor
commit, deliberately** — it gets its first real content only when the portal
has actually been deployed to a real server and proved to work there.

### How to run it locally

```bash
docker compose up -d                                     # database
cd backend && .venv/Scripts/python.exe seed.py           # demo data
.venv/Scripts/python.exe -m uvicorn main:app --port 8000 # API
cd ../frontend && npm run dev                            # http://localhost:5173
```

Demo logins are in `.env` (never committed). Both `.env` and `frontend/.env`
are needed; copy each `.env.example` if they are missing.

### Staff tools (all in `backend/`)

| Command | What it does |
| ------- | ------------ |
| `python manage_users.py --list` | every customer, and who can sign in for them |
| `python manage_users.py --add-customer CODE --name N` | add a customer |
| `python manage_users.py --add-user EMAIL --customer CODE` | give somebody a login; prints a temporary password once |
| `python manage_users.py --reset-password EMAIL` | issue a new temporary password |
| `python manage_users.py --deactivate EMAIL` | stop somebody signing in, at once |
| `python manage_users.py --activate EMAIL` | let them back in |
| `python migrate.py` | bring the database schema up to date, losing nothing |
| `python migrate.py --status` | where the schema is, and whether the code agrees |
| `python migrate.py --sql` | the SQL a migration would run, executing nothing |
| `python seed.py` | load demo data (`--reset` drops everything first) |
| `python import_data.py FILE.csv --dry-run` | check a data file, change nothing |
| `python import_data.py FILE.csv` | import orders and shipments |
| `python add_document.py --list` | show which documents are uploaded or missing |
| `python add_document.py --shipment X --type Y --file Z` | attach a document |
| `python notify.py --dry-run` | show who would be emailed |
| `python notify.py --preview` | print the full text of one email |
| `python notify.py` | send (only if `SEND_EMAILS=true`) |
| `python seed.py --schema-only` | migrate the schema only, never demo data |

`--dry-run` works on every `manage_users.py` command that changes something.

### Setting up a real customer

```bash
python manage_users.py --add-customer HANSA --name "Hansa Stahl GmbH" --country Germany
python manage_users.py --add-user einkauf@hansa-stahl.de --customer HANSA --full-name "Petra Baumann"
```

The second command prints a temporary password **once** — it is stored as a
hash, so nobody, including the server, can read it back. Send it the way you
would send anything else confidential, and not in the same message as the
portal address. The portal then makes that person choose their own password
before it will show them a single order, and the API enforces that, not just
the screen.

On the server the same commands run inside the API container:

```bash
docker compose -f docker-compose.prod.yml exec api python manage_users.py --list
```

### Deploying (from the project root)

| Command | What it does |
| ------- | ------------ |
| `./safe-deploy.sh --dry-run` | show what would happen, change nothing |
| `./safe-deploy.sh --backup` | back up the database and `storage/`, stop |
| `./safe-deploy.sh` | back up, build, start, verify — roll back if it fails |

Set `PORTAL_DOMAIN` in `.env`: a real domain makes Caddy obtain HTTPS
automatically; `:80` serves plain HTTP for testing on your own machine.

## What is left before a real customer can use this

In the order that matters:

1. **A server.** `safe-deploy.sh` now exists and has been proved end to end on
   a local Docker stack — including five rollback drills, two of them for
   failed migrations. What is missing is a machine to run it on, and a DNS
   record pointing portal.alokindia.co.in at that machine. Both need the
   user, or whoever runs alokindia.co.in.
2. **The SAP/PMS question, still unanswered.** How can order data leave
   SAP/PMS — a spreadsheet export, a readable database, an API, or not at all?
   And does SAP/PMS even hold the vessel name and IMO number, or does that sit
   with the CHA/freight forwarder? The importer is finished and waiting; only
   the mapping into its CSV depends on this answer.
3. **Real SMTP credentials**, then one careful test email to a colleague,
   before any customer address goes on the list. This also unblocks
   self-service password reset, which is the one part of accounts still
   missing: a customer who forgets their password has to ask staff for a
   new one today.

## Roadmap

One step each time the user says "continue".

- ~~**Step 2 — Real security.**~~ **Done** — see progress log.
- ~~**Step 3 — Order detail page.**~~ **Done** — see progress log.
- ~~**Step 4 — Documents.**~~ **Done** — see progress log.
- **Step 5 — Real data.** _Import pipeline built and tested_ (`backend/import_data.py`, CSV format documented in `docs/import-template.csv`). **Blocked on one answer: how SAP/PMS can export.** Once that is known, the remaining work is mapping that export into the CSV and scheduling it.
- ~~**Step 6 — Shipment tracking.**~~ **Done** — see progress log.
- **Step 7 — Notifications.** _Email built and tested_ (`notify.py`,
  `notifier.py`). **WhatsApp not built** — needs a WhatsApp Business account
  and an approved template through a provider. **The pilot has not happened
  yet**, and cannot until the portal is actually deployed.

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
| 2026-09-09 | **Step 11 — Real customer accounts.** `manage_users.py` for staff: add a customer, give somebody a login with a one-time temporary password, reset it, deactivate or reactivate, all with `--dry-run`. Migration 0002 adds `must_change_password`; every customer-facing endpoint now refuses anybody still holding a temporary password, while `/api/me` and the new `POST /api/change-password` stay reachable so the portal can explain why. A password screen in the portal, forced on first sign-in and available by choice afterwards. Proved end to end on the deployed stack, including that migration 0002 reached a database with rows in it and kept them | `6c82e65` |
| 2026-09-09 | **Step 10 proved by deployment.** Real deploy of the migration code: the production database, whose tables predated migrations, was adopted at 0001 with nothing created or dropped. Two failure drills — a migration followed by a failing health check, and a migration that applied then reported drifted models — both put the schema back to 0001 and restored the previous image, with all rows untouched. The second drill found a real bug in the new deploy code, now fixed | `ef76e52` |
| 2026-09-09 | **Bug fix — UI text.** The order detail page showed the literal text `Loading order…` while loading, because a JSX text node is not a JavaScript string. Now renders `Loading order…` | _this commit_ |

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
  constraint in the database, so re-running `notify.py` cannot spam anyone.
- **Only a message that actually went out counts as done.** A suppressed or
  failed attempt is recorded, but is retried on the next run and its row is
  updated in place. This is what makes it safe to run `notify.py` from day one
  with `SEND_EMAILS=false` and switch sending on later without losing anyone.

### Design decisions worth remembering

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
- **`migrate.py --status` compares the code against the real database** and
  names, in plain words, anything a model has that the database does not.
  Forgetting to write a migration is the mistake this will meet most often,
  and it otherwise stays silent until something breaks.

### Known issues / risks

- **Tokens cannot be revoked.** They are signed and stateless, valid until
  they expire (12 hours). Changing `SECRET_KEY` signs everyone out.
- **The token is held in browser memory only**, so a page refresh signs the
  user out. Fine for now; revisit when the portal goes to real customers.
- **A customer who forgets their password must ask staff.** There is no
  "forgot password" email, because there is no working SMTP yet.
  `manage_users.py --reset-password` is the answer today, and it puts the
  account back on a temporary password that must be changed on next sign-in.
- **An account can be deactivated but not deleted.** Deactivating is nearly
  always what is actually wanted — a deleted login takes its history with it —
  but there is no tidy way to remove one created by mistake except SQL.
- **Nothing checks that an email address is real.** `--add-user` accepts
  whatever it is given, so a typo creates an account nobody can sign in to.
  Check the address before pressing enter; `--list` will show it.
- **Two demo customers still exist** so that customer isolation can be tested.
  They are created by `seed.py` from `.env` and must never be seeded onto a
  server holding real customers — that is why deploys run migrations only,
  and never `seed.py` without `--schema-only`.
- **Shipment and vessel data is still invented** for the demo. The importer is
  ready; real values arrive once the SAP/PMS export is settled.
- **The demo database now also holds `CUST-100` / `CUST-101`** from importing
  the template. They have no users, so nobody can sign in as them.
- **Documents are uploaded by staff from the server** using
  `backend/add_document.py`. There is deliberately no upload endpoint on the
  API, so nothing customer-facing can write files. A staff web UI is a
  later job.
- **Document files live in `storage/`**, which is git-ignored and must be
  included in server backups — `safe-deploy.sh` will need to cover it.
- **`seed.py --reset` clears the database but leaves document files behind**
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
  channel would slot into `notifier.py` alongside email.
- **Nothing triggers notifications automatically.** `notify.py` must be run
  after each import, by hand or on a schedule.
- **MarineTraffic shows a vessel's current position, not the cargo.** It
  cannot confirm a container or parcel is aboard, and free pages can be rate
  limited or blocked. A paid carrier API is the answer if customers need
  guaranteed, shipment-level tracking.
