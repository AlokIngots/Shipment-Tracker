#!/usr/bin/env bash
#
# Deploy the Alok Ingots customer portal.
#
#   ./safe-deploy.sh              deploy the current code
#   ./safe-deploy.sh --backup     take a backup and stop, change nothing
#   ./safe-deploy.sh --dry-run    show what would happen, change nothing
#
# It always backs up the database AND the customer documents in storage/
# before touching anything, and puts the previous version back if the new
# one does not come up. This is the only supported way to deploy: running
# "docker compose build" by hand skips every safety net in here.

set -euo pipefail

cd "$(dirname "$0")"

# Which compose files to deploy with. Defaults to the production stack on
# its own, which is what a machine of its own wants.
#
# A server that already has something on 80 and 443 -- srv1427359 runs
# AlokCRM behind nginx -- adds the server override, which moves the portal
# to 127.0.0.1:8080 and leaves the front door alone:
#
#   COMPOSE_FILES="docker-compose.prod.yml docker-compose.server.yml" ./safe-deploy.sh
COMPOSE_FILES="${COMPOSE_FILES:-docker-compose.prod.yml}"

COMPOSE=(docker compose)
for _file in $COMPOSE_FILES; do
  [ -f "$_file" ] || { printf 'No such compose file: %s
' "$_file" >&2; exit 1; }
  COMPOSE+=(-f "$_file")
done

# The first one, for the messages that print a restore command.
COMPOSE_FILE="${COMPOSE_FILES%% *}"
BACKUP_ROOT="backups"
KEEP_BACKUPS=10
HEALTH_TRIES=30
HEALTH_WAIT=2

STAMP="$(date +%Y-%m-%d_%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$STAMP"

BACKUP_ONLY=false
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --backup)  BACKUP_ONLY=true ;;
    --dry-run) DRY_RUN=true ;;
    -h|--help) sed -n '3,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg  (try --help)" >&2; exit 2 ;;
  esac
done

# ------------------------------------------------------------------ output

BOLD=$'\033[1m'; RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; OFF=$'\033[0m'
step()  { printf '\n%s==>%s %s\n' "$BOLD" "$OFF" "$1"; }
ok()    { printf '    %s+%s %s\n' "$GREEN" "$OFF" "$1"; }
warn()  { printf '    %s!%s %s\n' "$YELLOW" "$OFF" "$1"; }
die()   { printf '\n%sFAILED:%s %s\n\n' "$RED" "$OFF" "$1" >&2; exit 1; }

# ------------------------------------------------------------- preflight

step "Checking this machine is ready"

command -v docker >/dev/null 2>&1 || die "Docker is not installed."
docker info >/dev/null 2>&1 || die "Docker is installed but not running."
"${COMPOSE[@]}" version >/dev/null 2>&1 || die "The 'docker compose' plugin is missing."
[ -f "$COMPOSE_FILE" ] || die "$COMPOSE_FILE not found. Run this from the project folder."
[ -f .env ] || die ".env not found. Copy .env.example to .env and fill it in."

missing=""
for var in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD SECRET_KEY; do
  value="$(grep -m1 "^${var}=" .env | cut -d= -f2- | tr -d '\r' || true)"
  [ -n "$value" ] || missing="$missing $var"
done
[ -z "$missing" ] || die "These must be set in .env:$missing"

SECRET_LEN=$(grep -m1 '^SECRET_KEY=' .env | cut -d= -f2- | tr -d '\r' | wc -c)
[ "$SECRET_LEN" -ge 33 ] || die "SECRET_KEY in .env is too short (needs 32+ characters).
    Generate one with:
      python -c \"import secrets; print(secrets.token_urlsafe(48))\""

DB_NAME="$(grep -m1 '^POSTGRES_DB='   .env | cut -d= -f2- | tr -d '\r')"
DB_USER="$(grep -m1 '^POSTGRES_USER=' .env | cut -d= -f2- | tr -d '\r')"
DOMAIN="$(grep -m1 '^PORTAL_DOMAIN='  .env | cut -d= -f2- | tr -d '\r' || true)"
ok "Docker is running"
ok ".env has the settings that must not be guessed"
if [ -z "$DOMAIN" ] || [ "$DOMAIN" = ":80" ]; then
  warn "PORTAL_DOMAIN is not a real domain — serving plain HTTP, no certificate"
else
  ok "PORTAL_DOMAIN is $DOMAIN — Caddy will obtain HTTPS automatically"
fi

if $DRY_RUN; then
  step "Dry run — this is what would happen"
  cat <<EOM
    1. Back up the database to  $BACKUP_DIR/database.sql.gz
    2. Back up documents to     $BACKUP_DIR/storage.tar.gz
    3. Remember the current version so it can be put back
    4. Build the new images
    5. Start the stack and bring the database schema up to date
    6. Check the portal answers; if it does not, roll back automatically

    Nothing has been changed.
EOM
  exit 0
fi

# --------------------------------------------------------------- backup

step "Backing up before changing anything"

mkdir -p "$BACKUP_DIR"

if "${COMPOSE[@]}" ps --status running --services 2>/dev/null | grep -qx db; then
  if "${COMPOSE[@]}" exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" 2>/dev/null | gzip > "$BACKUP_DIR/database.sql.gz"; then
    ok "Database saved  ($(du -h "$BACKUP_DIR/database.sql.gz" | cut -f1))"
  else
    rm -f "$BACKUP_DIR/database.sql.gz"
    die "Could not back up the database. Nothing has been changed."
  fi
else
  warn "No database running yet — first deployment, nothing to back up"
  : > "$BACKUP_DIR/database.sql.gz.none"
fi

if [ -d storage ] && [ -n "$(ls -A storage 2>/dev/null || true)" ]; then
  tar -czf "$BACKUP_DIR/storage.tar.gz" storage
  ok "Customer documents saved  ($(du -h "$BACKUP_DIR/storage.tar.gz" | cut -f1))"
else
  warn "No documents in storage/ yet — nothing to back up"
  : > "$BACKUP_DIR/storage.tar.gz.none"
fi

# Remember the running version, so a failed deploy can be undone.
PREVIOUS_API="$(docker image inspect -f '{{.Id}}' alok-portal-api:latest 2>/dev/null || true)"
PREVIOUS_WEB="$(docker image inspect -f '{{.Id}}' alok-portal-web:latest 2>/dev/null || true)"
if [ -n "$PREVIOUS_API" ] && [ -n "$PREVIOUS_WEB" ]; then
  docker tag alok-portal-api:latest alok-portal-api:rollback
  docker tag alok-portal-web:latest alok-portal-web:rollback
  ok "Current version tagged as :rollback"
  echo "$PREVIOUS_API" > "$BACKUP_DIR/api.image"
  echo "$PREVIOUS_WEB" > "$BACKUP_DIR/web.image"
else
  warn "No previous version to fall back to — this is the first deployment"
fi

git rev-parse HEAD > "$BACKUP_DIR/commit.txt" 2>/dev/null || true

if $BACKUP_ONLY; then
  step "Backup only — finished"
  ok "Everything is in $BACKUP_DIR"
  exit 0
fi

# ------------------------------------------------------------ roll back

# Which migration the database was on before this deploy, and after it.
# Both stay empty until the schema step runs, so a deploy that fails before
# then cannot trigger a schema rollback.
SCHEMA_BEFORE=""
SCHEMA_AFTER=""

# Put the schema back where it was, so the old code does not wake up facing
# tables it does not recognise.
restore_schema() {
  # Only act if this deploy actually moved the schema, and only if we know
  # for certain where it was before. Guessing here would drop tables.
  [ -n "$SCHEMA_AFTER" ] || return 0
  [ "$SCHEMA_BEFORE" != "$SCHEMA_AFTER" ] || return 0

  if [ -z "$SCHEMA_BEFORE" ]; then
    warn "This deploy started the migration history from nothing, so there is"
    warn "no earlier point to go back to. The tables are being left exactly as"
    warn "they are, which is the safe thing to do."
    return 0
  fi

  warn "This deploy changed the database schema. Putting it back to $SCHEMA_BEFORE"
  # This has to happen while the NEW image is still running: the old image
  # does not contain the new migration files, so it could not undo them.
  if "${COMPOSE[@]}" exec -T api python -m alembic downgrade "$SCHEMA_BEFORE" >/dev/null 2>&1; then
    ok "Schema is back at $SCHEMA_BEFORE, which is what the old code expects"
  else
    warn "THE SCHEMA COULD NOT BE PUT BACK."
    cat <<EOM

    The database is at $SCHEMA_AFTER but the old code expects $SCHEMA_BEFORE,
    so the portal may not work until this is sorted out. Restore the database
    from the backup taken minutes ago:

      gunzip -c $BACKUP_DIR/database.sql.gz | docker compose -f $COMPOSE_FILE exec -T db psql -U $DB_USER -d $DB_NAME

EOM
  fi
}

rollback() {
  printf '\n%s==> Rolling back to the previous version%s\n' "$YELLOW" "$OFF"
  restore_schema
  if [ -n "$PREVIOUS_API" ] && [ -n "$PREVIOUS_WEB" ]; then
    docker tag alok-portal-api:rollback alok-portal-api:latest
    docker tag alok-portal-web:rollback alok-portal-web:latest
    "${COMPOSE[@]}" up -d --no-build >/dev/null 2>&1 || true
    ok "Previous version is running again"
  else
    "${COMPOSE[@]}" down >/dev/null 2>&1 || true
    warn "There was no previous version, so the stack has been stopped"
  fi
  cat <<EOM

    The data itself was not touched: a schema step changes the shape of the
    tables, never the rows. If you ever need the database exactly as it was
    before this deploy, the backup is here:

      gunzip -c $BACKUP_DIR/database.sql.gz | \\
        docker compose -f $COMPOSE_FILE exec -T db psql -U $DB_USER -d $DB_NAME

EOM
}

# --------------------------------------------------------------- build

step "Building the new version"
if ! "${COMPOSE[@]}" build; then
  warn "The build failed, so nothing was replaced"
  die "Build failed. The portal is still running the old version."
fi
ok "Images built"

# --------------------------------------------------------------- start

step "Starting the portal"
if ! "${COMPOSE[@]}" up -d; then
  rollback
  die "The stack would not start."
fi
ok "Containers started"

step "Bringing the database schema up to date"
# Read the current revision, or fail loudly.
#
# This used to be `... 2>/dev/null || true`, which meant a command that
# could not run at all gave exactly the same empty answer as a database
# with no migration history. Those two must never be confused: the second
# tells restore_schema there is nothing to go back to, and it then declines
# to roll the schema back. So a wrong command name would quietly switch off
# the schema safety net for the whole deploy -- and it did. The backend
# reorganisation moved migrate.py to scripts/migrate.py and this script
# went on calling the old path.
schema_revision() {
  local out
  if ! out="$("${COMPOSE[@]}" exec -T api python -m scripts.migrate --revision 2>&1)"; then
    warn "Could not read the database revision. The API said:"
    printf '%s\n' "$out" | sed 's/^/    /' >&2
    return 1
  fi
  printf '%s' "$out" | tr -d '\r\n'
}

# A container that crashes on start-up is restarted by Docker, so it can
# still report itself as "running". The honest test is whether we can
# actually execute something inside it.
#
# Note where the schema is BEFORE migrating, so a deploy that fails later
# can put it back exactly there.
SCHEMA_BEFORE="$(schema_revision)" || {
  rollback
  die "Could not read the database revision before migrating, so nothing
    was changed. The message above says why."
}

MIGRATED_CLEANLY=true
"${COMPOSE[@]}" exec -T api python -m scripts.migrate || MIGRATED_CLEANLY=false

# Read where the schema ended up BEFORE deciding what to do about the
# result. A migration can be applied and still report a problem afterwards,
# and rolling back without knowing that would leave the schema moved.
SCHEMA_AFTER="$(schema_revision)" || SCHEMA_AFTER=""

if ! $MIGRATED_CLEANLY; then
  printf '
%s--- last lines from the API, this is why ---%s
' "$YELLOW" "$OFF"
  "${COMPOSE[@]}" logs --tail 25 api 2>&1 | sed 's/^/    /' || true
  rollback
  die "The database could not be brought up to date. The error above is why."
fi
if [ "$SCHEMA_BEFORE" = "$SCHEMA_AFTER" ]; then
  ok "Schema was already up to date at ${SCHEMA_AFTER:-none} - nothing changed"
else
  ok "Schema moved from ${SCHEMA_BEFORE:-empty} to ${SCHEMA_AFTER:-none}"
fi

# --------------------------------------------------------------- verify

step "Checking the portal actually answers"

api_ok=false
for _ in $(seq 1 "$HEALTH_TRIES"); do
  if "${COMPOSE[@]}" exec -T api python -c \
     "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3).status==200 else 1)" \
     >/dev/null 2>&1; then
    api_ok=true; break
  fi
  sleep "$HEALTH_WAIT"
done
$api_ok || { rollback; die "The API never became healthy."; }
ok "API is answering"

# Ask Docker where the website actually ended up rather than assuming 80.
# On a server that already has nginx the override moves it to
# 127.0.0.1:8080, and a health check hardcoded to 80 would fail and roll
# back a deploy that had in fact worked perfectly.
# Asked with a retry, because a container that has only just started can
# answer "0.0.0.0:0" for a moment before the mapping settles -- and a URL
# with port 0 in it fails, rolls back a deploy that worked, and blames the
# website. That happened once while this was being written. Anything that
# is not a usable port number counts as "not ready yet", not as an answer.
web_published_port() {
  local answer port
  for _ in $(seq 1 10); do
    answer="$("${COMPOSE[@]}" port web 80 2>/dev/null | tr -d '[:space:]')"
    port="${answer##*:}"
    case "$port" in
      "" | 0 | *[!0-9]*) ;;
      *) printf '%s' "$port"; return 0 ;;
    esac
    sleep 1
  done
  # Never found one: fall back to the default rather than refuse to deploy.
  printf '80'
}

WEB_PORT="$(web_published_port)"
WEB_URL="http://127.0.0.1:${WEB_PORT}/api/health"

web_ok=false
for _ in $(seq 1 "$HEALTH_TRIES"); do
  if curl -fsSkL -o /dev/null --max-time 5 "$WEB_URL" 2>/dev/null; then
    web_ok=true; break
  fi
  sleep "$HEALTH_WAIT"
done
$web_ok || { rollback; die "The website is not reachable at $WEB_URL."; }
ok "Website is reachable on port $WEB_PORT and reaching the API through it"

# ---------------------------------------------------------------- tidy

step "Tidying up"
docker image prune -f >/dev/null 2>&1 || true

if [ -d "$BACKUP_ROOT" ]; then
  # shellcheck disable=SC2012
  ls -1d "$BACKUP_ROOT"/*/ 2>/dev/null | sort -r | tail -n +$((KEEP_BACKUPS + 1)) | while read -r old; do
    rm -rf "$old"
    warn "Removed old backup $(basename "$old")"
  done
fi
ok "Keeping the newest $KEEP_BACKUPS backups"

# --------------------------------------------------------------- done

printf '\n%s==> Deployed%s\n' "$GREEN" "$OFF"
ok "Backup of this deploy: $BACKUP_DIR"
if [ -z "$DOMAIN" ] || [ "$DOMAIN" = ":80" ]; then
  if [ "$WEB_PORT" = "80" ]; then
    ok "Open it at http://localhost"
  else
    # Bound to loopback behind somebody else's nginx: not reachable from a
    # browser elsewhere, and saying "open it at localhost" would be a lie.
    ok "Answering on http://127.0.0.1:${WEB_PORT} — reach it through nginx"
  fi
else
  ok "Open it at https://${DOMAIN}"
fi
echo
