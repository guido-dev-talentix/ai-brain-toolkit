#!/bin/bash
# AI Brain installer — maakt een Obsidian-vault van al je Claude-gesprekken
# en houdt die elk uur bij.
#
# Gebruik:  bash install.sh                 (installeert in ~/AI brain)
#           bash install.sh "/ander/pad"    (eigen locatie; niet in Documenten/Bureaublad)
set -euo pipefail

PKG="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-$HOME/AI brain}"
VAULT="$TARGET/Vault"
LABEL="com.aibrain.sync"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
GLOBAL_MD="$HOME/.claude/CLAUDE.md"

say() { printf '\n\033[1m%s\033[0m\n' "$1"; }

case "$TARGET" in
  /*) ;;
  *) echo "Geef een volledig pad op, bijvoorbeeld \"$HOME/AI brain\"."; exit 1 ;;
esac

case "$TARGET" in
  "$HOME/Documents"*|"$HOME/Desktop"*|"$HOME/Downloads"*)
    echo "Kies een map buiten Documenten/Bureaublad/Downloads: macOS blokkeert daar de automatische sync."
    exit 1 ;;
esac

say "1/6 Python controleren"
PY="$(command -v python3 || true)"
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then
  echo "Python 3 ontbreekt. Draai eerst:  xcode-select --install   en start daarna dit script opnieuw."
  exit 1
fi
echo "OK: $("$PY" --version) ($PY)"

say "2/6 Mappen en scripts neerzetten in: $TARGET"
mkdir -p "$TARGET/scripts" "$VAULT/Claude Code" "$VAULT/Transcripten" "$VAULT/Chats" "$VAULT/Topics"
cp "$PKG/scripts/sync_vault.py" "$PKG/scripts/sync_and_notify.sh" "$TARGET/scripts/"
chmod +x "$TARGET/scripts/sync_and_notify.sh"
cp "$PKG/uninstall.sh" "$TARGET/uninstall.sh"
[ -f "$TARGET/scripts/config.json" ] || cp "$PKG/templates/config.json" "$TARGET/scripts/config.json"
[ -f "$VAULT/Home.md" ] || cp "$PKG/templates/Home.md" "$VAULT/Home.md"
[ -f "$TARGET/CLAUDE.md" ] || cp "$PKG/templates/project-claude-md.md" "$TARGET/CLAUDE.md"
echo "OK"

say "3/6 Instructies toevoegen aan ~/.claude/CLAUDE.md"
mkdir -p "$HOME/.claude"
touch "$GLOBAL_MD"
if grep -q "AI-BRAIN:START" "$GLOBAL_MD"; then
  echo "Staat er al in, overgeslagen."
else
  cp "$GLOBAL_MD" "$GLOBAL_MD.backup-$(date +%Y%m%d%H%M%S)"
  TARGET="$TARGET" VAULT="$VAULT" "$PY" - "$PKG/templates/global-claude-md.md" "$GLOBAL_MD" <<'EOF'
import os, sys
snippet = open(sys.argv[1]).read().replace("{{TARGET}}", os.environ["TARGET"]).replace("{{VAULT}}", os.environ["VAULT"])
with open(sys.argv[2], "a") as f:
    f.write(snippet)
EOF
  echo "OK (backup van het oude bestand staat ernaast)"
fi

say "4/6 Eerste sync (kan even duren bij veel sessies)"
PYTHON="$PY" bash "$TARGET/scripts/sync_and_notify.sh"
tail -4 "$TARGET/scripts/.sync.log" | head -2

say "5/6 Elk uur automatisch syncen (launchd)"
if [ "${AI_BRAIN_SKIP_LAUNCHD:-}" = "1" ]; then echo "Overgeslagen (testmodus)"; else
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$TARGET/scripts/sync_and_notify.sh</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHON</key>
        <string>$PY</string>
    </dict>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$TARGET/scripts/.sync_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$TARGET/scripts/.sync_stderr.log</string>
</dict>
</plist>
EOF
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || { sleep 2; launchctl bootstrap "gui/$(id -u)" "$PLIST"; }
echo "OK"
fi

say "6/6 Klaar"
cat <<EOF
Je AI Brain staat in: $TARGET

Nog twee dingen:
  1. Obsidian (gratis, obsidian.md) → "Open folder as vault" → kies: $VAULT
  2. Open in de Claude-app een Claude Code-sessie in de map "$TARGET"
     en typ:  start onboarding
     Claude stelt je een paar vragen en richt alles op jou in.
EOF
