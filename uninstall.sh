#!/bin/bash
# Zet de automatische AI Brain-sync uit. De vault en je gesprekken blijven staan.
LABEL="com.aibrain.sync"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
echo "Automatische sync staat uit. De vault is niet aangeraakt."
echo "Wil je ook de instructies weg: haal het blok tussen AI-BRAIN:START en AI-BRAIN:END uit ~/.claude/CLAUDE.md."
