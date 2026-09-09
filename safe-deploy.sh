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

COMPOSE_FILE="docker-compose.prod.yml"
COMPOSE=(docker compose -f "$COMPOSE_FILE")
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
    5. Start the stack and create any missing database tables
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

rollback() {
  printf '\n%s==> Rolling back to the previous version%s\n' "$YELLOW" "$OFF"
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

    The database was NOT restored, because nothing in this deploy changed it.
    If you ever need to put it back, the backup is here:

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

step "Making sure the database has the tables it needs"
if ! "${COMPOSE[@]}" exec -T api python seed.py --schema-only; then
  rollback
  die "Could not prepare the database."
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

web_ok=false
for _ in $(seq 1 "$HEALTH_TRIES"); do
  if curl -fsSkL -o /dev/null --max-time 5 "http://127.0.0.1/api/health" 2>/dev/null; then
    web_ok=true; break
  fi
  sleep "$HEALTH_WAIT"
done
$web_ok || { rollback; die "The website is not reachable on port 80."; }
ok "Website is reachable and reaching the API through it"

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
  ok "Open it at http://localhost"
else
  ok "Open it at https://${DOMAIN}"
fi
echo
