# AI Brain Toolkit

Turn your Claude conversations into a searchable Obsidian knowledge base.

Automatically syncs both **Claude.ai web conversations** and **Claude Code CLI sessions** into an Obsidian vault with topic classification, tagging, and interlinking.

## How it works

```
Claude.ai (conversations.json)  ──┐
                                   ├──▶  sync_vault.py  ──▶  Obsidian Vault
Claude Code (~/.claude/projects/) ─┘       │                   ├── Chats/
                                           │                   ├── Claude Code/
                                      config.json              ├── Topics/
                                      (your keywords)          └── Home.md
```

**What the sync does:**
- Parses conversations and creates one Obsidian note per chat
- Auto-classifies into topics based on configurable keywords
- Extracts tags and assigns importance (based on message count)
- Generates Topic pages (Map of Content) that group related chats
- Tracks sync state so it only processes new conversations
- Updates a Home.md dashboard with stats

## Setup

### 1. Export your Claude.ai conversations

Go to [claude.ai](https://claude.ai) → Settings → Export data. You'll receive a `conversations.json` file.

### 2. Configure

```bash
cp config.example.json config.json
```

Edit `config.json`:

```json
{
  "vault_dir": "~/path/to/your/obsidian/vault",
  "conversations_file": "~/path/to/conversations.json",
  "claude_code_dir": "~/.claude/projects",
  "topic_keywords": {
    "Your Topic": ["keyword1", "keyword2", "keyword3"],
    "Another Topic": ["keyword4", "keyword5"]
  }
}
```

- **vault_dir**: Where your Obsidian vault lives (or where to create it)
- **conversations_file**: Path to your exported `conversations.json`
- **claude_code_dir**: Where Claude Code stores sessions (default: `~/.claude/projects`)
- **topic_keywords**: Your own topics with keywords for auto-classification

### 3. Run

```bash
# Sync everything
python3 scripts/sync_vault.py

# Only Claude.ai web conversations
python3 scripts/sync_vault.py --web-only

# Only Claude Code sessions
python3 scripts/sync_vault.py --code-only

# Rebuild topic pages without syncing
python3 scripts/sync_vault.py --rebuild-topics

# Use a specific config file
python3 scripts/sync_vault.py --config /path/to/config.json
```

### 4. Open in Obsidian

Open the vault directory in Obsidian. You'll see:
- **Chats/** — Claude.ai web conversations
- **Claude Code/** — CLI sessions grouped by project
- **Topics/** — Auto-generated topic hubs (Map of Content)
- **Home.md** — Dashboard with stats

Use Obsidian's graph view to explore connections between conversations.

## Automate with cron

```bash
chmod +x scripts/sync_and_notify.sh

# Every 2 hours
crontab -e
0 */2 * * * /path/to/ai-brain-toolkit/scripts/sync_and_notify.sh
```

## Memory consolidation (dream agent)

`scripts/dream.md` contains a system prompt for a "memory consolidation agent". Use it with Claude Code to enrich your vault:

```bash
# In your vault directory, paste the dream.md prompt to Claude Code
# It will scan weak pages, improve tags, add links between related chats
```

## Requirements

- Python 3.8+
- No external dependencies (stdlib only)
- Obsidian (free) for viewing

## File structure

```
ai-brain-toolkit/
├── config.example.json      # Template config — copy to config.json
├── scripts/
│   ├── sync_vault.py        # Main sync engine
│   ├── sync_and_notify.sh   # Cron wrapper
│   └── dream.md             # Memory consolidation agent prompt
└── vault/
    └── .obsidian/            # Recommended Obsidian plugin config
```

## Privacy

This toolkit processes conversations **locally only**. No data is sent anywhere. Your `conversations.json` and vault content should never be committed to git — the `.gitignore` excludes them by default.

## License

MIT
