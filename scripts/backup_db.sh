#!/bin/bash
# Daily PostgreSQL backup for multi-ai-bot
# Cron: 0 3 * * * /root/multi-ai-bot/scripts/backup_db.sh

set -euo pipefail

BACKUP_DIR="/media/hdd/ai-bot/backups"
DB_NAME="multi_ai_bot"
DB_USER="multi_ai_bot"
DB_HOST="127.0.0.1"
DB_PORT="5432"
KEEP_DAYS=7

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

# Dump and compress
PGPASSWORD="${DB_PASSWORD:-mAb5Xk9RvN2pL7qW3tJd8}" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-owner \
    --no-privileges \
    | gzip > "$BACKUP_FILE"

SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[$(date)] Backup created: $BACKUP_FILE ($SIZE)"

# Remove backups older than KEEP_DAYS
find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime +${KEEP_DAYS} -delete
REMAINING=$(find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" | wc -l)
echo "[$(date)] Backups remaining: $REMAINING"
