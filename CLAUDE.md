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

- **Step 2 — Real security.** Enforce the login token so `/api/orders` only
  answers signed-in customers, each seeing ONLY their own orders. Add tables:
  `customers`, `users`, `shipments`, `documents`.
- **Step 3 — Order detail page.** Balance quantities (Ordered / Dispatched /
  Balance) and the list of part-shipments, each with its own status, documents
  and vessel.
- **Step 4 — Documents.** Store and let customers download Packing List,
  Commercial Invoice, Bill of Lading, Mill Test Certificates per shipment.
- **Step 5 — Real data.** Feed real order data from our systems (SAP/PMS);
  capture each shipment's vessel and IMO number.
- **Step 6 — Shipment tracking.** A "View live on MarineTraffic" link using the
  vessel's IMO; a paid carrier tracking API later.
- **Step 7 — Notifications.** Email/WhatsApp on Shipped/Arrived, then a pilot
  with one friendly customer.

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
| 2026-09-08 | Demo email + password moved out of code into `.env` (backend and frontend); credentials removed from the repo | _this commit_ |

### Known issues / risks

- **The login token is not enforced yet.** `GET /api/orders` answers anyone who
  asks, signed in or not. Fixed in Step 2.
- **Demo authentication is temporary.** One demo account, with its email and
  password read from `.env` (never committed). Replaced by real customer
  accounts in Step 2.
- `safe-deploy.sh` **does not exist yet** — it must be written before the first
  deployment.
