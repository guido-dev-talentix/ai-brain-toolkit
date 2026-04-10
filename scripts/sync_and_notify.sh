#!/bin/bash
# AI Brain Vault Auto-Sync
# Run periodically to sync new Claude.ai and Claude Code conversations.
#
# Cron example (every 2 hours):
#   0 */2 * * * /path/to/scripts/sync_and_notify.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$SCRIPT_DIR/.sync.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') - Sync started" >> "$LOG_FILE"
python3 "$SCRIPT_DIR/sync_vault.py" >> "$LOG_FILE" 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') - Sync finished" >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"

# Keep log limited to last 500 lines
tail -500 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
