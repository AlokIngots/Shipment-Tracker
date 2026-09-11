# Backend — code map

The API for the Alok Ingots customer portal. FastAPI, SQLAlchemy, PostgreSQL.

**Where things go.** One line per folder. If you are adding a file and it
does not obviously belong to one of these, it probably needs a new folder
and a new line here.

```
backend/
  main.py            builds the app and includes the routers. Nothing else.
  Dockerfile         how the API is packaged
  requirements.txt   pinned dependencies for the running API
  alembic.ini        migration settings
  migrations/        the migration files themselves

  app/
    core/            things the whole app needs
      config.py      every setting read from .env, in one place
      database.py    the engine, the session, the Base for models
      security.py    password hashing and sign-in tokens
      deps.py        who is asking, and may they

    models/          the database tables, one file per thing
      customer.py    Customer, User
      order.py       Order, Shipment
      document.py    Document
      photo.py       Photo
      notification.py  Notification
      audit.py       AuditEvent — the activity record, append-only

    schemas/         the shapes that cross the wire
      auth.py        signing in, and saying who you are
      orders.py      what a customer is sent
      admin.py       what the admin console is sent, and submits back

    routers/         the endpoints, grouped by feature
      auth.py        sign in, /api/me, change your own password
      orders.py      a customer reading their own orders      (read-only)
      documents.py   a customer downloading their documents   (read-only)
      photos.py      a customer viewing their material photos (read-only)
      admin/         everything that writes. Staff only.
        accounts.py  customers and their logins (never staff logins)
        orders.py    create and edit orders; the checking rules
        shipments.py create and edit part-shipments
        documents.py attach and remove shipping documents
        photos.py    add and remove material photos
        activity.py  read the activity record (there is no route that edits it)

    services/        the working logic, with no HTTP in it
      storage.py     where document files live on disk
      tracking.py    IMO and container validation, the tracking link
      statuses.py    the lifecycle sequence and what may move where
      notifications.py  who is owed a message, and sending it
      accounts.py    customers, logins, temporary passwords
      ratelimit.py   slowing down bulk password guessing
      audit.py       recording who changed what; everything that writes calls it
      photos.py      proving an upload is a picture; making its small preview

  scripts/           one-off tools, run by hand on the server
    migrate.py       bring the database schema up to date
    manage_users.py  customers, logins, passwords
    import_data.py   load orders and shipments from CSV
    add_document.py  attach a document from the command line
    make_thumbnails.py  previews for photos uploaded before previews existed
    notify.py        send the notifications that are owed
    seed.py          demo data (never on a real server)
```

## The two halves

The portal is an **admin console** and a **customer portal**, and the split
is in the routing, not only in the screens:

- `app/routers/orders.py`, `app/routers/documents.py` and
  `app/routers/photos.py` are the customer half. Between them they have **no POST, PUT or DELETE**. A customer can
  read their own orders and download their own documents, and that is all.
- Everything under `app/routers/admin/` writes, and every route in it
  depends on `StaffUser`. That dependency is the enforcement — not the UI.

The one exception is `POST /api/change-password`, which a customer must be
able to call, because it changes nothing but their own password.

## Running the tests

```bash
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m pytest
```

The dev database must be up (`docker compose up -d` at the project root).
The suite builds its **own** database beside it, named after the development
one with `_test` on the end, creates the schema by running the real Alembic
migrations, and drops it at the end. It never touches the development data:
each test runs inside a transaction that is rolled back, so the row counts
are the same before and after.

Because the schema is built by the migrations, a migration that does not
apply fails the suite before a single assertion runs.

Tests also run on GitHub for every push and pull request — see
`.github/workflows/tests.yml`.

## Running it

From `backend/`, with the dev database up (`docker compose up -d` at the
project root):

```bash
.venv/Scripts/python.exe -m scripts.migrate            # build/update tables
.venv/Scripts/python.exe -m uvicorn main:app --port 8000
```

Scripts run as modules, so that `app.*` imports resolve:

```bash
.venv/Scripts/python.exe -m scripts.manage_users --list
.venv/Scripts/python.exe -m scripts.notify --dry-run
```

On the server, the same, inside the API container:

```bash
docker compose -f docker-compose.prod.yml exec api python -m scripts.manage_users --list
```

## Two things worth knowing

**Settings are read once, in `app/core/config.py`.** No other module calls
`os.getenv` for configuration. Before, four modules each worked out the
project root with `Path(__file__).parent.parent` and each loaded `.env`
again — which meant moving any one of them one folder deeper silently
changed where it looked. Now the paths come from config.py's own known
position, and a missing `DATABASE_URL` or a short `SECRET_KEY` refuses to
start rather than defaulting to something.

**`notifier.py` and `notify.py` were not duplicates**, despite the names.
One was the library, one the command that drove it. They are now
`app/services/notifications.py` (deciding who is owed a message, building
it, sending it, recording what happened) and `scripts/notify.py` (reading
the arguments and printing the result). The two pieces of real logic that
were stranded in the script — `pending()` and `record_outcome()` — moved
into the service, so a scheduled job or an endpoint can send notifications
without importing a command-line script.
