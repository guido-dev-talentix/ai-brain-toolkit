# AI Brain — instructies voor Claude

Deze map is het AI Brain van de gebruiker: een Obsidian-vault (`Vault/`) die elk uur automatisch wordt bijgewerkt met al haar/zijn Claude-gesprekken (`scripts/sync_vault.py`, via launchd `com.aibrain.sync`).

## Onboarding

Doe dit wanneer de gebruiker "start onboarding" zegt, óf wanneer `scripts/config.json` nog `"user_name": ""` heeft of `~/.claude/CLAUDE.md` nog `ONBOARDING:`-regels bevat.

1. Interview kort en vriendelijk, één of twee vragen per keer, in de taal van de gebruiker:
   - Naam, en hoe Claude haar/hem moet aanspreken
   - Werk of studie: wat doe je, waar, met wie werk je veel samen
   - Waar gebruik je Claude vooral voor? Lopende projecten?
   - Hobby's, sport, dingen die vaak terugkomen
   - Hoe wil je dat Claude communiceert (taal, kort of uitgebreid, toon, wat je irriteert)
2. Vul in `~/.claude/CLAUDE.md` de secties **Over mij** en **Communicatie** in (vervang de `ONBOARDING:`-regels). Kort en feitelijk, geen opsmuk. Laat de rest van dat bestand ongemoeid.
3. Pas `scripts/config.json` aan: zet `user_name`, en maak 5–9 topics die bij deze persoon passen, met per topic een korte beschrijving en 6–15 kleine-letter-keywords (namen van projecten, collega's, hobby's werken goed). Haal generieke topics weg die niet passen.
4. Draai `python3 scripts/sync_vault.py --rebuild-topics` en laat zien hoeveel gesprekken per topic zijn ingedeeld.
5. Vertel daarna in 3 zinnen hoe het werkt en hoe ze claude.ai-chats kan toevoegen (zie hieronder).

## claude.ai-gesprekken toevoegen (optioneel)

claude.ai → Settings → Privacy → **Export data**. Je krijgt een mail met een zip. Zet `conversations.json` uit die zip in deze map (naast `scripts/`). De volgende sync neemt ze mee. Herhaal dit af en toe.

## Handig om te weten

- Sync handmatig draaien: `bash scripts/sync_and_notify.sh` — log in `scripts/.sync.log`
- Alleen sessies die lokaal draaien worden gesynct (desktop-app en terminal), geen cloud-sessies
- Stoppen: `bash uninstall.sh` (laat de vault staan)
