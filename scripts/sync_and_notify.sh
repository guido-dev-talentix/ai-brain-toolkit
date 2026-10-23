#!/bin/bash
# AI Brain Vault Auto-Sync — draait elk uur via launchd

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$SCRIPT_DIR/.sync.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') - Sync gestart" >> "$LOG_FILE"
"${PYTHON:-python3}" "$SCRIPT_DIR/sync_vault.py" >> "$LOG_FILE" 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') - Sync afgerond" >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"

# Houd log beperkt tot laatste 500 regels
tail -500 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
