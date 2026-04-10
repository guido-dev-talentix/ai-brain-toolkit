#!/usr/bin/env python3
"""
AI Brain Vault Sync — Syncs Claude conversations into an Obsidian vault.

Supports:
  1. Claude.ai web conversations (exported conversations.json)
  2. Claude Code CLI sessions (~/.claude/projects/)

Usage:
  python3 sync_vault.py                    # Sync everything
  python3 sync_vault.py --web-only         # Claude.ai web only
  python3 sync_vault.py --code-only        # Claude Code only
  python3 sync_vault.py --rebuild-topics   # Rebuild topic pages
  python3 sync_vault.py --config path.json # Use custom config file
"""

import json
import os
import sys
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ===== CONFIG =====

DEFAULT_CONFIG_LOCATIONS = [
    Path.cwd() / "config.json",
    Path(__file__).parent.parent / "config.json",
    Path.home() / ".ai-brain" / "config.json",
]

DEFAULT_TOPIC_KEYWORDS = {
    "Engineering": ["api", "backend", "frontend", "react", "next.js", "typescript",
                    "python", "supabase", "database", "deploy", "docker"],
    "AI & LLMs": ["ai", "llm", "claude", "gpt", "prompt", "rag", "fine-tun",
                   "machine learning", "embedding", "token"],
    "Infrastructure": ["server", "vps", "docker", "dns", "ssh", "deployment",
                       "ci/cd", "monitoring", "nginx"],
}


def load_config(config_path=None):
    """Load configuration from JSON file."""
    if config_path:
        path = Path(config_path).expanduser()
        if not path.exists():
            print(f"Config file not found: {path}")
            sys.exit(1)
        with open(path) as f:
            return json.load(f)

    for path in DEFAULT_CONFIG_LOCATIONS:
        if path.exists():
            with open(path) as f:
                print(f"Using config: {path}")
                return json.load(f)

    print("No config.json found. Copy config.example.json to config.json and edit it.")
    sys.exit(1)


def resolve_paths(config):
    """Resolve ~ and relative paths in config."""
    vault_dir = Path(config["vault_dir"]).expanduser().resolve()
    conversations_file = Path(config["conversations_file"]).expanduser().resolve()
    claude_code_dir = Path(config.get("claude_code_dir", "~/.claude/projects")).expanduser().resolve()

    return vault_dir, conversations_file, claude_code_dir


# ===== HELPERS =====

def load_state(state_file):
    """Load sync state (tracks which conversations are already synced)."""
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {"synced_web": [], "synced_code": [], "last_sync": None}


def save_state(state, state_file):
    """Save sync state."""
    state["last_sync"] = datetime.now(timezone.utc).isoformat()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)


def safe_filename(name, fallback="Untitled"):
    """Convert a name to a safe filename for Obsidian."""
    if not name or not name.strip():
        return fallback
    safe = name.replace('/', '-').replace('\\', '-').replace(':', ' -')
    safe = safe.replace('"', "'").replace('|', '-').replace('?', '')
    safe = safe.replace('*', '').replace('<', '').replace('>', '')
    safe = safe.rstrip('. ').strip()
    return safe if safe else fallback


def classify_topics(text, topic_keywords):
    """Classify text into topics based on keyword matching."""
    text_lower = text.lower()
    scores = {}
    for topic, keywords in topic_keywords.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[topic] = score
    return [t for t, _ in sorted(scores.items(), key=lambda x: -x[1])[:3]]


def extract_tags(text, topic_keywords, max_tags=8):
    """Extract tags from text based on keyword frequency."""
    text_lower = text.lower()
    all_keywords = []
    for keywords in topic_keywords.values():
        for kw in keywords:
            if kw in text_lower:
                all_keywords.append(kw.replace(' ', '-'))
    seen = set()
    tags = []
    for kw in all_keywords:
        if kw not in seen:
            seen.add(kw)
            tags.append(kw)
    return tags[:max_tags]


def generate_chat_page(name, uuid, date, summary, takeaways, tags, topics,
                       related_names, importance, source="web", claude_url=None):
    """Generate an Obsidian markdown page for a chat."""
    if not claude_url and uuid and source == "web":
        claude_url = f"https://claude.ai/chat/{uuid}"

    fm_tags = ', '.join(f'"{t}"' for t in tags)
    fm_topics = ', '.join(f'"{t}"' for t in topics)
    importance_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(importance, "🟡")

    topic_links = '\n'.join(f"- [[{t}]]" for t in topics)
    related_links = '\n'.join(f"- [[{r}]]" for r in related_names) if related_names else "_No related chats found._"
    takeaway_bullets = '\n'.join(f"- {t}" for t in takeaways) if takeaways else "- Auto-synced, not yet enriched"

    source_label = "Claude.ai" if source == "web" else "Claude Code"
    open_link = f"> [Open in Claude]({claude_url})" if claude_url else f"> Source: {source_label}"

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

{importance_icon} **Importance:** {importance} | **Date:** {date} | **Source:** {source_label}

{open_link}

## Summary

{summary}

## Key Takeaways

{takeaway_bullets}

## Topics

{topic_links}

## Related Chats

{related_links}
"""


# ===== CLAUDE.AI WEB SYNC =====

def sync_web_conversations(state, conversations_file, chats_dir, topic_keywords):
    """Sync new conversations from conversations.json."""
    if not conversations_file.exists():
        print("  conversations.json not found, skipping.")
        return 0

    with open(conversations_file) as f:
        conversations = json.load(f)

    synced_uuids = set(state.get("synced_web", []))
    new_count = 0

    for conv in conversations:
        uuid = conv.get("uuid", "")
        if uuid in synced_uuids:
            continue

        name = conv.get("name", "") or ""
        summary = conv.get("summary", "") or "No summary available."
        date = (conv.get("created_at", "") or "")[:10]
        messages = conv.get("chat_messages", [])

        if not messages and not name:
            synced_uuids.add(uuid)
            continue

        all_text = f"{name} {summary} "
        for msg in messages:
            text = msg.get("text", "")
            if text:
                all_text += text + " "

        topics = classify_topics(all_text, topic_keywords)
        tags = extract_tags(all_text, topic_keywords)
        msg_count = len(messages)
        importance = "high" if msg_count >= 10 else ("medium" if msg_count >= 4 else "low")

        takeaways = []
        if summary and len(summary) > 50:
            sentences = summary.replace("**", "").split(". ")
            takeaways = [s.strip() + "." for s in sentences[1:4] if len(s.strip()) > 20]

        safe_name = safe_filename(name, f"Chat {uuid[:8]}")
        filepath = chats_dir / f"{safe_name}.md"
        if filepath.exists():
            safe_name = f"{safe_name} ({date})"
            filepath = chats_dir / f"{safe_name}.md"

        content = generate_chat_page(
            name=name or "Untitled conversation",
            uuid=uuid,
            date=date,
            summary=summary,
            takeaways=takeaways,
            tags=tags,
            topics=topics if topics else ["Other"],
            related_names=[],
            importance=importance,
            source="web"
        )

        chats_dir.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(content)

        synced_uuids.add(uuid)
        new_count += 1
        print(f"  + {safe_name}")

    state["synced_web"] = list(synced_uuids)
    return new_count


# ===== CLAUDE CODE SYNC =====

def parse_claude_code_session(jsonl_path):
    """Parse a Claude Code JSONL session file and extract key info."""
    user_messages = []
    assistant_texts = []
    first_timestamp = None
    last_timestamp = None
    session_id = None
    git_branch = None
    cwd = None

    with open(jsonl_path) as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            timestamp = obj.get("timestamp", "")
            if timestamp:
                if not first_timestamp:
                    first_timestamp = timestamp
                last_timestamp = timestamp

            if not session_id:
                session_id = obj.get("sessionId", "")
            if not git_branch:
                git_branch = obj.get("gitBranch", "")
            if not cwd:
                cwd = obj.get("cwd", "")

            msg_type = obj.get("type", "")

            if msg_type == "user":
                msg = obj.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, str):
                    if not content.startswith("<local-command") and not content.startswith("<command-"):
                        clean = content.strip()
                        if clean and len(clean) > 5:
                            user_messages.append(clean[:500])

            elif msg_type == "assistant":
                msg = obj.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            text = c.get("text", "").strip()
                            if text and len(text) > 10:
                                assistant_texts.append(text[:300])
                elif isinstance(content, str) and content.strip():
                    assistant_texts.append(content[:300])

    return {
        "session_id": session_id,
        "user_messages": user_messages,
        "assistant_texts": assistant_texts[:20],
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "git_branch": git_branch,
        "cwd": cwd,
        "message_count": len(user_messages) + len(assistant_texts),
    }


def get_project_name(encoded_path):
    """Convert encoded project path to readable name."""
    parts = encoded_path.split('-')
    try:
        idx = parts.index('Projects')
        name = ' '.join(parts[idx+1:])
    except ValueError:
        name = ' '.join(parts[-2:]) if len(parts) >= 2 else encoded_path
    return name.strip() or encoded_path


def sync_code_sessions(state, claude_code_dir, code_chats_dir, topic_keywords):
    """Sync new Claude Code sessions."""
    if not claude_code_dir.exists():
        print("  Claude Code directory not found, skipping.")
        return 0

    synced_sessions = set(state.get("synced_code", []))
    new_count = 0

    for project_dir in sorted(claude_code_dir.iterdir()):
        if not project_dir.is_dir():
            continue

        project_name = get_project_name(project_dir.name)
        jsonl_files = sorted(project_dir.glob("*.jsonl"), key=os.path.getmtime)

        for jsonl_file in jsonl_files:
            session_key = f"{project_dir.name}/{jsonl_file.stem}"
            if session_key in synced_sessions:
                continue

            if jsonl_file.stat().st_size < 500:
                continue

            try:
                session = parse_claude_code_session(jsonl_file)
            except Exception as e:
                print(f"  ! Error parsing {jsonl_file.name}: {e}")
                synced_sessions.add(session_key)
                continue

            if not session["user_messages"]:
                synced_sessions.add(session_key)
                continue

            first_prompt = session["user_messages"][0] if session["user_messages"] else ""
            all_text = ' '.join(session["user_messages"][:10]) + ' ' + ' '.join(session["assistant_texts"][:10])

            title_text = first_prompt[:80].replace('\n', ' ').strip()
            if len(first_prompt) > 80:
                title_text += "..."

            date = ""
            if session["first_timestamp"]:
                try:
                    dt = datetime.fromisoformat(session["first_timestamp"].replace('Z', '+00:00'))
                    date = dt.strftime("%Y-%m-%d")
                except Exception:
                    date = ""

            topics = classify_topics(all_text, topic_keywords)
            tags = extract_tags(all_text, topic_keywords)
            if project_name.lower() not in [t.lower() for t in tags]:
                tags.insert(0, project_name.lower().replace(' ', '-'))

            msg_count = session["message_count"]
            importance = "high" if msg_count >= 20 else ("medium" if msg_count >= 8 else "low")

            summary_parts = []
            if first_prompt:
                summary_parts.append(f"**First prompt:** {first_prompt[:200]}")
            if session["git_branch"]:
                summary_parts.append(f"**Git branch:** `{session['git_branch']}`")
            summary_parts.append(f"**Project:** {project_name} | **Messages:** {msg_count}")
            summary = '\n\n'.join(summary_parts)

            takeaways = [msg[:150] for msg in session["user_messages"][:5]]

            chat_name = f"CC - {project_name} - {title_text}"
            safe_name = safe_filename(chat_name, f"CC-{jsonl_file.stem[:8]}")
            if len(safe_name) > 120:
                safe_name = safe_name[:120]

            filepath = code_chats_dir / f"{safe_name}.md"
            if filepath.exists():
                safe_name = f"{safe_name} ({date})"
                filepath = code_chats_dir / f"{safe_name}.md"

            content = generate_chat_page(
                name=chat_name,
                uuid=jsonl_file.stem,
                date=date,
                summary=summary,
                takeaways=takeaways,
                tags=tags,
                topics=topics if topics else ["AI & LLMs"],
                related_names=[],
                importance=importance,
                source="claude-code",
                claude_url=None
            )

            code_chats_dir.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w') as f:
                f.write(content)

            synced_sessions.add(session_key)
            new_count += 1
            print(f"  + [{project_name}] {safe_name}")

    state["synced_code"] = list(synced_sessions)
    return new_count


# ===== TOPIC REBUILD =====

def rebuild_topics(chats_dir, code_chats_dir, topics_dir, topic_keywords):
    """Rebuild all topic MOC pages based on current vault contents."""
    topic_convs = defaultdict(list)

    all_chat_dirs = [chats_dir, code_chats_dir]
    for chat_dir in all_chat_dirs:
        if not chat_dir.exists():
            continue
        for md_file in sorted(chat_dir.glob("*.md")):
            with open(md_file) as f:
                content = f.read()

            fm_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
            if not fm_match:
                continue

            fm = fm_match.group(1)
            name = md_file.stem

            date_match = re.search(r'date:\s*(\S+)', fm)
            importance_match = re.search(r'importance:\s*(\S+)', fm)
            topics_match = re.search(r'topics:\s*\[(.+?)\]', fm)
            source_match = re.search(r'source:\s*(\S+)', fm)

            date = date_match.group(1) if date_match else ""
            importance = importance_match.group(1) if importance_match else "medium"
            source = source_match.group(1) if source_match else "web"

            topics = []
            if topics_match:
                topics = [t.strip().strip('"') for t in topics_match.group(1).split(',')]

            summary_match = re.search(r'## Summary\n\n(.+?)(?=\n\n##|\Z)', content, re.DOTALL)
            summary = summary_match.group(1).strip()[:120] if summary_match else ""

            entry = {
                "safe_name": name,
                "date": date,
                "importance": importance,
                "summary": summary,
                "source": source,
                "folder": "Claude Code" if chat_dir == code_chats_dir else "Chats",
            }

            for topic in topics:
                topic_convs[topic].append(entry)

    topics_dir.mkdir(parents=True, exist_ok=True)

    for topic, convs in sorted(topic_convs.items(), key=lambda x: -len(x[1])):
        high = [c for c in convs if c.get('importance') == 'high']
        medium = [c for c in convs if c.get('importance') == 'medium']
        low = [c for c in convs if c.get('importance') == 'low']

        web_count = sum(1 for c in convs if c.get('source') != 'claude-code')
        code_count = sum(1 for c in convs if c.get('source') == 'claude-code')

        def conv_list(conv_group):
            lines = []
            for c in conv_group:
                name = c['safe_name']
                date = c.get('date', '')
                summary = c.get('summary', '')[:120]
                imp_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(c.get('importance', 'medium'), "🟡")
                source_icon = "💻" if c.get('source') == 'claude-code' else "🌐"
                lines.append(f"- {imp_icon}{source_icon} [[{name}]] _{date}_ — {summary}")
            return '\n'.join(lines) if lines else '_None._'

        total = len(convs)
        source_line = f"🌐 {web_count} web | 💻 {code_count} code" if code_count > 0 else f"🌐 {web_count} web"

        content = f"""---
tags: ["topic", "moc"]
type: topic
total_chats: {total}
---

# {topic}

> **{total} conversations** | {source_line}

## Important 🔴

{conv_list(high)}

## Regular 🟡

{conv_list(medium)}

## Minor 🟢

{conv_list(low)}
"""

        filepath = topics_dir / f"{topic}.md"
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  {topic} ({total} chats)")

    return len(topic_convs)


# ===== UPDATE HOME =====

def update_home(vault_dir, chats_dir, code_chats_dir, topics_dir, state_file):
    """Update the Home.md dashboard with current stats."""
    total_web = len(list(chats_dir.glob("*.md"))) if chats_dir.exists() else 0
    total_code = len(list(code_chats_dir.glob("*.md"))) if code_chats_dir.exists() else 0
    total_topics = len(list(topics_dir.glob("*.md"))) if topics_dir.exists() else 0
    total = total_web + total_code

    state = load_state(state_file)
    last_sync = state.get("last_sync", "Never")
    if last_sync and last_sync != "Never":
        try:
            dt = datetime.fromisoformat(last_sync)
            last_sync = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass

    home_path = vault_dir / "Home.md"
    if home_path.exists():
        with open(home_path) as f:
            content = f.read()
        old_stats = re.search(r'> \*\*\d+ conversations\*\*.*', content)
        if old_stats:
            new_stats = f"> **{total} conversations** (🌐 {total_web} web + 💻 {total_code} code) | **{total_topics} topics** | Last sync: {last_sync}"
            content = content.replace(old_stats.group(0), new_stats)
            with open(home_path, 'w') as f:
                f.write(content)
            print(f"  Home.md updated ({total} chats)")
    else:
        # Create initial Home.md
        content = f"""---
tags: ["dashboard"]
type: home
---

# AI Brain

Your personal knowledge base of Claude conversations.

> **{total} conversations** (🌐 {total_web} web + 💻 {total_code} code) | **{total_topics} topics** | Last sync: {last_sync}

## Topics

Browse by topic in the `Topics/` folder, or use the graph view to explore connections.

## Quick Links

- [[Topics/]] — All topic pages (Map of Content)
- [[Chats/]] — Claude.ai web conversations
- [[Claude Code/]] — Claude Code CLI sessions
"""
        with open(home_path, 'w') as f:
            f.write(content)
        print(f"  Home.md created ({total} chats)")


# ===== MAIN =====

def main():
    args = sys.argv[1:]
    web_only = "--web-only" in args
    code_only = "--code-only" in args
    rebuild = "--rebuild-topics" in args

    config_path = None
    if "--config" in args:
        idx = args.index("--config")
        if idx + 1 < len(args):
            config_path = args[idx + 1]

    config = load_config(config_path)
    vault_dir, conversations_file, claude_code_dir = resolve_paths(config)
    topic_keywords = config.get("topic_keywords", DEFAULT_TOPIC_KEYWORDS)

    chats_dir = vault_dir / "Chats"
    code_chats_dir = vault_dir / "Claude Code"
    topics_dir = vault_dir / "Topics"
    state_file = Path(__file__).parent / ".sync_state.json"

    state = load_state(state_file)
    print(f"🧠 AI Brain Vault Sync")
    print(f"   Vault: {vault_dir}")
    print(f"   Last sync: {state.get('last_sync', 'Never')}")
    print()

    total_new = 0

    if not code_only:
        print("📡 Syncing Claude.ai web conversations...")
        new_web = sync_web_conversations(state, conversations_file, chats_dir, topic_keywords)
        total_new += new_web
        print(f"   {new_web} new web chats\n")

    if not web_only:
        print("💻 Syncing Claude Code sessions...")
        new_code = sync_code_sessions(state, claude_code_dir, code_chats_dir, topic_keywords)
        total_new += new_code
        print(f"   {new_code} new code sessions\n")

    if total_new > 0 or rebuild:
        print("📚 Rebuilding topic pages...")
        rebuild_topics(chats_dir, code_chats_dir, topics_dir, topic_keywords)
        print()

        print("🏠 Updating Home.md...")
        update_home(vault_dir, chats_dir, code_chats_dir, topics_dir, state_file)
        print()

    save_state(state, state_file)

    print(f"{'='*50}")
    print(f"✅ Sync complete: {total_new} new items")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
