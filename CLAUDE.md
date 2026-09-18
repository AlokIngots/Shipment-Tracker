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
   are signing in (by password or by email link, side by side since
   18 Sep 2026) and changing your own password, none of which touch
   customer data. See
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

**Step 46, password sign-in beside the email link (18 September 2026),**
is on `feature/password-login` (restore tag `pre-password-login`), pushed,
**waiting for Alok's OK to merge, not deployed.** No migration: the
`password_hash` column has existed since 0001. Why: AWS SES started
refusing its credentials and, with sign-in by email link only, nobody could
get in. What it does: `PASSWORD_SIGN_IN` is on by default, so the sign-in
screen offers email + password and still the email link; staff press
**Set password** on any login in Customers & logins and hand the password
over themselves (the customer is not made to change it);
`python -m scripts.set_password --email EMAIL` does the same on the server,
typed without echo; a session lasts `SESSION_TTL_DAYS` (30) and survives
closing the browser (the token moved from sessionStorage to localStorage),
and Sign out ends it in every tab. `TOKEN_TTL_SECONDS` is no longer read.
A temporary password now holds back only somebody who signed in WITH it,
never somebody who came by link (the token says which) — before, switching
passwords on would have stuck every link-only customer on a "choose your
password" screen asking for a password they never had.

**On the server, when it is deployed:** the server's `.env` was copied from
the old example, so it very likely says `PASSWORD_SIGN_IN=false` and
`TOKEN_TTL_SECONDS=43200`. Change the first to `true` (the second is now
ignored; `SESSION_TTL_DAYS=30` can be added but is the default).

**Last worked on: 17 September 2026.** Steps 1–29 and 31–43 are built,
merged to `dev` **and deployed**. Nothing is merged and waiting to go out.

**Step 44, live container tracking from ShipsGo, is merged to `dev`
(`374abf0`, 17 Sep 2026) and NOT deployed** — Alok deploys it. It
carries **migration 0013** (a new `shipment_tracking` table), so its
deploy is a schema change: `safe-deploy.sh` backs up and runs it. Before
or after that deploy, put `SHIPSGO_API_KEY` in the server's `.env` and run
`python -m scripts.shipsgo_check` in the api container (read-only, spends
nothing) to prove the key works and reads cost nothing. Restore tag
`pre-shipsgo-tracking`.

**Confirmed by Alok on 17 September 2026:** steps 39, 40, 41 and 43 are
deployed and live, and step 42's sample-data removal has been **run on the
server** — the sample orders and customers are gone and the only order on
the live portal is the real Bucher order, EXP-043. None of 39–43 carried a
migration, so the schema is still **0012**. (The exact deploy date and
backup name were not recorded here.)

**The portal is live and current** at https://portal.alokindia.co.in on
srv1427359. On **16 September 2026** `dev` at step 37 (`4a86156`) was
deployed there: `safe-deploy.sh` ran clean, the schema is at **0012**, and
the API and website came up healthy. So steps 35, 36 and 37 — container
tracking, the staff Track panel, and the honest order detail with no vessel
map — are live, on top of the 15 September deploy that carried steps 28,
29, 31, 32, 33 and 34 with migrations 0009 and 0011. Magic-link sign-in is
confirmed working live.

**The first real order is on the live portal.** The Bucher order,
**EXP-043**, was entered through the staff screens on 16 September 2026 and
checked from the other side — Alok signed in as that customer and saw it.
So the portal holds real customer data now, and the tracking work of steps
35–37 has been seen on a real screen with a real shipment on it, which is
what the three "not opened in a browser" caveats in the progress log were
waiting for.

Email works there: on 11 Sep 2026 the server's `.env` was set to
`SEND_EMAILS=true` with AWS SES SMTP (region ap-south-1, sending from
enquiries@alokindia.com), and a real sign-in link was received and used.
**`NOTIFY_ONLY_EMAILS` is set to the owner's address on the server**, so
step 33's automatic sender — which is live — can reach nobody else however
many customers are in the database. Leave it that way until a real customer
is meant to start receiving mail.

The user deploys to the server themselves; this PC has no SSH to it.

**The two conditions that used to gate a deploy are both met** and are
history: the 11 Sep sign-in link was received, and order status coming from
the shipments rather than being typed was accepted. Nothing gates a deploy
today except the usual: a green test run, a backup, and the user saying go.

**What is live from steps 39–43.** Step 39, the pilot-readiness fixes:
sign-in links no longer go through `NOTIFY_ONLY_EMAILS`, documents are
served as what they really are, and the front door sends a
Content-Security-Policy and HSTS. Step 40, the sign-in link signing people
in by itself with no Continue button. Step 41, customers told by email when
their documents are ready. Step 43, the customer's order page sends nobody
to a carrier's website; the container and B/L numbers have Copy buttons
instead. Step 42 was a one-off run on the server, not a deploy, and it is
done.

**Steps 33 and 41 still reach no real customer until that customer's
address is on `NOTIFY_ONLY_EMAILS` on the server**, which gates every
notification (but no longer sign-in links) and is the one line that
switches them on. There is a real customer in the database, so check that
setting before every deploy.

Two things from steps 39 and 43 could only be proved live and are **not
recorded here as checked**: the security headers
(`curl -sI https://portal.alokindia.co.in`, then open a photo and download a
document, because a wrong CSP breaks those silently) and the Copy buttons
pressed in a real browser.

Before that: step 38 — the staff orders list collapsed into slim rows — was
deployed on **16 September 2026** (`safe-deploy.sh` clean, backup
`2026-09-16_050439`, seen live).

**Step 30, "Forgot your password", is held unmerged** on
`feature/step30-password-reset` (`a37b9b7`) on the user's decision: do not
merge or delete it without asking.

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

**Restore point:** tag `pre-single-use-default` is `dev` with sign-in links
reusable, before that default was reversed. Nothing needs reverting to get
reusable links back: set `MAGIC_LINK_SINGLE_USE=false` in the server's
`.env` and recreate the api container.

**Restore point:** tag `pre-longer-signin-links` is `dev` after step 33,
before step 34 (24-hour reusable sign-in links). Undo it on `dev` with
`git revert --no-edit pre-longer-signin-links..dev`. There is no migration
to take back. Faster than a revert, and needing no deploy: set
`MAGIC_LINK_SINGLE_USE=true` and `MAGIC_LINK_TTL_SECONDS=900` in the
server's `.env` and recreate the api container. Links already in inboxes
keep whatever expiry they were issued with; only new ones change.

**Restore point:** tag `pre-auto-notify` is `dev` after step 32, before
step 33 (notifications that send themselves). Undo it on `dev` with
`git revert --no-edit pre-auto-notify..dev`. If it was already deployed,
first take the database back with
`docker compose -f docker-compose.prod.yml exec api python -m alembic downgrade 0009`
— that drops the two columns counting attempts and nothing else. Reverting
does not un-send anything already emailed, and does not need to: the record
of what was sent is what stops anybody being told twice, and it stays.

**Restore point:** tag `pre-magic-link-only` is `dev` after step 29, before
step 31 (sign-in by email link only). Undo it on `dev` with
`git revert --no-edit pre-magic-link-only..dev`. There is no migration. On a
server already running it, an email failure does not need a revert: see
"If email fails" under "Deploying". Since step 32 one setting brings the
password sign-in back, screen included.

**Restore point:** tag `pre-password-escape-hatch` is `dev` after step 31,
before step 32 (the password box comes back while `PASSWORD_SIGN_IN` is
on). Undo it on `dev` with
`git revert --no-edit pre-password-escape-hatch..dev`. No migration.

**Restore point:** tag `pre-container-tracking` is `dev` after step 34,
before step 35 (the Track container button). Undo it on `dev` with
`git revert --no-edit pre-container-tracking..dev`. If it was already
deployed, first take the database back with
`docker compose -f docker-compose.prod.yml exec api python -m alembic downgrade 0011`
— that drops the one `carrier` column and nothing else. Faster than a
revert and needing no deploy: a carrier nobody recognises gets no button,
so emptying `shipments.carrier` turns the feature off wherever it is wrong.

**Restore point:** tag `pre-carrier-fallback` is `dev` after step 35,
before step 36 (the live map, staff tracking, and Evergreen's fallback).
Undo it on `dev` with `git revert --no-edit pre-carrier-fallback..dev`.
There is no migration to take back. Two smaller undos need no revert and no
deploy: setting `VESSEL_MAP_URL_TEMPLATE` to anything without `{imo}` in it
removes the map and leaves the link, and setting
`CARRIER_URL_EVERGREEN_BL` puts a container deep link back.

**Restore point:** tag `pre-honest-tracking` is `dev` after step 36, before
step 37 (the vessel map and vessel link removed). Undo it on `dev` with
`git revert --no-edit pre-honest-tracking..dev` — but read why it was done
first: it puts back a map that tells a transshipped customer their cargo is
going the wrong way. There is no migration either way.

**Restore point:** tag `pre-compact-orders` is `dev` after step 37, before
step 38 (the staff orders list collapsed into rows). Undo it on `dev` with
`git revert --no-edit pre-compact-orders..dev`. There is no migration and no
API change, so a revert is the whole undo; the staff screen goes back to a
page of opened cards and nothing else moves.

**Restore point:** tag `pre-shipsgo-tracking` is `dev` after the SAP notes,
before step 44 (live tracking from ShipsGo). Once merged, undo it on `dev`
with `git revert --no-edit pre-shipsgo-tracking..dev`. If it was already
deployed, first take the database back with
`docker compose -f docker-compose.prod.yml exec api python -m alembic downgrade 0012`
— that drops the `shipment_tracking` table and nothing else. The shipments
already added stay in the ShipsGo account; enabling them again later finds
them by B/L and costs nothing. Faster than a revert and needing no deploy:
empty `SHIPSGO_API_KEY` and recreate the api container — nothing is sent to
ShipsGo, Enable is refused, and customers keep seeing the last stored copy
(Stop tracking on a shipment hides it).

**Restore point:** tag `pre-remove-carrier-box` is `dev` after step 44,
before step 45 (the staff "Track this container on <carrier>" box
removed). Undo it on `dev` with
`git revert --no-edit pre-remove-carrier-box..dev`. Frontend only: no
migration, no API change.

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

213 tests, about a minute, with the dev database up. They build their own
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
| `python -m scripts.set_password --email EMAIL` | set somebody's password, typed twice and never shown; not temporary; signs them out everywhere. Staff can use it on their own account — the admin console refuses that |
| `python -m scripts.manage_users --reset-password EMAIL` | issue a new temporary password; signs them out everywhere, and is the way back in during an email failure with `PASSWORD_SIGN_IN` on (see "If email fails") |
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
  links write only sign-in bookkeeping, and `POST /api/login` writes
  nothing.
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

**If email fails: getting back in with a password.** Since step 46
password sign-in is on by default and a password is set with
`scripts.set_password`, so the quickest way in is, on srv1427359:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.server.yml exec api python -m scripts.set_password --email you@alokindia.com
```

— then sign in with that email and password. The older route below (step
32) still works where step 46 is not deployed. In the project folder on
srv1427359:

1. Add `PASSWORD_SIGN_IN=true` to `.env`, then recreate the API so it reads
   it (a plain `restart` does not re-read `.env`):
   `docker compose -f docker-compose.prod.yml -f docker-compose.server.yml up -d --force-recreate --no-build api`
2. The sign-in screen shows the password box again at its next load, with
   no rebuild. Anybody who does not know a password gets a temporary one:
   `docker compose -f docker-compose.prod.yml -f docker-compose.server.yml exec api python -m scripts.manage_users --reset-password EMAIL`
3. They sign in with it, and the portal makes them choose their own before
   showing anything else.
4. Once email works again, set `PASSWORD_SIGN_IN=false` and recreate the API
   the same way. The password box goes and link-only is back.

**Removing the sample data from the live server** — **done**: this was run
on the live server (confirmed 17 Sep 2026) and only the real Bucher order
remains. Kept here for a demo database. Four sample orders were
loaded for a demo (`deploy/sample-data/sample-data.sql`, run by hand with
`mode=load`). **Nothing re-creates them by itself** — `safe-deploy.sh` runs
migrations only, the API starts the notification timer and nothing else, and
`scripts/seed.py` is a development tool. To remove them, in the project
folder on the server, after a backup:

```bash
D="docker compose -f docker-compose.prod.yml -f docker-compose.server.yml exec -T db psql -U $POSTGRES_USER -d $POSTGRES_DB -q"
$D -v mode=remove < deploy/sample-data/sample-data.sql
```

It deletes `customers WHERE code LIKE 'SAMPLE-%'` and lets the foreign keys
cascade, so it can reach nothing that is not sample data, and running it
twice is harmless. It prints how many rows it found before deleting them and
how many real customers and orders remain. Two things it cannot undo: the
change history keeps its entries (deliberately append-only), and an email
already sent stays sent.

**Since 16 Sep 2026 the file refuses to `load` into a database that holds any
real order**, which is what the live server has. `-v allow_beside_real_data=yes`
overrides that, and should be needed only on a demo database.
`scripts/seed.py` refuses in the same situation, naming the real customers it
found.

**Rolling back a whole deploy on srv1427359**, in one line, run in the
project folder on the server:

```bash
C="docker compose -f docker-compose.prod.yml -f docker-compose.server.yml"; $C exec -T api python -m alembic downgrade 0008 && docker tag alok-portal-api:rollback alok-portal-api:latest && docker tag alok-portal-web:rollback alok-portal-web:latest && $C up -d --no-build
```

It takes the database back from 0009 to 0008 while the new version is
still running (the old one does not contain migration 0009, so it could not
undo it), then puts back the images `safe-deploy.sh` saved as `:rollback`
just before building the new ones. Worth knowing:

- `0008` is right only if the deploy printed "Schema moved from 0008 to
  0009". Use whichever "from" revision it printed.
- `:rollback` is overwritten by the next run of `safe-deploy.sh`, so this
  undoes the most recent deploy only.
- The server's git checkout is not moved. Put it back to the old commit
  before deploying again, or the next deploy brings the new code back.
- Downgrading 0009 refills the order status from the shipments; typed
  statuses cannot come back. The live portal holds no orders, so none are
  lost. For the database exactly as it was, the deploy also printed the
  path of its backup.

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
  `app/routers/admin/notifications.py` — taken in step 33 by the Messages
  screen and Send now,
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
| 22 | Ready to share a server | deploy on a host that already runs nginx, without touching it | — | **Done, deployed 15 Sep 2026** |
| 23 | Port 8090, and the nginx site in the repo | 8080 was taken by alok-crm-frontend | — | **Done, deployed 15 Sep 2026** |
| 24 | Who changed what | every change recorded with who, when and before → after; an Activity tab to read it; nobody can edit or remove it | (nothing — internal only, and customers cannot reach it) | **Done** |
| 25 | Photo previews | a small preview made at upload; a file that is not really a picture refused; a command for photos uploaded before | gallery tiles load the preview, clicking opens the original | **Done** |
| 26 | Sign in with an email link | staff can sign in by link too | "Sign in with email link" beside the password; single-use 15-minute link; same answer for any address; rate limited | **Done, live: a real link received and used on 11 Sep 2026** |
| 27 | Screens that fit | on a phone the toolbar, the four tabs and every row fit; no page scrolls sideways | every order-list column visible on any screen, order cards below 880px; the whole progress track and the totals fit a phone | **Done, not seen on a real phone** |
| — | Easy for real users (`feature/easy-usability`) | quick actions above the tabs (Add customer, Add customer login, New order, Upload document); a "Start here" 1-2-3 checklist on empty screens; plain labels; no screen mentions a server command | plain labels (Order status, Your documents, Track your shipment); friendly empty and error states with Try again | **Done, deployed 15 Sep 2026** |
| 28 | Order status from shipments | the order form shows the status instead of asking for it; a Cancelled tick on the order; a Last shipment tick on each shipment; a reminder when nearly all of an order has gone and nothing is ticked; `last_shipment` in the CSV importer | the order says Part shipped until the last lot is ticked, then follows the lot furthest behind; "final shipment" on that lot | **Done, deployed 15 Sep 2026** |
| 29 | Hidden details out of full-size photos | every photo saved without its camera, time and GPS position as it is uploaded; a line on the photo box says so; a command cleans photos uploaded before; phone photos with a second picture inside (MPO) accepted instead of refused; a photo cut short refused | the full-size photo they download carries only the picture | **Done** |
| 30 | Forgot your password (`feature/step30-password-reset`, `a37b9b7`) | Email reset link on each login | "Forgot your password?" on the sign-in card | **Built, held unmerged** on the user's decision, 11 Sep 2026; moot while sign-in is link-only. Do not merge or delete without asking |
| 31 | Sign in by email link only (`feature/magic-link-only`) | no Change password or Reset password button; Add customer login says "tell them to sign in with email link" instead of showing a temporary password; the four quick actions unchanged | the sign-in card has only the email box and Sign in with email link: no password box, no password Sign in button, no "or"; no Change password button | **Done, deployed 15 Sep 2026** |
| 32 | The escape hatch (`feature/password-escape-hatch`) | with `PASSWORD_SIGN_IN` on, `manage_users --reset-password` gives a temporary password to sign in with; a written "If email fails" procedure | the password box, the password Sign in button and "or" come back on the sign-in card only while the server switch is on; hidden while it is off | **Done, deployed 15 Sep 2026** |
| 33 | Notifications send themselves (`feature/step33-auto-notify`) | the API sends whatever is waiting on a timer, `NOTIFY_EVERY_MINUTES`, with only one sender at a time however many workers or containers are up; a **Messages to customers** tab showing what is waiting, what was sent, held back or failed, and how many tries it took; a Send now button; `scripts/notify.py` still works and now shares the same loop | the customer is told when their shipment moves, without anybody at Alok Ingots remembering a command | **Done, deployed 15 Sep 2026** |
| 34 | Sign-in links that last a day (`feature/step34-longer-signin-links`, `feature/step35-single-use-default`) | `MAGIC_LINK_TTL_SECONDS` is 24 hours, not 15 minutes. A link is still spent on first use: `MAGIC_LINK_SINGLE_USE` defaults true, and false is there if email scanners ever do start spending links. `GET /api/sign-in-options` now tells the screens the rules so they cannot state them wrongly | the link in the inbox still works the next morning; the email and the sign-in screen say what is actually true | **Done, deployed 15 Sep 2026** |
| 35 | Track the box, not the ship (`feature/step35-container-tracking`) | a Shipping line field on the shipment form and a `carrier` column in the CSV importer; a per-carrier registry of tracking URLs, each overridable from `.env`; Evergreen Line first | a **Track container** button on each shipment, opening the carrier's own page by B/L or container number, with the carrier's search page as the fallback that always works | **Done, deployed 16 Sep 2026**; Evergreen's deep link still unverified, so the button opens the carrier's search page |
| 36 | The map on the page, and tracking for staff (`feature/step36-live-vessel-map`) | a **Track** button on each shipment row opens the same map and the same buttons the customer sees, built by the same function, so nobody needs a customer login to follow a shipment | the vessel's live position embedded in the order detail rather than behind a link, the MarineTraffic link kept as the fallback, and Evergreen's **Track container** button now opening its search page with the B/L and container number shown beside it to copy | **Superseded by step 37**: the map and the vessel link were removed before either was ever deployed. What survives from this step is the staff Track panel and one shared `links_for()`, both **deployed 16 Sep 2026** as part of step 37 |
| 37 | Honest tracking (`feature/step37-honest-tracking`) | the Track panel keeps the carrier link and the copyable numbers; no map, no vessel link | the vessel map and "See where the vessel is now" are gone, because a transshipped hull's position is a different voyage. What is left is the status timeline, the shipment facts, the copyable B/L and container numbers, and one clearly-worded **Track this container on <carrier>** button. Plus a light readability pass on the order detail | **Done, deployed 16 Sep 2026**, and seen live on the first real order |
| 38 | A staff orders list you can scan (`feature/step38-compact-staff-orders`) | every order is one slim row — order number, customer and grade, dispatched of ordered, status, shipment count — shut until it is clicked. Open, it is exactly what the card held before: the three totals, the shipments with Track, Edit, Documents & photos and Remove, and Add shipment / Edit order / Remove order. Several rows can be open at once, the open ones are remembered for the browser tab, a just-saved order opens itself, and Collapse all appears while anything is open. The "no shipment ticked as the last one" warning shows on the shut row, so it cannot hide | (nothing — the customer screens are untouched, at the user's request) | **Done, deployed 16 Sep 2026** |
| 39 | Ready for a pilot customer (`fix/pilot-readiness`) | sign-in links stop obeying `NOTIFY_ONLY_EMAILS`, which still gates the automatic notifications; a link that fails to send is an ERROR in the log **and** a "Sign-in links that did not arrive" card on the Messages screen; the pilot note on that screen says which is which; CI lints the website as well as building it | documents download as what they really are, so a mill test certificate scanned as a JPG opens; a Content-Security-Policy and HSTS on every page | **Done, deployed** (confirmed live 17 Sep 2026) |
| 45 | No carrier redirect anywhere (`feature/remove-carrier-redirect-box`) | the staff **Track** panel loses the "Track this container on <carrier> ↗" button, the paragraph about opening the carrier's website, and the boxed B/L / container numbers with Copy. It now holds live tracking only (Enable, or Refresh / Stop and the timeline). The B/L and container numbers stay in the shipment's one-line summary | unchanged: the box was already gone for customers (step 43). The B/L and container numbers stay in the shipment facts with their Copy buttons; a shipment without live tracking shows its facts and no timeline, and nothing links off-site | **Merged to `dev` 17 Sep 2026, not deployed. No migration** |
| 44 | Live container tracking from ShipsGo (`feature/shipsgo-tracking`) | inside each shipment's **Track** panel: **Enable tracking (1 credit)**, asked for with a warning and done once per shipment; then the ShipsGo reference, who turned it on and whether a credit was used, **Refresh now (free)**, **Stop tracking**, and the same timeline the customer sees. A timer reads every tracked shipment back every `SHIPSGO_REFRESH_EVERY_HOURS` (6). `scripts/shipsgo_check.py` checks the key read-only | a **Live tracking** panel under the shipment facts: status, from, to, loaded on, expected arrival, transshipment, container, and the container's movements (place · move · date · vessel), with a transshipment marked and both vessels named. "Tracking is updating…" until ShipsGo has news. Drawn from the stored copy; no page view calls ShipsGo | **Merged to `dev` 17 Sep 2026, not deployed. Migration 0013** |
| 43 | Nothing sends the customer away (`feature/remove-tracking-redirect`) | staff keep the Track panel and the carrier link: looking a box up is part of answering the phone | the **Track this container on \<carrier\>** button and the paragraph about opening the carrier's website are gone. The six shipment facts stay, and the container and B/L numbers gain a small **Copy** button each, so the numbers are still one tap away without the portal handing the customer to somebody else's site | **Done, deployed** (confirmed live 17 Sep 2026) |
| 42 | The sample data goes, and stays gone (`feature/remove-sample-data`) | `mode=remove` takes the four sample orders, three sample customers and their logins off the live portal, saying how many it found; the loader now refuses a database that holds real orders, and `seed.py` refuses to put demo data beside real customers | nothing — but the four sample orders stop being what a real customer might see | **Done and executed**: `mode=remove` run on the server; only the real Bucher order remains (confirmed 17 Sep 2026) |
| 41 | Documents announce themselves (`feature/step41-document-notifications`) | nothing new to do: uploading a document is what sends the email, and the Messages tab lists what is waiting document by document. `NOTIFY_ON_DOCUMENTS` chooses which types speak | "Your Bill of Lading is ready", by email, without asking. Everything newly ready on one order arrives in **one** email however many documents and shipments it covers; a replaced document says nothing | **Done, deployed** (confirmed live 17 Sep 2026); reaches a customer only once they are on `NOTIFY_ONLY_EMAILS` |
| 40 | The sign-in link just signs you in (`feature/auto-redeem-signin`) | (nothing — staff sign in by the same link and get the same benefit) | the link from the email redeems itself as the page opens, showing "Signing you in…" and then the portal. No Continue button. An expired link still gets the "Link expired — Request a new link" screen, and a network failure gets Try again rather than a dead end | **Done, deployed** (confirmed live 17 Sep 2026) |

### Still to build, both sides

| Step | Admin Console side | Customer Portal side |
| ---- | ------------------ | -------------------- |
| **39 — Shipping details that have nowhere to go** | fields for what the Bill of Lading holds and the portal cannot store: customer address and EORI number, the customer contact's name and email without creating them a login, order date and Shipping Bill number, load and discharge ports, ETD/ETA where they are known, voyage number and seal number, container size, and gross weight beside net | the route and the dates on the order detail, instead of only what the carrier's page happens to show |
| **Photos from the Bundle app** | pull photos from the existing Bundle Inspection app instead of uploading them by hand | (gallery already built in step 15) |
| **Notifications — WhatsApp** | choose which statuses message which channel | receives the WhatsApp message |
| **SAP auto-pull** (parked 17 Sep 2026 on the user's decision; see "SAP Business One" below) | a connector in the office reads new export sales orders and customers from SAP Business One and sends them to a staff-only endpoint; an order whose customer is not recognised waits for staff to link it | orders appear without anybody typing them |

### What blocks the ones that are blocked

1. ~~A server.~~ **Done:** the portal is live at https://portal.alokindia.co.in
   on srv1427359. The user deploys it.
2. **The SAP question — answered 17 Sep 2026, and the build is parked.**
   Orders leave SAP Business One through its Service Layer, read directly
   rather than through the PMS. SAP does **not** hold the vessel, container
   or B/L details in practice, and does not link invoices to orders. See
   "SAP Business One — what the look-only check found" below. **Do not
   build the SAP import until the user brings it back.**
3. ~~Real SMTP credentials.~~ **Done 11 Sep 2026:** AWS SES SMTP
   (ap-south-1), sending from enquiries@alokindia.com, `SEND_EMAILS=true` on
   the server, and a real sign-in link received and used. Order
   notifications have still not been sent to a customer.
4. **The Bundle Inspection app.** Material photos may be better pulled from
   it than uploaded by hand — but that needs to know what it stores and
   whether anything can read it.

### SAP Business One — what the look-only check found

On **17 September 2026** SAP was read, and nothing in it was changed, to
find out what an automatic order import could carry. **The user then parked
the import: do not build it until they bring it back.**

**The system.** SAP Business One, read directly through its Service Layer
(its web interface for other programs), not through the PMS. **The server
address, company database and security notes are deliberately not in this
repo**; they are kept with the login on the office PC (below).

**The hard rule: SAP credentials never go on the portal server or into
this repo.** The internet-facing portal must hold nothing that opens SAP.
An import, when built, is a small connector on the office side that signs
in with a **read-only** SAP user and sends only export orders to a
staff-only portal endpoint. The login and the look-only scripts live in
`%USERPROFILE%\.alok-sap\` on the office PC (`sap.env`,
`sap_lookonly.py`, `sap_fillrate.py`, and `NOTES.txt` for the connection
and security details), readable by the user's account only. The data those scripts saved is under `lookonly\` there and holds
customer details: it stays there. The first check used the user's own
login; a read-only user is being asked of the SAP partner.

**The connection needs care.** The scripts accept exactly one known
server certificate and refuse any other; if the SAP partner changes the
certificate, the scripts must be updated. Two security fixes have been
raised with the user for the SAP partner; the details are in `NOTES.txt`,
not here.

**What SAP holds:**

- **Export sales orders are document series 416**, with a customer
  reference like `AIMPL/S.O/EXP/047/2026-27` (also in `U_SO`). The
  customer's group ("Sundry debtors -Expo…"), the export tick
  (`TaxExtension.ImportOrExport`) and a foreign country agree with it.
- **Export invoices are series 419**, numbered `EXP-058/2026-27` in
  `U_InvNo`.
- **Customers** are matched on SAP's customer code (Bucher is `C00574`).
  The portal's `customers.code` can hold exactly that. Name, country,
  currency and bill-to/ship-to addresses are there.
- **Order header:** date, due date, currency, total, customer PO number
  and date (`U_POR`, `U_PORD`), payment terms (`U_PT`), Incoterm and port
  (`U_IN`), delivery (`U_Delivery`), shipment (`U_Ship`), packing
  (`U_Packing`).
- **Order lines:** item, description with grade and size, quantity in
  tons, open quantity, ship date, length (`U_Length`), heat treatment
  (`U_HT`), tolerance (`U_Tol`).

**Three problems:**

1. **No shipping details in practice.** Invoices have custom fields for
   container number and type, B/L number and date, vessel, seal, ports of
   loading and discharge, final destination, shipping bill, and gross and
   net weight. **They were empty on all 61 export invoices from April to
   September 2026.** Shipment details keep coming from staff through the
   Admin Console unless the team starts filling those fields in SAP.
2. **Invoices are not linked to sales orders.** Export invoices are raised
   directly rather than copied from the order, and there are no delivery
   notes. So SAP cannot say which order a shipment belongs to, 48 of the
   last 50 export orders still show fully open, and dispatched/balance
   cannot be read from SAP. Creating invoices with "Copy From" the sales
   order would fix it.
3. **What is the portal's EXP-043?** Bucher's SAP **sales order**
   `EXP/043/2026-27` and Bucher's **invoice** `EXP-043/2026-27` (27 July
   2026) both exist; the two series happen to meet at 043. Which one the
   portal's order was entered from is **still to be confirmed with the
   user**. If it was the invoice, the portal holds a shipment as an order.

**Open questions for the user:** the EXP-043 question above, and whether
the team would raise export invoices with "Copy From" the sales order.

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

| 2026-09-11 | **Step 31 — Sign in by email link only, both halves** (`feature/magic-link-only`, restore tag `pre-magic-link-only`). On the user's decision, the sign-in card keeps only the email box and **Sign in with email link**: the password box, the password Sign in button and the "or" divider are gone. (`dev` never had a "Forgot your password?" link; step 30, which adds one, is held unmerged.) The password code is **dormant, not deleted**. A new setting, `PASSWORD_SIGN_IN`, off unless `.env` says true, makes `POST /api/login` give everybody the same refusal before anything is looked up, and switches off the rule that keeps a person on a temporary password away from their orders. Without that second part, every new login would have signed in by link and then been asked for a temporary password nobody sent them. Switched back on, both work exactly as before. Staff lose the Change password and Reset password buttons; Add customer login now says "tell them to open the portal and press Sign in with email link" instead of showing a temporary password, and the Start here checklist says the same. Customers lose Change password. The four quick actions, `manage_users.py`, and the change-password and forced-password screens are all kept. The sign-in email and the too-many-links message no longer mention a password. Proved by 6 new tests (211 in all; every older test now runs with password sign-in switched on, as the proof the dormant code still works): a right password, a wrong one and an unknown address all get the same 403; a brand-new login signs in by link and sees its orders; a staff login signs in by link and adds a customer, a customer login, an order, a shipment and a document, and that customer then signs in by link and sees the order and the document; the email says nothing of a password; and switched on, the temporary-password rule is back. The frontend build passes, `manage_users --list` runs, and a headless Edge run on the development site passed 22 checks: one button on the sign-in card at desktop and phone width, no password box, no divider, no Forgot link, `/api/login` refused from the browser, no Change password or Reset password button on either half, all four quick actions open (Upload document onto Documents & photos with its Upload buttons), Add customer login shows the new note and no password, and no browser errors. The two runs left two development-only logins (`link-only-check-…@demo-customer.example`) and their change-history entries. A fresh sign-in link requested from the live server for mis@alokindia.com has **not arrived**; see Known issues. Merged to `dev` and pushed the same day on the user's OK; **not deployed** | `f1c8ac7` + _this commit_ |

| 2026-09-11 | **Step 32 — The escape hatch, both halves** (`feature/password-escape-hatch`, restore tag `pre-password-escape-hatch`). After step 31, `PASSWORD_SIGN_IN=true` reopened password sign-in in the API only: the sign-in screen had no password box, so if email ever failed nobody could get in from a browser. On the user's request, the sign-in card now asks the server, through a new read-only `GET /api/sign-in-options`, every time it loads, and shows the password box, the password Sign in button and the "or" divider only while the switch is on. Off, the normal state, it is exactly step 31's link-only card, and if the question cannot be answered it stays link-only. Switching needs no rebuild of the website. The recovery procedure is written under "If email fails" in "Deploying": switch on and recreate the API, `manage_users --reset-password` for anyone without a password, sign in, choose a password, switch off again once email works. Proved by 2 new tests (213 in all): the screen is told the switch's current state without signing in; and with the switch on, a staff member reset on the server signs in with the temporary password, is held to choosing a real one, then reaches the staff screens. The frontend build passes. One build of the development site was run in headless Edge against the API started first with the switch off, then with it on. Off, 9 checks: only Sign in with email link at desktop and phone width, no password box or divider, `/api/login` refused from the browser, no browser errors. On, 10 checks: the password box and both buttons back at desktop and phone width, nothing scrolling sideways, a login made by `manage_users --add-user` signed in with its temporary password, was made to choose its own and reached its orders, no browser errors. That run left one development-only login (`recovery-check-…@second-demo.example`). Merged to `dev` on the user's OK; **not deployed**, and deploying waits on the same two conditions as step 31 | _this commit_ |
| 2026-09-12 | **Step 33 — Notifications send themselves, both halves** (`feature/step33-auto-notify`, restore tag `pre-auto-notify`). Until now nothing reached a customer unless somebody at Alok Ingots remembered to run `python -m scripts.notify` on the server, which made “has the customer been told?” a question about a person's memory. The API now sends whatever is waiting on a timer of its own (`NOTIFY_EVERY_MINUTES`, 15 by default; 0 switches it off), started in a FastAPI lifespan. The sending loop moved out of the script into `notifications.run()`, so the timer, the new Send now button and the command all do exactly the same thing. Two senders cannot both send: whoever takes a PostgreSQL advisory lock sends and the other skips, which matters with more than one worker and during a deploy when two containers briefly overlap — skipping loses nothing, because what is waiting stays waiting. A fifth staff tab, **Messages to customers**, shows what is waiting and who it is for, what was sent, held back or failed with the server's own reason, how many tries it took, and how the sender is configured — including, in plain words, that email being off means messages are recorded but not delivered. Migration 0011 adds `notifications.last_attempt_at` and `attempts`, because a message suppressed in the morning and sent in the afternoon kept saying “morning”. **Numbered 0011, not 0010**: revision 0010 is already taken by the held-unmerged step 30 branch, and two files claiming one revision is the Alembic mistake with no clean way out. Proved by 16 new tests (229 in all, all passing); the migration drilled upgrade → downgrade → upgrade on a throwaway database with every row count unchanged; the frontend build and `npm run lint` clean; and a live run against a throwaway database and a local mail sink in which the timer, with nobody pressing anything, emailed a shipment marked Shipped, did not email it a second time, then caught a move to In transit about fifteen seconds later and emailed that. A headless Edge pass over the new tab at 1440 and 390px: five tabs all on screen and none off the edge, nothing scrolling sideways, both messages listed, Send now pressed for real and reporting back, no browser errors. The development database and the live one were not touched. **Not deployed** | _this commit_ |
| 2026-09-12 | **Step 34 — Sign-in links that last a day, and survive being opened** (`feature/step34-longer-signin-links`, restore tag `pre-longer-signin-links`). On Alok's decision a link now lasts 24 hours instead of 15 minutes, and keeps working until it expires however many times it is opened. **The reason given for the reusable half does not hold in this codebase, and Alok was told so**: the token travels in the URL fragment, which no browser ever sends to a server, and redeeming waits for a button press — both put there in step 26 precisely so that Outlook Safe Links and the like cannot spend a link. A scanner fetching the URL was proved to leave the token unseen by the server. The longer expiry stands on its own merits; the reusable half is a real security trade-off bought for a problem that was already solved, and is one environment variable away from being undone. `MAGIC_LINK_SINGLE_USE` is that variable, modelled on step 32's escape hatch: set it true and recreate the api container, no rebuild and no deploy. Asking for a new link still retires the old one, and a password change or reset still kills any link already sent — which now matter more, being the only things that end a link early. `GET /api/sign-in-options` also gained `link_lasts` and `link_single_use`, because two screens had “15 minutes” written into them by hand and would have started lying the moment the setting changed. The sign-in email was reworded honestly and still never mentions a password, which step 31 forbids — caught by a test, not by luck. Proved by 6 new tests (235 in all, all passing), the frontend build and lint clean, and a live run against a throwaway database and a local mail sink: the email says 24 hours and “more than once”, a scanner's GET reaches the server without the token, the same link then signed in three times in a row, asking again killed it, and the newest worked. **Not deployed** — this PC has no SSH to the server | _this commit_ |
| 2026-09-12 | **Reusable sign-in links reversed, on Alok's decision** (`feature/step35-single-use-default`, restore tag `pre-single-use-default`). Reusable links had been asked for so that email scanners could not spend a link before the customer reached it. Shown that this portal has never had that problem — the token travels in the URL fragment, which no browser sends to a server, and redeeming waits for a button press, both built in step 26 for exactly this — Alok chose single use. `MAGIC_LINK_SINGLE_USE` now defaults to true. **The 24-hour expiry stays**, which is what actually fixed the reliability complaint: a customer reading the email next morning no longer finds a dead link. Reusable is still one environment variable away and is kept tested, so the way out exists if a real scanner problem ever appears. A new test pins the reason single use is safe here — that the emailed address carries no token before the “#” and that fetching it leaves the link unused — so the property cannot quietly stop being true. Proved by 236 tests all passing, the frontend build and lint clean, and a live run against a throwaway database and a local mail sink: the portal and the email both say “works once, within 24 hours” and no longer mention reuse, the stored link lasts exactly one day, the first press signed in and the second was refused. **Not deployed** | _this commit_ |
| 2026-09-15 | **`dev@de723f0` deployed to the live server, by Alok.** `safe-deploy.sh` ran clean, the schema reported "Already up to date at 0011", the API and website came up healthy, and magic-link sign-in was confirmed working on the live site. This cleared the whole backlog in one go: steps 28, 29, 31, 32, 33 and 34 and the usability pass are now live, and migrations 0009 and 0011 are applied on the server. `NOTIFY_ONLY_EMAILS` is set to the owner's address there, so step 33's automatic sender — which is now running on the server — can reach nobody else whatever is in the database. The two conditions that had gated this deploy since 11 Sep are both met and are now history. No real customer has signed in yet | (deploy, no commit) |
| 2026-09-15 | **Step 35 — Track the box, not the ship** (`feature/step35-container-tracking`, restore tag `pre-container-tracking`). The vessel link answers "where is the ship", which is not what a buyer asks, so each shipment now also carries the shipping line and a **Track container** button that opens that carrier's own tracking page. Migration 0012 adds one nullable `shipments.carrier`, free text, left empty on every existing row rather than guessed from a B/L prefix. A per-carrier registry in `app/services/tracking.py` holds up to three URLs per line — by Bill of Lading, by container number, and the carrier's search page with nothing filled in — and adding a carrier is one entry and no code. Every URL can be corrected from `.env` (`CARRIER_URL_<CARRIER>_<BL|CONTAINER|HOME>`), because a carrier can change its tracking URL without warning and a deploy should not be the only way to follow. The B/L is preferred over the container, both being identifiers of the shipment but the B/L the carrier's own reference for that consignment. A container number failing its ISO 6346 check digit is never deep-linked, the same rule the staff form already applies. Carrier matching is loose — case, spacing and punctuation ignored, plus aliases — because staff copy the line off a Bill of Lading and will not type a code; an unrecognised line is stored and shown but gets no button, rather than a button leading nowhere. The customer side stays read-only and the server builds every URL, as the vessel link already did. Staff get a Shipping line field on the shipment form, the carrier on the orders screen summary, a `carrier` column in the CSV importer and template, and a Carrier entry in the activity record. **Evergreen Line is the only carrier in the registry, and its two deep links are unverified**: ShipmentLink refused every connection from this machine and its tracking form has historically been a POST, so the design always keeps a `home` fallback and tells the screen whether the link was prefilled — the button works either way and says "paste the container number" when it has to. Proved by 25 new database-free tests passing (registry matching, B/L preferred over container, a bad check digit never linked, the always-safe fallback, URL escaping, `.env` overriding a built-in and an empty override not deleting one) and a clean frontend build. **The full suite and the end-to-end half have not been run: Docker Desktop will not start on this PC, so there is no database.** 6 further end-to-end tests are written and waiting for one, taking the suite to 267 collected. Not deployed | `161a32f` + _this commit_ |
| 2026-09-15 | **Step 36 — The map on the page, staff tracking, and Evergreen's fallback** (`feature/step36-live-vessel-map`, restore tag `pre-carrier-fallback`). Three things, one branch. **The vessel's live position is now embedded in the order detail** instead of only behind a link, with the caption "Live position of the vessel — may pause when the ship is out of range." and the MarineTraffic link kept underneath as the fallback. It is an iframe the portal builds itself, from `VESSEL_MAP_URL_TEMPLATE`, and deliberately **not** VesselFinder's documented `<script>`: that script writes nothing but this iframe, and running it here would put third-party JavaScript in the portal's own origin, where the customer's sign-in token lives — a cross-origin frame cannot reach it. **No MMSI is stored and none is needed**: VesselFinder resolves the IMO the portal already holds, checked against WAN HAI 359 (IMO 9554092), whose embed answered with MMSI 563182400 and `configError:""`. **Evergreen's deep link is gone**, confirmed broken: both candidates opened on ShipmentLink's blank Quick Tracking form, so the button opens that search page and the screen shows the B/L and container number beside it, each with a one-tap Copy that degrades to selectable text when the clipboard is refused. **Staff get the same map and the same buttons** behind a per-shipment Track toggle — shut by default, because an order with a dozen lots would otherwise load a dozen frames — and both halves now read from one `tracking.links_for()`, so a customer and the member of staff on the phone to them cannot be shown different positions; a test asserts all seven link fields match across the two endpoints. **No migration.** **No CSP change was needed and none was made**: the portal sends no Content-Security-Policy, so nothing blocks the frame; `deploy/Caddyfile` now carries a comment saying what `frame-src` must name if one is ever added, and `X-Frame-Options DENY` — which is about the portal being framed by others — stays untouched. Proved by 38 database-free tests passing (46 in the file, 282 collected), a clean frontend build and a clean `npm run lint`, and over HTTP: the exact URL the portal builds returns 200, names the right vessel, and sends no `X-Frame-Options`. **Not proved: the map has never been opened in a browser** — Docker Desktop will not start on this PC, so the 8 end-to-end tests and the whole suite are unrun, and nothing has confirmed the frame draws, sizes or scrolls on a real screen. Not deployed | _this commit_ |
| 2026-09-15 | **Step 37 — Honest tracking** (`feature/step37-honest-tracking`, restore tag `pre-honest-tracking`). The first real order settled an argument step 36 had got wrong. Bucher's boxes go to Antwerp; WAN HAI 359, the vessel on the Bill of Lading, was showing Chennai to China, because export cargo is transshipped — the ship drops the boxes at a hub and sails on to its next voyage. So **the embedded map and the "See where the vessel is now" link are both gone**, from the customer view and the staff view, along with `tracking_url()`, `vessel_map_url()`, `TRACKING_URL_TEMPLATE`, `TRACKING_PROVIDER_NAME` and both `VESSEL_MAP_*` settings: dead plumbing in a service is worse than none, and a test in each of `test_validation.py` and `test_container_tracking.py` now asserts they stay gone. Neither was ever deployed, so no customer saw either. **The vessel name and IMO number are still stored**, because they are on the paperwork; the IMO row was dropped from the *customer* facts, as the only thing it was ever for was the link. What is left is what a buyer can act on: the status timeline, the shipment facts (shipping line, vessel, container number, B/L number, departure date, expected arrival), the copyable numbers, and **one** action — **Track this container on Evergreen Line** — which opens the carrier's own page, the one party that knows about the transshipment. The screen says the carrier's site can be slow and that its page asks for a number, with a Copy button on each. A light readability pass came with it: brand red corrected to `#BC0300` and kept strictly as a signal colour, the one action given a phone-sized tap target instead of a 3px pill, the six facts given a minimum column width so they form tidy columns rather than a ragged list, and the tracking action set in a panel of its own. No dark theme; `color-scheme: light` unchanged. **No migration.** Proved by 95 database-free tests passing (272 collected, down from 282 as the map's own tests went with it), a clean frontend build and a clean `npm run lint`. **Not proved: nothing has been opened in a browser** — Docker Desktop will not start on this PC, so the end-to-end tests and the whole suite are unrun and no screen has been looked at. Not deployed | _this commit_ |
| 2026-09-16 | **Steps 35, 36 and 37 deployed to the live server, by Alok, and the first real order loaded.** `safe-deploy.sh` ran clean, the schema is at **0012** — migration 0012's nullable `shipments.carrier` applied — and the API and website came up healthy. So container tracking, the staff Track panel and the honest order detail (carrier link and copyable numbers, no vessel map, no vessel link) are all live. The **Bucher order, EXP-043**, was then entered through the staff screens and checked from the other side: Alok signed in as that customer and saw the order. That is the first real customer data on the portal, and the first time steps 35–37 have been looked at in a browser at all — the three rows above say they never had been, because Docker Desktop would not start on this PC. The end-to-end tests are still unrun here for the same reason. `NOTIFY_ONLY_EMAILS` was last recorded as holding only the owner's address; with a real customer in the database it is worth confirming on the server before Bucher is meant to start receiving mail | (deploy, no commit) |
| 2026-09-16 | **Step 38 — A staff orders list you can scan** (`feature/step38-compact-staff-orders`, restore tag `pre-compact-orders`). The Orders & shipments screen drew every order as a fully opened card — heading, three stat tiles, every shipment with its four buttons, three card actions — stacked down one page, so five orders filled a screen and a real list would be unreadable. Each order is now **one slim row**: sales order number, customer and grade, dispatched of ordered, the status pill, and how many shipments. Clicking the row opens exactly what the card held before; nothing was removed and no button moved inside the body. **Every row is shut by default, including an order with a single shipment** — Alok's decision, 16 Sep 2026: one predictable rule reads better than a list that opens some rows and not others. Several rows can be open at once (staff compare orders), which ones are open is remembered in `sessionStorage` so a save does not shut the list, an order that was just added or edited opens itself, and **Collapse all** appears beside New order while anything is open. The row is a real `<button>` with `aria-expanded` and `aria-controls`, so it works from the keyboard and reads correctly to a screen reader, and it is 44px tall for a finger. The three right-hand columns are given fixed widths so quantities, statuses and counts line up down the page, and the **Tick last shipment** warning sits before them — in the flexible part of the row — so it cannot knock those columns out of line; it is on the *shut* row on purpose, because it is the one thing that must not hide. Brand red is used for it and nowhere else on this screen. **Frontend only: no API change, no migration, and `/api/staff/orders` already returned the shipments the shut row counts.** The customer screens were not opened, at Alok's request — a deliberate exception to the "every step covers both halves" rule, and the only one so far. Proved by a clean `npm run build` and `npm run lint` with **13 warnings before and after, none of them new**, and by headless Edge over CDP against a throwaway page that renders the real component with the real stylesheets and a made-up server answer: at 1440, 1024 and 390px the page does not scroll sideways (`scrollWidth` equals `clientWidth` at each), the columns line up, a long customer name is cut with an ellipsis instead of pushing the numbers off, the chevron turns, opened rows show the totals and both shipments, and the remembered-open path was exercised through the same `sessionStorage` key the screen reads. `--window-size` had to be abandoned for `Emulation.setDeviceMetricsOverride`: headless Edge on this PC laid out at 492–504 CSS px whatever width was asked for, which would have made every earlier phone check meaningless. **Not proved: nothing has been clicked by a person, and there is still no database on this PC** — Docker Desktop will not start, so the end-to-end tests are unrun and the screen has never been opened against the real API. The throwaway page was deleted and is not in the repository | _this commit_ |
| 2026-09-16 | **Step 38 deployed to the live server, by Alok**, later the same day: `safe-deploy.sh` ran clean, the backup it took is `2026-09-16_050439`, and the new list was seen working on the live site. No migration and no API change, so the schema stays at **0012** and only the website bundle moved. That closes the gap the step 38 row above leaves open — the screen had never been clicked by a person when it was written | (deploy, no commit) |
| 2026-09-16 | **Step 43 — Nothing sends the customer away** (`feature/remove-tracking-redirect`). On Alok's decision the customer's shipment view no longer offers **Track this container on \<carrier\>**, and the paragraph explaining that it opens the carrier's website in a new tab has gone with it. A customer reading their own order should not be handed off to somebody else's site — and the carrier's page was slow, asked for a number, and knew nothing the portal had not already told them. **Everything they can act on stays**: shipping line, vessel, container number, Bill of Lading number, departure date and expected arrival, with the container and B/L numbers now carrying a small **Copy** button each so they can be pasted wherever the customer chooses. This applies to every carrier, not only Evergreen, because the button was drawn from whatever `links_for()` returned. **The customer view now contains no external link of any kind.** Staff keep the Track panel exactly as it was: looking a box up on the carrier's site is part of answering the phone, and staff are not customers. The backend is untouched — `tracking.links_for()` still builds the URL and the customer endpoint still returns it, unused by the screen; removing it from the API would have meant changing the customer schema and the tests that assert both halves are shown the same thing, which is a bigger change than this one and not asked for. `TrackActions` is now documented as the staff component, with a small `CopyButton` exported beside it for the facts list. Proved by a clean `npm run build` and `npm run lint` (13 warnings before and after, none new) and by headless Edge over CDP against a throwaway page rendering the real customer screen with a faked order: at 900px and 390px the six facts are all present, both Copy buttons are there, no carrier link or note is drawn anywhere, and nothing scrolls sideways. **Not proved: nobody has pressed Copy in a real browser** — the clipboard needs a secure context, and the button falls back to "Select it" when it is refused. **Not deployed** | _this commit_ |
| 2026-09-16 | **Step 42 — The sample data goes, and stays gone** (`feature/remove-sample-data`). Four sample orders (`SAMPLE/SO/EXP/001–004`) and three sample customers were loaded onto the live portal for a demo and had to come off before a real customer saw them. **Part 1, where they came from:** `deploy/sample-data/sample-data.sql`, run by hand. Nothing automatic — `safe-deploy.sh` runs `scripts.migrate` and nothing else, the API lifespan starts the notification timer only, and `scripts/seed.py` is a development tool needing DEMO_* values in `.env`. So the way it could come back is a person, and both doors are now shut: the SQL file **refuses `mode=load` when the database holds a single order belonging to a customer whose code is not `SAMPLE-`** (`-v allow_beside_real_data=yes` overrides, for a demo database), and `seed.py` refuses to create demo data when it finds a customer that is neither demo nor sample, naming it. **Part 2, removing what is there:** `mode=remove` already existed and is unchanged in what it deletes — `DELETE FROM customers WHERE code LIKE 'SAMPLE-%'`, with every login, order, shipment, document, photo, notification and sign-in link following by `ON DELETE CASCADE`. It cannot reach a real row: the delete is by customer code, and a pre-existing guard refuses outright if a `SAMPLE/` order is found on a customer that is not a sample one. What is new is that it now **says what it did** — it counts the sample customers, orders, shipments and logins before deleting them and prints that beside what remains, so success reads as "4 sample orders found, removed; 1 real customer, 1 real order remaining". Running it twice is harmless: the second run finds nothing and says so. **No migration, no application code touched** — the API, the screens and the customer half are all untouched. Proved by 6 new tests: three on the seed guard (a real customer stops it; sample and demo customers do not; an empty database is fine) and three on the SQL file (it carries the refusal, the delete is reachable only through `SAMPLE-` customers and is the only `DELETE` in the file, and the run reports counts). **The removal itself can only be proved on the server** — no database here, and this file talks to the database container directly rather than through the app | _this commit_ |
| 2026-09-16 | **Step 41 — Documents announce themselves** (`feature/step41-document-notifications`, restore tag `pre-document-notifications`). Status changes have emailed customers by themselves since step 33; documents said nothing, so a Bill of Lading could sit on the portal for days with nobody told. Now the same 15-minute timer announces documents too, and staff do nothing but upload as they already do. **Alok's rules, 16 Sep 2026: the fewest emails that still keep the customer informed.** So everything newly ready on one *order* goes in **one** email — however many documents and however many shipments it spans — and a document that **replaces** one of the same kind says nothing at all, because a corrected invoice announced a second time only asks the customer which copy is right. **No migration and no new table:** the event is recorded as `Document: Bill of Lading` in the existing `notifications` table, so the unique constraint on (shipment, event, user) already promises "each type announced once per shipment per person", and `String(50)` already fits the longest name. `record_outcome()` gained an explicit `event` argument, defaulting to the shipment status as before. `NOTIFY_ON_DOCUMENTS` chooses which types speak, defaulting to all four, and a test holds that default equal to `EXPECTED_DOCUMENTS` in the staff router so a fifth kind cannot be added there and quietly stay silent. The Messages tab lists waiting documents one line each, because the question it answers is what the customer has not been told. A row with no file behind it is never announced, so nobody is sent to an empty download. Proved by 8 new tests (announced once and only once; a replacement announced never; three documents in one email; two shipments of one order still one email; a type switched off says nothing; an empty document row is not a document; the status emails unchanged; the two lists equal) — **seven of them need a database and therefore ran only in CI.** **Not deployed, and it reaches nobody until the customer is on `NOTIFY_ONLY_EMAILS`** | _this commit_ |
| 2026-09-16 | **Step 40 — The sign-in link just signs you in** (`feature/auto-redeem-signin`). On Alok's decision the Continue button is gone: the link redeems itself in a `useEffect` as the page opens, shows **"Signing you in…"**, and hands over to the portal. The button had a reason — a mail scanner opening the link would have spent it — and that reason has gone: the live server now runs `MAGIC_LINK_SINGLE_USE=false` with a 24-hour expiry, so a link survives being opened more than once, and the token has always travelled after the "#" where no browser sends it to a server. **The two screens that matter on failure are kept**: a 400 still gives "Link expired — Request a new link", and anything else (a dead gateway, no network) now gives **Try again** plus a way to ask for a new link, rather than the old dead end. Redeeming is guarded by a ref so React's development double-render cannot post twice — harmless while links are reusable, wrong the moment they are not. `takeSignInLinkToken()` already strips the token from the address bar before this screen is drawn, so a refresh shows the sign-in screen rather than redeeming again. **Frontend only: one file, no API change, no migration, and the password escape hatch on the sign-in card is untouched.** Proved by a clean `npm run build` and `npm run lint` (13 warnings before and after, none new) and by headless Edge over CDP against a throwaway page rendering the real component with the server's answer faked: the waiting state, the expired screen and the failure screen all drawn at 420px with nothing scrolling sideways. **Not proved: no real email link has been opened** — that needs the live server. **Not deployed** | _this commit_ |
| 2026-09-16 | **Step 39 — Ready for a pilot customer** (`fix/pilot-readiness`, restore tag `pre-pilot-fixes`). Three fixes the pre-pilot audit called Critical or Important, and one to CI. **Sign-in links no longer go through `NOTIFY_ONLY_EMAILS`.** `notifications.send()` takes `pilot_list=True` by default and `magic_links.send()` passes `False`, so the allow-list gates the automatic shipment notifications and nothing else; `SEND_EMAILS` still stops everything, links included, because that is the switch for the whole portal. Before this, a customer who was not on the list asked to sign in, was told "Check your email", and received nothing — the portal's worst failure, because it looked exactly like success. **The answer the browser gets is unchanged, deliberately, even when sending really fails**: an error shown only for addresses that have accounts turns the sign-in page into a way to ask which addresses those are, and the route answers before sending anyway. So the failure surfaces where staff will see it instead — `log.error` with the address, and a **"Sign-in links that did not arrive"** card on the Messages screen, fed by the last 20 failures kept in memory (forgotten on restart, and the link itself is never kept). **Documents are served as what they are**: `storage.media_type_for()` reads the stored suffix, so a mill test certificate scanned as a JPG arrives as `image/jpeg` instead of being labelled `application/pdf` and refusing to open; anything unrecognised goes out as `application/octet-stream` rather than being guessed at. **The front door sends a Content-Security-Policy and HSTS**: `default-src 'self'` with three deliberate exceptions — `img-src data: blob:` because documents and photos are fetched with the token and handed over as blob URLs, `style-src 'unsafe-inline'` because React writes style attributes, and `frame-ancestors 'none'` restating `X-Frame-Options` — plus `max-age=31536000; includeSubDomains` **without `preload`**, which is not this portal's door to close on the whole domain. CI now runs `npm run lint` as well as the build. **No migration.** Proved by 5 new database-free tests (a link reaches an address that is not on the pilot list; a notification to that same address is still suppressed; `SEND_EMAILS=false` still stops a link; a failed link is recorded without its token; and the Caddyfile carries both headers, checked on the directive rather than the file so the comment explaining `preload` does not fool it) and 2 new database-backed ones (a PDF and a JPG document download with the right content type; a failed link shows on the staff Messages endpoint). Every existing stub of `notifications.send` was updated for the new keyword. Frontend build and lint clean, 13 warnings before and after. **The two headers cannot be proved from here** — no local stack — so they are checked on the live server after deploy. **Not deployed** | _this commit_ |
| 2026-09-16 | **CI on `dev` put right: two tests had been asking for an endpoint that never existed** (`fix/staff-orders-test-url`). The `tests` workflow had been red on every push to `dev` since the step 36 merge (`34963112630`, 15 Sep); step 35 was the last green one. `gh run view --log-failed` on the step 38 run named it exactly: `272 collected, 2 failed`, both in `test_container_tracking.py` — `test_staff_and_customer_are_shown_the_same_tracking` asserting `405 == 200` on `{"detail":"Method Not Allowed"}`, and `test_neither_half_is_sent_a_vessel_link_any_more` dying on `KeyError: 'shipments'`. Both called `GET /api/staff/orders/<id>`, which **has never existed**: that path carries PUT and DELETE only, and the staff screen reads the whole list from `GET /api/staff/orders`. So it was stale tests, not a bug — the staff list already builds every shipment with `links_for()`, the same function the customer endpoint uses, which is the behaviour those two tests exist to check. Both now go through a `staff_shipment` helper that reads the list the way the screen does and **asserts the request succeeded**, so a wrong URL fails saying so instead of dying on a `KeyError`; its docstring records why that path answers 405. Tests only, no app change. Green on `dev` at run `35060264643`: **272 passed**, backend and frontend both. The bad URL entered in `7c72ed6` (step 36) and was carried through `26424b8` (step 37), which is why a heavy rewrite of that file did not clear it. **Why it went unnoticed for three steps: Docker Desktop will not start on this PC, so the ~175 database-backed tests run nowhere but CI** | _this commit_ |
| 2026-09-17 | **Steps 39, 40, 41 and 43 confirmed deployed and live, and step 42 executed** — as reported by Alok; this PC cannot see the server. The sample orders and customers were removed on the server with `mode=remove`, and the only order on the live portal is the real Bucher order, EXP-043. None of them carried a migration, so the schema stays at **0012**. Nothing merged to `dev` is waiting to go out. Deploy date and backup name not recorded. Notes only | _this commit_ |
| 2026-09-17 | **SAP read for the first time, look-only, and the import parked.** SAP Business One was read through its Service Layer with a script that refuses any request other than GET plus sign-in and sign-out, and accepts only the server's known certificate. It read the latest 50 sales orders, their customers, the custom field list, and 61 export invoices; **nothing in SAP was changed.** Found: export orders are series 416 and export invoices series 419; customers match on SAP's customer code; the shipping fields exist in SAP but were empty on every export invoice; and invoices are not linked to orders. Details in "SAP Business One — what the look-only check found". The SAP login and scripts stay on the office PC, never in this repo or on the portal server. **On the user's decision the import is not built.** No application code touched. Notes only | _this commit_ |
| 2026-09-17 | **Step 44 — Live container tracking from ShipsGo** (`feature/shipsgo-tracking`, restore tag `pre-shipsgo-tracking`, **migration 0013**). ShipsGo API v2 (`https://api.shipsgo.com/v2`, header `X-Shipsgo-User-Token`, read from the official OpenAPI spec): `POST /ocean/shipments` adds a shipment by `booking_number` and **costs 1 credit**; `GET /ocean/shipments/{id}` and the list are free. **How credits are protected:** (1) only one function, `shipsgo.add_shipment`, can POST, and `_call` refuses every other write; a test proves it is called only from `live_tracking.enable`, which is called only from the staff Enable route, which demands `confirm: true`; (2) enable locks the shipment row, and if tracking already exists it returns without contacting ShipsGo at all; (3) a second shipment on the same B/L copies the first one's ShipsGo id without asking ShipsGo; (4) otherwise it looks the B/L up in the account first (free) and reuses what it finds; (5) the POST sends no `reference`, because ShipsGo counts the reference in its duplicate check; (6) a 409 ALREADY_EXISTS is reused, which ShipsGo documents as free; (7) the id is committed the moment ShipsGo answers, and Stop tracking only removes our row, so re-enabling finds it again for nothing; (8) every answer's `X-Shipsgo-Credits-Cost` is read, and a read that ever reports a cost raises `CreditTripwire`, which stops the refresh timer. Nothing is on by default: no save, no customer page and no timer run adds anything. **Refresh:** a second loop in `scheduler.py` with its own advisory lock reads every tracked shipment that has not been read for `SHIPSGO_REFRESH_EVERY_HOURS` (default 6), pausing between reads (ShipsGo allows 100 a minute), skipping journeys ShipsGo has finished and shipments that failed 20 times. **Storage:** `shipment_tracking`, one row per shipment (unique), holding ShipsGo's id, the B/L added, status, carrier, ports, loading date, ETA, transshipment count and each container's movements as JSON. If staff change the B/L afterwards, customers stop seeing the panel and Enable refuses until tracking is stopped. **Screens:** `LiveTracking.jsx`, shared by both halves; the customer view has no link out, keeping step 43. Proved by 31 new tests in `test_live_tracking.py` against a fake ShipsGo that counts every call — **17 need no database and passed here; 14 need PostgreSQL and run only in CI** — by the migration rendering cleanly in both directions (`alembic upgrade 0012:0013 --sql`), by a clean `npm run build` and `npm run lint` (13 warnings before and after, none new), and by headless Edge over CDP rendering the real customer and staff screens with a faked order at 390, 900 and 1100px: timeline drawn, both transshipment tags and the vessel-change note present, "Tracking is updating…" shown for a shipment with no news, nothing scrolls sideways, no console errors. **Not proved: no call to the real ShipsGo has been made** — there is no key on this PC. Run `scripts.shipsgo_check` on the server first. The mock-up discussed earlier was not available in this session; the panel follows the portal's existing style. CI green on `6cc4406` (325 passed). **Merged to `dev` on Alok's OK (`374abf0`); not deployed** | `248009d`, `6cc4406` |
| 2026-09-17 | **Step 45 — No carrier redirect anywhere** (`feature/remove-carrier-redirect-box`, restore tag `pre-remove-carrier-box`). On Alok's decision, with live tracking in the portal the external "Track this container on <carrier> ↗" box is redundant and is the off-site redirect that was not wanted. It survived only in the staff Track panel — step 43 had already taken it off the customer view — so `TrackActions` and its boxed `CopyNumber` are deleted from `Tracking.jsx`, which now holds only the `CopyButton` the customer's shipment facts use, and the styles only that box used (`.track`, `.track--button`, `.track--primary`, `.trackbox`, `.trackbox-note`, `.copynums`, `.copynum-label`, `.copynum-row`, `.copynum-value`, `.copynum-hint`) are removed. The staff Track button is still always there and opens live tracking alone. **The backend is untouched:** `tracking.links_for()` still builds `container_tracking_url` and both APIs still send it, unused by any screen — removing it means changing two schemas and the step 35–37 tests, which is a bigger change than this one and was not asked for. No migration. Proved by a clean `npm run build` and `npm run lint` (13 warnings before and after, none new), and by headless Edge over CDP rendering the real customer and staff screens with a faked order whose API data still carries a carrier URL, at 390, 900 and 1100px, one shipment tracked and one not: no `<a href>` anywhere on either page, no "Track this container", "carrier's website" or shipmentlink text, the customer's four Copy buttons (B/L and container on each shipment) still there, the untracked shipment shown with its facts and no timeline, staff offered Enable tracking on it, nothing scrolling sideways, no console errors. CI green (325 passed). **Merged to `dev` on Alok's OK; not deployed** | `19cf3a4` |
| 2026-09-18 | **Step 46 — Password sign-in beside the email link** (`feature/password-login`, restore tag `pre-password-login`, **no migration**). SES refusing credentials had locked everybody out. `PASSWORD_SIGN_IN` defaults to true; `.env.example` says so. Admin Console: **Set password** on every login (customer and team) → `POST /api/staff/logins/{id}/set-password`, `StaffUser` only, refuses your own account and weak passwords, stores only the PBKDF2 hash, `must_change_password` false, stamps `password_changed_at` (signs them out everywhere, retires links already sent), activity record `login.password_set` without the password; a "Suggest one" button makes a readable 12-letter one. Server: `scripts/set_password.py --email`, prompts twice via `getpass`, refuses without a terminal, prints usage with no `--email`, warns if the login is disabled or `PASSWORD_SIGN_IN` is off. Sessions: `SESSION_TTL_DAYS` (30) replaces `TOKEN_TTL_SECONDS`; the token is kept in localStorage (an old sessionStorage one is moved across), and Sign out clears it everywhere and signs out other tabs. The token now records `pwd` when it came from a password, and `must_choose_password` applies only then, so link sign-ins are never held back by a temporary password. Two old tests that expected a link sign-in to be held back were changed to expect the opposite; 16 new tests in `test_password_login.py`. **Waiting for Alok's OK to merge; not deployed** | _this commit_ |

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
- ~~**The link page waits for a press.**~~ **Changed 16 Sep 2026 (step 40):**
  the link now signs the person in as the page opens, with no button. The
  press was there because company mail systems — Outlook's Safe Links, for
  one — open every link in an email to scan it, and a page that signed in on
  opening would have had its one use spent by the scanner. Two things make
  that impossible now: the token travels after the "#", which no browser
  sends to a server, so a scanner fetching the address never learns it (true
  all along, which is why the risk was theoretical); and the live server
  keeps links reusable for 24 hours (`MAGIC_LINK_SINGLE_USE=false`), so
  opening one twice costs nothing. **If single-use is ever switched back on,
  re-read this**: auto-redeem still works for the person, but a second open
  of the same link then lands on "Link expired".
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
- **The screen asks the server; the switch is not built into the website.**
  (Step 32.) A switch the website only learned when it was built would need
  a rebuild and a deploy in the middle of an email failure.
  `GET /api/sign-in-options` answers on every load of the sign-in screen,
  and says nothing about any account. If it cannot be reached, the screen
  stays link-only, the normal state, rather than guessing.

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
  One server setting decides who can sign in at all: `SEND_EMAILS` must stay
  true. **`NOTIFY_ONLY_EMAILS` no longer applies to sign-in links** (step 39,
  16 Sep 2026) — it gates the automatic notifications only, and anybody with
  a login gets the link they asked for. Until then it gated both, so a
  customer not on the list was told to check their email and received
  nothing. The way back in an emergency is under the `pre-magic-link-only`
  restore point.
- **The 11 Sep 2026 re-check has not been confirmed.** A fresh link was
  requested from the live server for mis@alokindia.com at 11:11 UTC (answer
  202), and nothing from enquiries@alokindia.com reached that inbox in the
  next 10 minutes. The answer is the same whether or not an address has an
  account, so the likeliest reason is that mis@alokindia.com has no login on
  the live portal, or is not on `NOTIFY_ONLY_EMAILS`, rather than sending
  having broken, but that is not proven. A second link was requested for
  **exports@alokindia.com**, which has a live staff login, at 11:46 UTC
  (answer 202). **Settled since:** email on the live server is confirmed
  working — a magic-link sign-in was used there on 15 Sep 2026 — so this
  gates nothing any more. The mis@alokindia.com silence is still unexplained
  and most likely means that address has no login, or is not on
  `NOTIFY_ONLY_EMAILS`.
- **While `PASSWORD_SIGN_IN` is on, a password is a way in for everybody.**
  That is the point during an email failure, but it also brings back
  password guessing (rate limited as before) and temporary passwords staff
  have seen. Switch it off again once email works. The sign-in screen asks
  the server each time it loads, so a page already open keeps what it
  showed until it is reloaded.
- **Most people will not know a password.** Logins made since step 31 never
  chose one, so in an email failure each person needs `--reset-password`
  first (step 2 of "If email fails").
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
- **The portal says nothing about where the vessel is, on purpose.** The
  MarineTraffic link and the embedded map were both removed on 15 Sep 2026,
  after the first real order showed why: export cargo is transshipped, so
  the named ship drops the boxes at a hub and sails on. WAN HAI 359,
  carrying an Antwerp order, read Chennai to China. A customer reading that
  would draw exactly the wrong conclusion. The vessel name and IMO number
  are still stored and still shown — they are on the Bill of Lading — but
  nothing claims to say where that hull is now. **Do not put it back**
  without solving the transshipment problem, which needs the carrier's own
  leg-by-leg data and not an AIS feed.
- **The customer is no longer sent to the carrier's website at all** (step
  43, 16 Sep 2026). They get the shipping line, vessel, container number,
  B/L number and the two dates, with a Copy button on each number, and no
  link off the portal. Staff keep the carrier link in their Track panel. The
  consequence to be honest about: **the portal now shows only what Alok has
  entered.** If a container is delayed at a transshipment hub, nothing here
  will say so until somebody at Alok Ingots updates the shipment.
- **Container tracking is one outbound link, not a paid API.** Each shipment
  can carry a shipping line, and **Track this container on <carrier>** opens
  that carrier's own page — which knows about the transshipment, because the
  carrier arranged it. The portal does not read the answer, so it cannot
  show a position or an ETA on its own screens, and nothing confirms the box
  is aboard. Real shipment-level data inside the portal needs a paid
  carrier API.
- **The carrier's site can be slow or unreachable, and that is accepted.**
  It is one link to somebody else's website. The screen says the page can be
  slow, and the B/L and container numbers sit beside the button with a Copy
  button each, so a customer whose browser cannot reach Evergreen still has
  what they need to phone or email somebody.
- **Evergreen's deep links are confirmed not to work**, and are gone. Both
  candidates were opened against the real Bill of Lading on 15 Sep 2026 and
  both landed on ShipmentLink's blank Quick Tracking form, which is what a
  POST-only form does with a GET. The button now opens that search page and
  the portal shows the B/L and container number beside it to copy. If
  Evergreen ever offers a real GET link, `CARRIER_URL_EVERGREEN_BL` in
  `.env` turns it back on with no release. Note the asymmetry: `.env` can
  add or replace a template but never remove one — an empty value is
  ignored on purpose, so a half-written line cannot delete a working link —
  so switching a carrier *back* to its search page is a code change.
- **Copying a number can fail and says so.** The Copy button needs the
  clipboard API, which wants a secure context; the numbers are always on
  screen as selectable text, and the button changes to "Select it" with an
  explanation when the browser refuses. Untested in a browser.
- **Only Evergreen Line is in the registry.** Any other carrier typed on the
  form is stored and shown, and simply gets no button. That is deliberate —
  a button labelled with a line the portal cannot link to is a dead end —
  but it means the feature does nothing at all for a shipment on Maersk,
  MSC, Hapag-Lloyd or a feeder line until an entry is added.
- **Every shipment already in the database has no carrier.** The column
  arrives empty and nothing backfills it, because a carrier guessed from a
  B/L prefix would be a guess written into real data. Until staff set it,
  those shipments show no Track container button — exactly as before.
- **`scripts/add_document.py` still works** and does the same thing as the
  staff page. Keep them in step: both store a random name and replace a
  document of the same type.
- **Document files live in `storage/`**, which is git-ignored and must be
  included in server backups — `safe-deploy.sh` will need to cover it.
- **`scripts.seed --reset` clears the database but leaves document files behind**
  in `storage/documents/`, so old files accumulate as orphans. Harmless while
  the data is invented; worth a tidy-up before real documents arrive.
- ~~**`safe-deploy.sh` has only ever run against a local Docker stack.**~~
  **No longer true:** it has run clean against srv1427359 several times, most
  recently on 16 Sep 2026, with a real domain and Caddy's real certificate.
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
- **The development database is stamped `0010` and should not be.** On
  12 Sep 2026 the local `alok_portal` database said it was at revision 0010
  — that is step 30's `0010_password_reset_links`, applied while that branch
  was checked out and never taken back when it was held unmerged. The file
  is not on `dev`, so `alembic upgrade head` there fails with "Can't locate
  revision 0010" until it is put right. Nothing was done about it, because
  it is the user's database and step 30 is the user's decision. **The live
  server is not affected** — it has never had step 30. To fix it when you
  want to: check the step 30 migration out on its own
  (`git show feature/step30-password-reset:backend/migrations/versions/0010_password_reset_links.py`),
  `alembic downgrade 0009`, then delete the file again.
- **Revision 0010 is spoken for.** `feature/step30-password-reset` owns it,
  so step 33's migration is 0011 with 0009 as its parent. If step 30 is ever
  merged, renumber its migration to 0012 with `down_revision = '0011'`
  first, or Alembic will see two heads.
- **What the automatic sender still does not do.** Since step 33 the API
  sends on a timer by itself, so nothing waits on somebody remembering a
  command. What it is not: it only looks at shipment *status*, so a
  correction to a vessel name or an ETA tells nobody; it sends to every
  active login of a customer, with no way to say "this person only"; and
  the timer lives in the API process, so while the API is down nothing is
  sent — it catches up on the next run, because what is waiting stays
  waiting.
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
- **The live server's `storage/` permissions were fixed by hand, not in the
  repo.** Document upload failed on the live portal on 16 Sep 2026 with
  "Could not upload that file"; the cause was folder permissions on the
  server and Alok fixed it there, after which the Bucher Bill of Lading
  uploaded. **Nothing in this repository makes that survive a rebuild**, so a
  fresh server or a changed volume could bring it back. Parked on Alok's
  decision, 16 Sep 2026 — worth a small step that sets the ownership in the
  image or the compose file. On the bright side this settles the audit's
  **C4**: a document has now travelled from a staff upload to the live
  portal.
- **The staff orders list has no search, filter or sorting.** Step 38 made
  every order one slim row, which is what makes a long list readable at all,
  but the list is still every order in the portal, newest last, with nothing
  to narrow it. That is fine for the handful of orders live today and will
  not be at two hundred; a filter by customer or status is the obvious next
  thing when it starts to hurt.
- **Which rows are open is remembered per browser tab, and only there.**
  `sessionStorage`, like the sign-in token: a refresh or a save keeps the
  list as it was, closing the tab forgets it, and a browser that refuses
  site data simply starts with everything shut. Nothing about it reaches the
  server or another device.
- **The staff orders list was built without a database to try it against.**
  Step 38 was proved with a headless browser against a throwaway page holding
  made-up orders, because Docker Desktop will not start on this PC. It has
  since been deployed and seen working live (16 Sep 2026), which settles the
  drawing of it; the keyboard path and the remembered-open behaviour still
  have nobody's word but the harness's.
- **The database-backed tests run nowhere but CI.** With no database on this
  PC, about 175 of the 272 tests cannot be run before a push — which is how
  two tests calling an endpoint that never existed survived three steps
  (16 Sep 2026; see the progress log). Watch the Actions tab after every
  push until Docker Desktop works again.
- **The frontend has no tests.** The 229 committed tests are all backend.
  Nothing checks that the progress track draws, that the photo gallery
  revokes its blob URLs, or that a backwards status change asks before it
  saves. `npm run build` passing only means it compiles.
- **A paid carrier API is still the only way to shipment-level tracking**
  inside the portal's own screens. Free AIS pages show a hull's position,
  which is not the cargo's — the reason vessel tracking was removed
  altogether on 15 Sep 2026.
