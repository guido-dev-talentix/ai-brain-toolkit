
<!-- AI-BRAIN:START -->
## Over mij

<!-- ONBOARDING: nog invullen. Open Claude Code in de map "{{TARGET}}" en zeg "start onboarding". -->

## Communicatie

<!-- ONBOARDING: nog invullen (taal, toon, lengte van antwoorden). -->

## AI Brain — mijn gespreksgeheugen

Er is een vault met al mijn eerdere Claude-gesprekken: `{{VAULT}}`

- `Claude Code/` — één notitie per sessie (eerste vraag, verloop, laatste antwoord)
- `Transcripten/` — volledige tekst van elke sessie; blijft staan, ook als Claude Code zijn eigen logs na 30 dagen wist
- `Chats/` — claude.ai-gesprekken (uit een data-export)
- `Topics/` — overzicht per onderwerp

### Wanneer raadplegen
- Als ik verwijs naar een eerder gesprek, besluit of afspraak ("weet je nog…", "hoe deden we dat ook alweer?")
- Als ik vraag "hebben we het hier al over gehad?"
- Als context uit eerdere sessies nodig is om goed te antwoorden

### Hoe zoeken
```bash
# Notities en transcripten (bestandsnamen)
grep -ril "zoekterm" "{{VAULT}}" --include="*.md"
# Met context
grep -ri -B2 -A5 "zoekterm" "{{VAULT}}/Transcripten"
```
<!-- AI-BRAIN:END -->
