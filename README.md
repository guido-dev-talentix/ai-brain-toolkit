# AI Brain

*Turns your Claude Code sessions into a searchable Obsidian vault that updates every hour. Documentation is in Dutch.*

Claude onthoudt na een gesprek niks. Met dit pakket wel: alles wat je in Claude Code bespreekt, komt elk uur vanzelf in een map op je Mac terecht. Als je later vraagt "weet je nog hoe we dat deden?", zoekt Claude het daar op.

## Wat je nodig hebt

- Een Mac met Claude Code (de Claude-app of de terminal)
- Python 3 (zit op elke Mac met de Xcode-tools; anders eerst `xcode-select --install`)
- Obsidian (gratis, obsidian.md), om je gesprekken als netwerk te bekijken. Niet verplicht.

## Installeren (5 minuten)

```bash
git clone https://github.com/guido-dev-talentix/ai-brain-toolkit.git
cd ai-brain-toolkit
bash install.sh
```

Of open een Claude Code-sessie in de gekloonde map en typ: *Installeer dit AI Brain-pakket met install.sh*.

Daarna:

1. Open in Obsidian de map `~/AI brain/Vault` ("Open folder as vault").
2. Start een Claude Code-sessie in de map `~/AI brain` en typ `start onboarding`. Claude stelt je een paar vragen en deelt je gesprekken in onderwerpen in die bij jou passen.

## Wat er gebeurt

- Er komt een map `~/AI brain` met daarin je vault en het sync-script. De gekloonde map heb je daarna alleen nog nodig om bij te werken.
- Elk uur wordt elke Claude Code-sessie opgeslagen: een korte notitie (`Claude Code/`) plus de volledige tekst (`Transcripten/`). Sessies die doorlopen worden bijgewerkt. De transcripten blijven staan, ook als Claude Code zijn eigen logs na 30 dagen wist.
- Claude krijgt in `~/.claude/CLAUDE.md` de instructie om daar te zoeken als je naar een eerder gesprek verwijst. Het installatiescript voegt dat blok toe en maakt eerst een backup; de rest van je CLAUDE.md blijft staan. Staat het blok er al (tussen `AI-BRAIN:START` en `AI-BRAIN:END`), dan slaat het die stap over.

## Goed om te weten

- Alles blijft op je eigen Mac. Er gaat niets naar een server.
- Cloud-sessies (die niet op je Mac draaien) komen er niet in.
- Gesprekken uit claude.ai (de gewone chat) kun je toevoegen via een data-export: claude.ai → Settings → Privacy → Export data, en zet `conversations.json` uit de zip in `~/AI brain`. De volgende sync neemt ze mee.
- Sync met de hand draaien: `bash ~/AI\ brain/scripts/sync_and_notify.sh` (log in `scripts/.sync.log`).
- Stoppen kan met `bash ~/AI\ brain/uninstall.sh`. Je gesprekken blijven dan bewaard.
- Andere locatie: `bash install.sh "/ander/pad"`. Niet in Documenten, Bureaublad of Downloads: daar blokkeert macOS de automatische sync.

## Bijwerken

```bash
cd ai-brain-toolkit && git pull && bash install.sh
```

Je vault en je instellingen (`scripts/config.json`) blijven staan. De scripts en `uninstall.sh` worden vervangen en de uurlijkse sync wordt opnieuw aangemeld. Het AI Brain-blok in je CLAUDE.md wordt niet bijgewerkt: wil je de nieuwste tekst, haal het blok dan eerst weg en draai `install.sh` opnieuw.
