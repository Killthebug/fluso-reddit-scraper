# Reddit Thread Scraping — Strategy Reference

## Strategy 1: Unauthenticated JSON API (best effort)

Append `.json` to any Reddit thread URL. Works from residential IPs, often blocked from datacenter/cloud IPs.

```
https://www.reddit.com/r/AskReddit/comments/<id>/<slug>.json?limit=100&raw_json=1
```

The response is a 2-element JSON array: `[post_data, comment_data]`.

## Strategy 2: OAuth2 (script / installed app)

Works from any IP. Requires a Reddit developer application.

### Setup (one-time, 2 minutes)

1. Go to https://www.reddit.com/prefs/apps
2. Click "create app" or "create another app"
3. Name: anything (e.g. "research-scraper")
4. Select **"installed app"**
5. Redirect URI: `http://localhost:8080` (not actually used)
6. Click "create app"
7. Copy the string **under** the app name (e.g. `oBJCSEj0mZYHdgTiwQ`) — that's your `REDDIT_CLIENT_ID`
8. `REDDIT_CLIENT_SECRET` should be an empty string for installed apps

Export:
```bash
export REDDIT_CLIENT_ID="oBJCSEj0mZYHdgTiwQ"
export REDDIT_CLIENT_SECRET=""
```

Then run with `--oauth` flag.

### How it works

The "installed app" grant type requests `https://oauth.reddit.com/grants/installed_client` with a `device_id` field. Reddit returns a read-only access token. The token is used to call `https://oauth.reddit.com/r/<sub>/comments/<id>.json`.

No user login required. Rate limit: 60 requests/minute.

## Strategy 3: Exa fallback (when OAuth is not available)

If the runtime has Exa connected, the agent should use `tool-search` → `EXA_AI__SEARCH` to find cached/article versions of the thread content. This was the approach used successfully in the `1t9322i` case.

**Workflow:**
1. Extract the Reddit post ID from the URL
2. Search Exa for: `"<post title keywords>" reddit` or `reddit <subreddit> <post_id>`
3. Use `EXA_AI__GET_CONTENTS` on the most relevant results to retrieve article summaries
4. Combine and present the content

**Limitations:** Secondhand content (news articles summarizing the thread), not the original comments. Good for understanding the gist and extracting themes, but not for exact comment text.

### Exa as first resort for the agent

When Exa is connected AND the agent's runtime IP is blocked AND no OAuth credentials are configured, the agent should go straight to Exa. The Python script will fail with a clear error; the agent should catch this and pivot.

## Strategy 4: PullPush (Reddit archive)

Free, no-auth archive API. Good for historical threads or when other methods fail.

```bash
# Search by post ID
curl "https://api.pullpush.io/reddit/search/submission/?ids=<post_id>"

# Search comments of a thread
curl "https://api.pullpush.io/reddit/search/comment/?link_id=<post_id>"
```

**Limitations:** Archive may not have recent threads. No real-time data. Comment coverage is incomplete.

## Strategy 5: Cached versions

- Google Cache: `https://webcache.googleusercontent.com/search?q=cache:reddit.com/r/...`
- Archive.org: `https://web.archive.org/web/*/reddit.com/r/...`
- Removeddit/Reveddit: Alternative frontends (many are now defunct but worth trying)

## Choosing a Strategy

| Environment | Best Strategy |
|---|---|
| Local machine / residential IP | Strategy 1 (unauthenticated JSON) |
| Cloud/server IP + have Reddit app | Strategy 2 (OAuth) |
| Cloud/server IP + no Reddit app | Strategy 3 (Exa) or 4 (PullPush) |
| Historical/archived thread | Strategy 4 (PullPush) or cached versions |
