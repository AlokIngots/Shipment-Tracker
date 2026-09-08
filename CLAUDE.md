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

1. **Never work directly on `main` or `dev`.** Always a feature branch. Commit
   often. Merge to `dev` only via a Pull Request the user opens on GitHub.
2. **Before changing existing code, commit the current state first** as a
   restore point, and tell the user the rollback command.
3. **Never commit secrets or junk:** no `.env`, no passwords, no customer
   files/PDFs, no `node_modules`, no build folders.
4. **Going live later uses `./safe-deploy.sh`** (it backs up the database).
   Never run `docker compose build` directly.
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

**Step 1 (the skeleton) is done and working** — login → order list from the real
database — committed on `feature/scaffold`. **Not yet pushed to GitHub.**

## Immediate next actions

To be done when the user says "continue", after they have run `gh auth login`:

1. ~~Move the demo password out of `backend/demo_auth.py` into `.env`~~ **Done.**
2. Create the **private** GitHub repo `alok-customer-portal`, add it as
   `origin`, and push `main`, `dev` and `feature/scaffold`.
3. Give the user click-by-click steps to open a Pull Request from
   `feature/scaffold` into `dev`. **Do not merge it.**

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
| 2026-09-08 | **Step 7 (email) — Notifications.** `notifications` table, `notifier.py` and `notify.py`; sends once per shipment status per user, with `SEND_EMAILS` and `NOTIFY_ONLY_EMAILS` safety switches. WhatsApp and the pilot still outstanding | _this commit_ |

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

### Known issues / risks

- **No database migrations yet.** Schema changes currently rely on
  `seed.py --reset`, which destroys data. Alembic (or equivalent) is needed
  before any real customer data goes in.
- **Tokens cannot be revoked.** They are signed and stateless, valid until
  they expire (12 hours). Changing `SECRET_KEY` signs everyone out.
- **The token is held in browser memory only**, so a page refresh signs the
  user out. Fine for now; revisit when the portal goes to real customers.
- **Accounts are still seeded from `.env`**, not created by anyone. Two demo
  customers exist so that isolation can be tested. Real account management is
  still to come.
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
- `safe-deploy.sh` **does not exist yet** — it must be written before the first
  deployment.
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
