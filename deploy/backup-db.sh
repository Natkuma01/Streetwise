#!/usr/bin/env bash
# Nightly database backup. Run as root (the cron file does this).
# Keeps the last 14 days in /var/backups/streetwise.
set -euo pipefail

DEST=/var/backups/streetwise
KEEP_DAYS=14
FILE="$DEST/streetwise-$(date +%F).sql.gz"

mkdir -p "$DEST"
chmod 700 "$DEST"

# Write to a temporary name first, so a half-finished dump is never mistaken
# for a good backup.
trap 'rm -f "$FILE.tmp"' EXIT
runuser -u postgres -- pg_dump streetwise | gzip > "$FILE.tmp"
mv "$FILE.tmp" "$FILE"

find "$DEST" -name 'streetwise-*.sql.gz' -mtime +"$KEEP_DAYS" -delete
echo "Backup saved: $FILE"
