#!/bin/zsh
# Nightly vault backup for Snag.
#
# Copies the SQLite vault to a timestamped backup directory and prunes
# backups older than 14 days. Designed for cron/launchd: no interaction,
# exits nonzero on failure.
#
#   deploy/backup_vault.sh                          # live defaults
#   deploy/backup_vault.sh /path/to/app.db /path/to/backup/root
#
# The copy uses sqlite3 .backup, which produces a consistent snapshot even
# while the bot holds the database open, then verifies it with quick_check.
# Only backup-* directories inside the backup root are ever pruned.
set -euo pipefail

SN_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DB_PATH="${1:-$SN_DIR/data/app.db}"
BACKUP_ROOT="${2:-$SN_DIR/data/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

if [[ ! -f "$DB_PATH" ]]; then
    echo "backup_vault: no database at $DB_PATH" >&2
    exit 1
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
DEST_DIR="$BACKUP_ROOT/backup-$STAMP"
mkdir -p "$DEST_DIR"
DEST="$DEST_DIR/app.db"

SQLITE3="$(command -v sqlite3 || echo /usr/bin/sqlite3)"
if [[ -x "$SQLITE3" ]]; then
    "$SQLITE3" "$DB_PATH" ".backup '$DEST'"
else
    cp "$DB_PATH" "$DEST"
fi

if [[ -x "$SQLITE3" ]]; then
    if ! "$SQLITE3" "$DEST" "PRAGMA quick_check;" 2>/dev/null | grep -qx "ok"; then
        echo "backup_vault: integrity check failed on $DEST" >&2
        exit 1
    fi
fi

# Prune backups older than the retention window. Only backup-* dirs are
# matched, never the root itself or anything else in it.
PRUNED="$(find "$BACKUP_ROOT" -maxdepth 1 -type d -name 'backup-*' -mtime "+$RETENTION_DAYS" -exec rm -rf {} + -print 2>/dev/null | wc -l | tr -d ' ')"

echo "backup_vault: wrote $DEST"
echo "backup_vault: kept $(find "$BACKUP_ROOT" -maxdepth 1 -type d -name 'backup-*' 2>/dev/null | wc -l | tr -d ' ') backup(s), pruned $PRUNED older than ${RETENTION_DAYS}d"
