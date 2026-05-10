# fluso-reddit-scraper

Multi-strategy Reddit thread scraper — extract post content and comments from any Reddit URL. Built as a Fluso workspace skill.

## What it does

Fetches Reddit thread content (post body + comments) with automatic strategy selection:

| Strategy | Works From | Setup |
|---|---|---|
| **1. Unauthenticated JSON API** | Residential/non-blocked IPs | None — just run it |
| **2. OAuth2 (installed app)** | Any IP | 2-min one-time setup at reddit.com/prefs/apps |
| **3. Exa fallback** | Any environment with Exa connected | None — automatic |
| **4. PullPush archive** | Any IP | None |

## Quick Start

```bash
# Install deps
uv sync --project .

# Scrape a thread (Markdown output)
uv run --project . python scripts/scrape_reddit.py \
  "https://www.reddit.com/r/AskReddit/comments/abc123/..." \
  --format md --max-replies 15
```

## Usage

```
python scripts/scrape_reddit.py <url> [options]

Options:
  --limit N          Comments to fetch (default: 100)
  --depth N          Max comment nesting depth
  --format FORMAT    json, text, or md (default: text)
  --sort SORT        hot, new, top, controversial
  --max-replies N    Top-level comments to show (default: 10)
  --raw              Output raw Reddit JSON
  --oauth            Force OAuth (needs REDDIT_CLIENT_ID set)
```

## OAuth Setup (for blocked IPs)

1. Go to https://www.reddit.com/prefs/apps
2. Create an "installed app"
3. Set the client ID:
   ```bash
   export REDDIT_CLIENT_ID="your_client_id"
   export REDDIT_CLIENT_SECRET=""
   ```
4. Run with `--oauth`

## As a Fluso Skill

Place in `skills/reddit-scraper/` in your Fluso workspace. The runtime auto-detects it on the next turn. See `SKILL.md` for the full trigger description and agent workflow.

## License

MIT
