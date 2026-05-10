---
name: reddit-scraper
description: Multi-strategy Reddit thread scraper. Extract post content and comments from any Reddit URL. Use when the user sends a reddit.com link and wants the thread content, comments, or a summary. Triggers on requests like scrape this Reddit thread, get the comments from, what does this Reddit post say, pull this Reddit thread, extract from reddit, or when a task requires reading Reddit thread content. Supports unauthenticated JSON API, OAuth2, Exa fallback, and PullPush archive.
---

# Reddit Scraper

Multi-strategy Reddit thread content extraction. Handles the reality that Reddit blocks datacenter IPs aggressively — the skill provides fallback paths for every environment.

## Quick Start

```bash
uv run --project /fluso/user/workspace/skills/reddit-scraper \
  python /fluso/user/workspace/skills/reddit-scraper/scripts/scrape_reddit.py \
  "<reddit_url>" --format md --max-replies 15
```

If the script fails with a block error (code 1), read the strategy reference and pivot to Exa.

## Choosing Your Path

**Step 1: Try the script.** It auto-detects OAuth credentials and falls back to unauthenticated.

**Step 2: If blocked** — check which applies:

| Situation | Action |
|---|---|
| **Exa is connected in this session** | Skip to Exa fallback below. This is the fastest path from a blocked IP when the user just wants content. |
| **User has Reddit dev credentials** | Set `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` env vars, rerun with `--oauth`. See [strategies.md](references/strategies.md) for setup. |
| **Neither Exa nor OAuth** | Try PullPush archive or cached versions. See details in [strategies.md](references/strategies.md). |

## Exa Fallback (primary fallback for this runtime)

When the script is blocked and Exa is connected:

1. Extract the post ID and title keywords from the Reddit URL
2. Search Exa: `tool-search` → `EXA_AI__SEARCH` with a query like `"<title keywords>" reddit <post_id>` or `reddit <subreddit> <post_id>`
3. Fetch contents: `tool-execute` → `EXA_AI__GET_CONTENTS` on the 3-5 most relevant results (usually news articles or blogs that summarized the thread)
4. Present the combined content to the user

**This is a valid, expected path.** The Exa results are secondhand summaries but are often sufficient for the user's task (e.g., understanding the gist of a thread, extracting themes for brainstorming).

## Script Reference

```
Usage:
  scrape_reddit.py <url> [options]

Options:
  --limit N          Comments to fetch (default: 100, max ~500)
  --depth N          Max comment nesting depth (default: all)
  --format FORMAT    Output format: json, text, md (default: text)
  --sort SORT        Comment sort: hot, new, top, controversial (default: hot)
  --max-replies N    Top-level comments to show in text/md (default: 10)
  --raw              Output raw JSON without parsing
  --oauth            Force OAuth strategy (needs REDDIT_CLIENT_ID set)
```

### Output Formats

- **`md`** — Markdown with blockquoted nested comments; best for feeding into further AI processing
- **`text`** — Plain text with indented nesting; readable for direct display
- **`json`** — Full structured data; use when programmatic processing is needed
- **`--raw`** — Raw Reddit API response; useful for debugging

### Common Patterns

```bash
# Get top 20 comments as Markdown
uv run --project /fluso/user/workspace/skills/reddit-scraper \
  python /fluso/user/workspace/skills/reddit-scraper/scripts/scrape_reddit.py \
  "https://www.reddit.com/r/AskReddit/comments/abc123/..." \
  --format md --max-replies 20 --sort top

# Get all comments as JSON for processing
uv run --project /fluso/user/workspace/skills/reddit-scraper \
  python /fluso/user/workspace/skills/reddit-scraper/scripts/scrape_reddit.py \
  "https://www.reddit.com/r/..." --format json --limit 200
```

## How the Script Works

The script converts any Reddit thread URL (www, old, new, short) to the JSON API endpoint:

```
https://www.reddit.com/r/<sub>/comments/<id>/<slug>.json?sort=hot&limit=100&raw_json=1
```

The response is a 2-element list:
- `[0]` — Post data (title, selftext, author, score, etc.)
- `[1]` — Comments (nested tree with replies)

The parser flattens the tree into a list of comments with `depth` and `replies` fields, skipping stickied/auto-mod comments.

## Limitations

- **Rate limits**: Unauthenticated ~10 req/min, OAuth ~60 req/min
- **Comment pagination**: Reddit's API returns at most ~500 comments per request. For very large threads, use `?after=t1_<comment_id>` to paginate (not yet implemented in the script)
- **Deleted/removed content**: The API returns `[deleted]` or `[removed]` for removed content — no workaround exists
- **NSFW content**: May require OAuth even from non-blocked IPs
