#!/usr/bin/env python3
"""
Obsidian Vault Sync — Houdt je AI Brain vault up-to-date met:
1. Claude.ai web conversations (conversations.json)
2. Claude Code sessies (~/.claude/projects/), ook die uit de desktop-app

Per Claude Code sessie komt er een notitie in "Claude Code/" en een volledig
tekst-transcript in "Transcripten/". Sessies die doorlopen worden bij elke sync
opnieuw geschreven naar dezelfde notitie. Claude Code ruimt zijn eigen
sessiebestanden na 30 dagen op; het transcript in de vault blijft staan.

Instellingen (naam, vault-map, topics) staan in config.json naast dit script.

Gebruik:
  python3 sync_vault.py                    # Sync alles
  python3 sync_vault.py --web-only         # Alleen Claude.ai web
  python3 sync_vault.py --code-only        # Alleen Claude Code
  python3 sync_vault.py --rebuild-topics   # Herbouw topic pages
"""

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ===== CONFIG =====
SCRIPT_DIR = Path(__file__).resolve().parent
BASE = SCRIPT_DIR.parent
CONFIG = json.loads((SCRIPT_DIR / "config.json").read_text())

USER_NAME = CONFIG.get("user_name") or "Ik"
BASE_DIR = BASE / CONFIG.get("vault_dir", "AI brain")
CONVERSATIONS_FILE = BASE / CONFIG.get("conversations_file", "conversations.json")
CLAUDE_CODE_DIR = Path.home() / ".claude" / "projects"
DESKTOP_SESSIONS_DIR = Path.home() / "Library" / "Application Support" / "Claude" / "claude-code-sessions"
CHATS_DIR = BASE_DIR / "Chats"
CODE_CHATS_DIR = BASE_DIR / "Claude Code"
TRANSCRIPTS_DIR = BASE_DIR / "Transcripten"
TOPICS_DIR = BASE_DIR / "Topics"
STATE_FILE = SCRIPT_DIR / ".sync_state.json"

TOPIC_KEYWORDS = {t: v.get("keywords", []) for t, v in CONFIG.get("topics", {}).items()}
TOPIC_DESCRIPTIONS = {t: v.get("description", "") for t, v in CONFIG.get("topics", {}).items()}
DEFAULT_CODE_TOPIC = CONFIG.get("default_code_topic", "Overig")

SYSTEM_PREFIXES = ("<local-command", "<command-", "<task-notification", "[Request interrupted")
SYSTEM_BLOCK_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)

# ===== HELPERS =====

def load_state():
    """Load sync state (tracks which conversations are already synced)."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"synced_web": [], "synced_code": [], "code_meta": {}, "last_sync": None}

def save_state(state):
    """Save sync state."""
    state["last_sync"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    with open(tmp, 'w') as f:
        json.dump(state, f, indent=2)
    tmp.replace(STATE_FILE)

def safe_filename(name, fallback="Naamloos"):
    """Convert a name to a safe filename for Obsidian."""
    if not name or not name.strip():
        return fallback
    safe = name.replace('/', '-').replace('\\', '-').replace(':', ' -')
    safe = safe.replace('"', "'").replace('|', '-').replace('?', '')
    safe = safe.replace('*', '').replace('<', '').replace('>', '')
    safe = safe.replace('[', '(').replace(']', ')').replace('#', '').replace('^', '')
    safe = safe.rstrip('. ').strip()
    return safe if safe else fallback

def classify_topics(text):
    """Classify text into topics based on keyword matching."""
    text_lower = text.lower()
    scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[topic] = score
    # Return top 3 topics
    return [t for t, _ in sorted(scores.items(), key=lambda x: -x[1])[:3]]

def extract_tags(text, max_tags=8):
    """Extract tags from text based on keyword frequency."""
    text_lower = text.lower()
    tags = []
    for keywords in TOPIC_KEYWORDS.values():
        for kw in keywords:
            tag = kw.replace(' ', '-')
            if kw in text_lower and tag not in tags:
                tags.append(tag)
    return tags[:max_tags]

def fmt_date(ts, fmt="%Y-%m-%d"):
    if not ts:
        return ""
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone().strftime(fmt)
    except ValueError:
        return ""

def generate_chat_page(name, uuid, date, summary, takeaways, tags, topics,
                        related_names, importance, source="web", claude_url=None):
    """Generate an Obsidian markdown page for a claude.ai chat."""
    if not claude_url and uuid:
        claude_url = f"https://claude.ai/chat/{uuid}"

    fm_tags = ', '.join(f'"{t}"' for t in tags)
    fm_topics = ', '.join(f'"{t}"' for t in topics)
    importance_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(importance, "🟡")

    topic_links = '\n'.join(f"- [[{t}]]" for t in topics)
    related_links = '\n'.join(f"- [[{r}]]" for r in related_names) if related_names else "_Geen gerelateerde chats gevonden._"
    takeaway_bullets = '\n'.join(f"- {t}" for t in takeaways) if takeaways else "- Auto-gesynct, nog niet verrijkt met AI-analyse"

    source_label = "Claude.ai" if source == "web" else "Claude Code"
    open_link = f"> [Open in Claude]({claude_url})" if claude_url else f"> Bron: {source_label}"

    return f"""---
tags: [{fm_tags}]
date: {date}
type: chat
source: {source}
importance: {importance}
claude_url: "{claude_url or ''}"
topics: [{fm_topics}]
---

# {name}

{importance_icon} **Belang:** {importance} | **Datum:** {date} | **Bron:** {source_label}

{open_link}

## Samenvatting

{summary}

## Key Takeaways

{takeaway_bullets}

## Onderwerpen

{topic_links}

## Gerelateerde Chats

{related_links}
"""


# ===== CLAUDE.AI WEB SYNC =====

def sync_web_conversations(state):
    """Sync new conversations from conversations.json."""
    if not CONVERSATIONS_FILE.exists():
        print("  conversations.json niet gevonden, sla over.")
        return 0

    with open(CONVERSATIONS_FILE) as f:
        conversations = json.load(f)

    synced_uuids = set(state.get("synced_web", []))
    new_count = 0

    for conv in conversations:
        uuid = conv.get("uuid", "")
        if uuid in synced_uuids:
            continue

        name = conv.get("name", "") or ""
        summary = conv.get("summary", "") or "Geen samenvatting beschikbaar."
        date = (conv.get("created_at", "") or "")[:10]
        messages = conv.get("chat_messages", [])

        # Skip empty conversations
        if not messages and not name:
            synced_uuids.add(uuid)
            continue

        # Collect all text for analysis
        all_text = f"{name} {summary} "
        for msg in messages:
            text = msg.get("text", "")
            if text:
                all_text += text + " "

        # Classify
        topics = classify_topics(all_text)
        tags = extract_tags(all_text)
        msg_count = len(messages)
        importance = "high" if msg_count >= 10 else ("medium" if msg_count >= 4 else "low")

        # Generate basic takeaways from summary
        takeaways = []
        if summary and len(summary) > 50:
            sentences = summary.replace("**", "").split(". ")
            takeaways = [s.strip() + "." for s in sentences[1:4] if len(s.strip()) > 20]

        safe_name = safe_filename(name, f"Chat {uuid[:8]}")

        # Check for duplicate filenames
        filepath = CHATS_DIR / f"{safe_name}.md"
        if filepath.exists():
            safe_name = f"{safe_name} ({date})"
            filepath = CHATS_DIR / f"{safe_name}.md"

        content = generate_chat_page(
            name=name or "Naamloos gesprek",
            uuid=uuid,
            date=date,
            summary=summary,
            takeaways=takeaways,
            tags=tags,
            topics=topics if topics else ["Overig"],
            related_names=[],  # Will be enriched later
            importance=importance,
            source="web"
        )

        CHATS_DIR.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(content)

        synced_uuids.add(uuid)
        new_count += 1
        print(f"  + {safe_name}")

    state["synced_web"] = list(synced_uuids)
    return new_count


# ===== CLAUDE CODE SYNC =====

def user_text(obj):
    """Return the human-typed text of a user line, or '' for tool results and system messages."""
    if obj.get("isMeta"):
        return ""
    content = obj.get("message", {}).get("content", "")
    if isinstance(content, list):
        parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        has_image = any(isinstance(c, dict) and c.get("type") == "image" for c in content)
        text = "\n".join(parts)
        if has_image:
            text = (text + "\n[afbeelding]").strip()
    else:
        text = content or ""
    text = SYSTEM_BLOCK_RE.sub("", text).strip()
    if not text or text.startswith(SYSTEM_PREFIXES):
        return ""
    return text

def parse_claude_code_session(jsonl_path):
    """Parse a Claude Code JSONL session file into a list of turns plus metadata."""
    turns = []  # (role, timestamp, text)
    first_timestamp = last_timestamp = None
    git_branch = cwd = None
    legacy_first_prompt = ""

    with open(jsonl_path) as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            timestamp = obj.get("timestamp", "")
            if timestamp:
                first_timestamp = first_timestamp or timestamp
                last_timestamp = timestamp
            git_branch = git_branch or obj.get("gitBranch", "")
            cwd = cwd or obj.get("cwd", "")

            msg_type = obj.get("type", "")
            if msg_type == "user":
                content = obj.get("message", {}).get("content", "")
                # Zelfde regel als de oude sync, om bestaande notities terug te vinden
                if not legacy_first_prompt and isinstance(content, str) \
                        and not content.startswith(("<local-command", "<command-")) \
                        and len(content.strip()) > 5:
                    legacy_first_prompt = content.strip()[:500]
                text = user_text(obj)
                if len(text) > 5:
                    turns.append(("user", timestamp, text))

            elif msg_type == "assistant":
                content = obj.get("message", {}).get("content", "")
                if isinstance(content, list):
                    text = "\n\n".join(c.get("text", "").strip() for c in content
                                       if isinstance(c, dict) and c.get("type") == "text" and c.get("text", "").strip())
                else:
                    text = (content or "").strip()
                if text:
                    turns.append(("assistant", timestamp, text))

    return {
        "turns": turns,
        "user_messages": [t for r, _, t in turns if r == "user"],
        "assistant_texts": [t for r, _, t in turns if r == "assistant"],
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "git_branch": git_branch,
        "cwd": cwd,
        "legacy_first_prompt": legacy_first_prompt,
    }

def get_project_name(encoded_path):
    """Convert encoded project path to readable name."""
    # -Users-naam-Projects-Mijn-project -> Mijn project
    parts = encoded_path.split('-')
    try:
        idx = parts.index('Projects')
        name = ' '.join(parts[idx+1:])
    except ValueError:
        name = ' '.join(parts[-2:]) if len(parts) >= 2 else encoded_path
    return name.strip() or encoded_path

def load_desktop_titles():
    """Session titles the desktop app gives its sessions, keyed by Claude Code session id."""
    titles = {}
    if not DESKTOP_SESSIONS_DIR.exists():
        return titles
    for meta_file in DESKTOP_SESSIONS_DIR.rglob("*.json"):
        try:
            meta = json.loads(meta_file.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("cliSessionId") and meta.get("title"):
            titles[meta["cliSessionId"]] = meta["title"]
    return titles

def legacy_safe_filename(name):
    """Filename rules of the older script, needed to find its notes back."""
    safe = name.replace('/', '-').replace('\\', '-').replace(':', ' -')
    safe = safe.replace('"', "'").replace('|', '-').replace('?', '')
    safe = safe.replace('*', '').replace('<', '').replace('>', '')
    return safe.rstrip('. ').strip()

def legacy_note_name(project_name, session, taken):
    """Find the note an older version of this script wrote for this session."""
    first_prompt = session["legacy_first_prompt"]
    if not first_prompt:
        return None
    title_text = first_prompt[:80].replace('\n', ' ').strip()
    if len(first_prompt) > 80:
        title_text += "..."
    base = legacy_safe_filename(f"CC - {project_name} - {title_text}")[:120]
    date = (session["first_timestamp"] or "")[:10]
    marker = f"**Eerste vraag:** {first_prompt[:200]}"
    for candidate in (base, f"{base} ({date})"):
        path = CODE_CHATS_DIR / f"{candidate}.md"
        if candidate not in taken and path.exists() and marker in path.read_text():
            return candidate
    return None

def new_note_name(project_name, first_prompt, date, taken):
    title_text = first_prompt[:80].replace('\n', ' ').strip()
    if len(first_prompt) > 80:
        title_text += "..."
    base = safe_filename(f"CC - {project_name} - {title_text}")[:120]
    name = base
    if (CODE_CHATS_DIR / f"{name}.md").exists() or name in taken:
        name = f"{base} ({date})"
    n = 2
    while (CODE_CHATS_DIR / f"{name}.md").exists() or name in taken:
        name = f"{base} ({date} {n})"
        n += 1
    return name

def quote(text, limit=None):
    text = text if limit is None or len(text) <= limit else text[:limit].rstrip() + "…"
    return '\n'.join(f"> {line}" if line else ">" for line in text.split('\n'))

def generate_code_page(note_name, project_name, session, title, topics, tags, importance, session_id):
    users = session["user_messages"]
    first_prompt = users[0]
    start = fmt_date(session["first_timestamp"])
    end = fmt_date(session["last_timestamp"])
    end_full = fmt_date(session["last_timestamp"], "%Y-%m-%d %H:%M")

    summary_parts = [f"**Eerste vraag:** {first_prompt[:200]}"]
    if title:
        summary_parts.append(f"**Titel (app):** {title}")
    if session["git_branch"]:
        summary_parts.append(f"**Git branch:** `{session['git_branch']}`")
    period = start if start == end else f"{start} t/m {end}"
    summary_parts.append(f"**Project:** {project_name} | **Periode:** {period} | "
                         f"**Berichten:** {len(users)} van {USER_NAME}, {len(session['assistant_texts'])} van Claude")

    # Verloop: eerste en laatste vragen, zodat ook lange sessies te overzien zijn
    shown = users if len(users) <= 12 else users[:6] + [None] + users[-6:]
    verloop = []
    for msg in shown:
        if msg is None:
            verloop.append(f"- _… {len(users) - 12} berichten overgeslagen, zie transcript …_")
        else:
            verloop.append("- " + msg[:200].replace('\n', ' ') + ("…" if len(msg) > 200 else ""))

    last_answer = session["assistant_texts"][-1] if session["assistant_texts"] else ""
    fm_tags = ', '.join(f'"{t}"' for t in tags)
    fm_topics = ', '.join(f'"{t}"' for t in topics)
    importance_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(importance, "🟡")
    topic_links = '\n'.join(f"- [[{t}]]" for t in topics)

    return f"""---
tags: [{fm_tags}]
date: {start}
last_active: "{end_full}"
type: chat
source: claude-code
importance: {importance}
claude_url: ""
session_id: {session_id}
project: "{project_name}"
topics: [{fm_topics}]
---

# CC - {project_name} - {title or first_prompt[:80].replace(chr(10), ' ')}

{importance_icon} **Belang:** {importance} | **Datum:** {period} | **Bron:** Claude Code

> Volledig gesprek: [[Transcripten/{note_name} (transcript)|transcript]]

## Samenvatting

{(chr(10) * 2).join(summary_parts)}

## Verloop

{chr(10).join(verloop)}

## Laatste antwoord van Claude

{quote(last_answer, 1500) if last_answer else '_Geen._'}

## Onderwerpen

{topic_links}
"""

def generate_transcript(note_name, project_name, session, title, session_id):
    lines = [
        "---",
        "type: transcript",
        "source: claude-code",
        f"session_id: {session_id}",
        f'project: "{project_name}"',
        f"date: {fmt_date(session['first_timestamp'])}",
        f'last_active: "{fmt_date(session["last_timestamp"], "%Y-%m-%d %H:%M")}"',
        "---",
        "",
        f"# Transcript — {title or note_name}",
        "",
        f"Notitie: [[{note_name}]] | Map: `{session['cwd'] or ''}`",
        "",
        "_Alleen tekst; tool-aanroepen en -resultaten zijn weggelaten._",
        "",
    ]
    for role, ts, text in session["turns"]:
        who = USER_NAME if role == "user" else "Claude"
        when = fmt_date(ts, "%Y-%m-%d %H:%M")
        lines.append(f"### {who} — {when}" if when else f"### {who}")
        lines.append("")
        lines.append(text)
        lines.append("")
    return '\n'.join(lines)

def sync_code_sessions(state):
    """Sync new and changed Claude Code sessions."""
    if not CLAUDE_CODE_DIR.exists():
        print("  Claude Code directory niet gevonden, sla over.")
        return 0

    legacy_synced = set(state.get("synced_code", []))
    meta = state.setdefault("code_meta", {})
    titles = load_desktop_titles()
    taken = {m["file"] for m in meta.values() if m.get("file")}
    new_count = updated_count = 0

    for project_dir in sorted(CLAUDE_CODE_DIR.iterdir()):
        if not project_dir.is_dir():
            continue

        project_name = get_project_name(project_dir.name)
        for jsonl_file in sorted(project_dir.glob("*.jsonl"), key=os.path.getmtime):
            session_key = f"{project_dir.name}/{jsonl_file.stem}"
            stat = jsonl_file.stat()
            signature = f"{stat.st_size}:{int(stat.st_mtime)}"
            known = meta.get(session_key)
            if known and known.get("sig") == signature:
                continue

            # Skip very small files (< 500 bytes, likely empty sessions); retry when they grow
            if stat.st_size < 500:
                continue

            try:
                session = parse_claude_code_session(jsonl_file)
            except Exception as e:
                print(f"  ! Fout bij parsen {jsonl_file.name}: {e}")
                continue

            if not session["user_messages"]:
                meta[session_key] = {"sig": signature, "file": None}
                continue

            date = fmt_date(session["first_timestamp"])
            note_name = known.get("file") if known else None
            if not note_name and session_key in legacy_synced:
                note_name = legacy_note_name(project_name, session, taken)
            is_new = note_name is None
            if is_new:
                note_name = new_note_name(project_name, session["user_messages"][0], date, taken)
            taken.add(note_name)

            all_user_text = ' '.join(session["user_messages"])
            analysis_text = all_user_text + ' ' + ' '.join(session["assistant_texts"][:20])
            topics = classify_topics(analysis_text) or [DEFAULT_CODE_TOPIC]
            tags = extract_tags(analysis_text)
            project_tag = project_name.lower().replace(' ', '-')
            if project_tag not in tags:
                tags.insert(0, project_tag)
            msg_count = len(session["turns"])
            importance = "high" if msg_count >= 20 else ("medium" if msg_count >= 8 else "low")
            title = titles.get(jsonl_file.stem)

            CODE_CHATS_DIR.mkdir(parents=True, exist_ok=True)
            TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
            (CODE_CHATS_DIR / f"{note_name}.md").write_text(
                generate_code_page(note_name, project_name, session, title, topics, tags, importance, jsonl_file.stem))
            (TRANSCRIPTS_DIR / f"{note_name} (transcript).md").write_text(
                generate_transcript(note_name, project_name, session, title, jsonl_file.stem))

            meta[session_key] = {"sig": signature, "file": note_name}
            legacy_synced.add(session_key)
            if is_new:
                new_count += 1
                print(f"  + [{project_name}] {note_name}")
            else:
                updated_count += 1
                print(f"  ~ [{project_name}] {note_name}")

    state["synced_code"] = sorted(legacy_synced)
    print(f"   {updated_count} bijgewerkte code sessies")
    return new_count + updated_count


# ===== TOPIC REBUILD =====

def rebuild_topics():
    """Rebuild all topic MOC pages based on current vault contents."""
    topic_convs = defaultdict(list)

    for chat_dir in [CHATS_DIR, CODE_CHATS_DIR]:
        if not chat_dir.exists():
            continue
        for md_file in sorted(chat_dir.glob("*.md")):
            content = md_file.read_text()

            fm_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
            if not fm_match:
                continue
            fm = fm_match.group(1)

            date_match = re.search(r'date:\s*(\S+)', fm)
            importance_match = re.search(r'importance:\s*(\S+)', fm)
            topics_match = re.search(r'topics:\s*\[(.+?)\]', fm)
            source_match = re.search(r'source:\s*(\S+)', fm)

            topics = [t.strip().strip('"') for t in topics_match.group(1).split(',')] if topics_match else []

            # Eerste alinea na ## Samenvatting
            summary_match = re.search(r'## Samenvatting\n\n(.+?)(?=\n\n|\Z)', content, re.DOTALL)
            summary = summary_match.group(1).strip()[:120].replace('\n', ' ') if summary_match else ""

            entry = {
                "safe_name": md_file.stem,
                "date": date_match.group(1) if date_match else "",
                "importance": importance_match.group(1) if importance_match else "medium",
                "summary": summary,
                "source": source_match.group(1) if source_match else "web",
            }
            for topic in topics:
                topic_convs[topic].append(entry)

    TOPICS_DIR.mkdir(parents=True, exist_ok=True)

    for topic, convs in sorted(topic_convs.items(), key=lambda x: -len(x[1])):
        description = TOPIC_DESCRIPTIONS.get(topic) or f"Gesprekken over {topic}."
        importance_order = {"high": 0, "medium": 1, "low": 2}
        convs_sorted = sorted(convs, key=lambda c: (importance_order.get(c['importance'], 1), c['date']))

        high = [c for c in convs_sorted if c['importance'] == 'high']
        medium = [c for c in convs_sorted if c['importance'] == 'medium']
        low = [c for c in convs_sorted if c['importance'] == 'low']

        web_count = sum(1 for c in convs if c['source'] != 'claude-code')
        code_count = sum(1 for c in convs if c['source'] == 'claude-code')

        def conv_list(conv_group):
            lines = []
            for c in conv_group:
                imp_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(c['importance'], "🟡")
                source_icon = "💻" if c['source'] == 'claude-code' else "🌐"
                lines.append(f"- {imp_icon}{source_icon} [[{c['safe_name']}]] _{c['date']}_ — {c['summary']}")
            return '\n'.join(lines) if lines else '_Geen._'

        total = len(convs)
        source_line = f"🌐 {web_count} web | 💻 {code_count} code" if code_count > 0 else f"🌐 {web_count} web"

        content = f"""---
tags: ["topic", "moc"]
type: topic
total_chats: {total}
---

# {topic}

{description}

> **{total} gesprekken** | {source_line}

## Belangrijke Chats 🔴

{conv_list(high)}

## Overige Chats 🟡

{conv_list(medium)}

## Korte / Bijzaken 🟢

{conv_list(low)}
"""
        (TOPICS_DIR / f"{topic}.md").write_text(content)
        print(f"  {topic} ({total} chats)")

    return len(topic_convs)


# ===== UPDATE HOME =====

def update_home(state):
    """Update the Home.md dashboard with current stats."""
    total_web = len(list(CHATS_DIR.glob("*.md"))) if CHATS_DIR.exists() else 0
    total_code = len(list(CODE_CHATS_DIR.glob("*.md"))) if CODE_CHATS_DIR.exists() else 0
    total_topics = len(list(TOPICS_DIR.glob("*.md"))) if TOPICS_DIR.exists() else 0
    total = total_web + total_code
    last_sync = datetime.now().strftime("%Y-%m-%d %H:%M")

    home_path = BASE_DIR / "Home.md"
    if home_path.exists():
        content = home_path.read_text()
        old_stats = re.search(r'> \*\*\d+ gesprekken\*\*.*', content)
        if old_stats:
            new_stats = f"> **{total} gesprekken** (🌐 {total_web} web + 💻 {total_code} code) | **{total_topics} onderwerpen** | Laatste sync: {last_sync}"
            home_path.write_text(content.replace(old_stats.group(0), new_stats))
            print(f"  Home.md bijgewerkt ({total} chats)")


# ===== MAIN =====

def main():
    args = sys.argv[1:]
    web_only = "--web-only" in args
    code_only = "--code-only" in args
    rebuild = "--rebuild-topics" in args

    state = load_state()
    print("🧠 AI Brain Vault Sync")
    print(f"   Laatste sync: {state.get('last_sync') or 'Nooit'}")
    print()

    total_new = 0

    if not code_only:
        print("📡 Syncing Claude.ai web conversations...")
        new_web = sync_web_conversations(state)
        total_new += new_web
        print(f"   {new_web} nieuwe web chats\n")

    if not web_only:
        print("💻 Syncing Claude Code sessions...")
        changed_code = sync_code_sessions(state)
        total_new += changed_code
        print(f"   {changed_code} nieuwe of bijgewerkte code sessies\n")

    if total_new > 0 or rebuild:
        print("📚 Topic pages opnieuw genereren...")
        rebuild_topics()
        print()

        print("🏠 Home.md bijwerken...")
        update_home(state)
        print()

    save_state(state)

    print(f"{'='*50}")
    print(f"✅ Sync compleet: {total_new} nieuwe of bijgewerkte items")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
