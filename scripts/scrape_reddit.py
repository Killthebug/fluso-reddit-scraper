#!/usr/bin/env python3
"""
Scrape Reddit thread content via the public JSON API, with multi-strategy fallback.

Strategies (tried in order):
  1. Unauthenticated JSON API  — works from residential/non-blocked IPs
  2. OAuth2 (script app)        — works from any IP; needs REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET
  3. Exa search fallback guide  — instructions for the agent to use tool-execute with Exa

Usage:
    python scrape_reddit.py <url> [--limit N] [--depth N] [--format json|text|md] [--sort hot|new|top|controversial]

Environment variables for OAuth:
    REDDIT_CLIENT_ID      — Reddit "installed app" client ID
    REDDIT_CLIENT_SECRET  — Reddit "installed app" client secret (use empty string for installed apps)
"""

import json
import os
import re
import sys
import argparse
from urllib.parse import urlparse
from typing import Optional

import requests

# ── Configuration ──

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
TIMEOUT = 15

OAUTH_URL = "https://www.reddit.com/api/v1/access_token"
API_BASE = "https://oauth.reddit.com"


# ── URL parsing ──

def reddit_json_url(url: str, sort: str = "hot", limit: int = 100) -> str:
    """Convert any Reddit thread URL to its .json API endpoint."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    match = re.match(r"/(r/\w+/comments/[a-z0-9]+)", path)
    if match:
        base = match.group(1)
        return f"https://www.reddit.com/{base}.json?sort={sort}&limit={limit}&raw_json=1"
    raise ValueError(f"Could not parse Reddit thread URL: {url}")


# ── Strategy 1: Unauthenticated ──

def fetch_unauthenticated(url: str, sort: str = "hot", limit: int = 100) -> dict:
    """Fetch thread via the public JSON API (no auth)."""
    api_url = reddit_json_url(url, sort=sort, limit=limit)
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(api_url, headers=headers, timeout=TIMEOUT)
    if resp.status_code == 403 or "blocked" in resp.text.lower():
        raise PermissionError("Reddit blocked this IP. Try strategy 2 (OAuth) or 3 (Exa fallback).")
    resp.raise_for_status()
    return resp.json()


# ── Strategy 2: OAuth2 ──

def _get_oauth_token(client_id: str, client_secret: str) -> str:
    """Obtain a read-only OAuth2 access token (installed app grant)."""
    data = {
        "grant_type": "https://oauth.reddit.com/grants/installed_client",
        "device_id": "REDDIT_SCRAPER_001",
    }
    auth = (client_id, client_secret) if client_secret else (client_id, "")
    headers = {"User-Agent": USER_AGENT}
    resp = requests.post(OAUTH_URL, auth=auth, data=data, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_oauth(url: str, client_id: str, client_secret: str, sort: str = "hot", limit: int = 100) -> dict:
    """Fetch thread via oauth.reddit.com (works from any IP, requires app registration)."""
    token = _get_oauth_token(client_id, client_secret)
    headers = {"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    match = re.match(r"/(r/\w+/comments/[a-z0-9]+)", path)
    if not match:
        raise ValueError(f"Could not parse Reddit thread URL: {url}")
    api_url = f"{API_BASE}/{match.group(1)}.json?sort={sort}&limit={limit}&raw_json=1"
    resp = requests.get(api_url, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ── Parse response ──

def parse_thread(raw: list) -> dict:
    """Parse raw Reddit JSON array into structured dict with post and comments."""
    if not raw or len(raw) < 2:
        raise ValueError("Unexpected Reddit JSON structure (expected 2-element list)")

    post_data = raw[0]["data"]["children"][0]["data"]
    comment_data = raw[1]["data"]["children"]

    post = {
        "title": post_data.get("title", ""),
        "author": post_data.get("author", "[deleted]"),
        "subreddit": post_data.get("subreddit", ""),
        "score": post_data.get("score", 0),
        "url": post_data.get("url", ""),
        "permalink": post_data.get("permalink", ""),
        "selftext": post_data.get("selftext", ""),
        "selftext_html": post_data.get("selftext_html", ""),
        "created_utc": post_data.get("created_utc", 0),
        "num_comments": post_data.get("num_comments", 0),
    }

    comments = []
    for child in comment_data:
        if child["kind"] == "t1":
            parsed = _parse_comment_tree(child["data"], depth=0)
            if parsed:
                comments.append(parsed)

    return {"post": post, "comments": comments, "comment_count": len(comments)}


def _parse_comment_tree(data: dict, depth: int = 0) -> Optional[dict]:
    """Recursively parse a comment and its nested replies."""
    if data.get("stickied", False):
        return None

    comment = {
        "author": data.get("author", "[deleted]"),
        "body": data.get("body", ""),
        "body_html": data.get("body_html", ""),
        "score": data.get("score", 0),
        "depth": depth,
        "created_utc": data.get("created_utc", 0),
        "replies": [],
    }

    replies = data.get("replies", "")
    if isinstance(replies, dict):
        for child in replies.get("data", {}).get("children", []):
            if child["kind"] == "t1":
                parsed = _parse_comment_tree(child["data"], depth=depth + 1)
                if parsed:
                    comment["replies"].append(parsed)

    return comment


# ── Output formatters ──

def format_text(data: dict, max_replies: int = 10) -> str:
    """Format thread data as readable plain text."""
    post = data["post"]
    lines = [
        f"=== {post['title']} ===",
        f"r/{post['subreddit']} | by u/{post['author']} | score: {post['score']} | {post['num_comments']} comments",
        f"permalink: https://www.reddit.com{post['permalink']}",
        "",
    ]
    if post["selftext"]:
        lines.append("--- Post Body ---")
        lines.append(post["selftext"])
        lines.append("")
    lines.append(f"--- Top {min(len(data['comments']), max_replies)} Comments ---")
    for c in data["comments"][:max_replies]:
        lines.append(_format_comment_text(c))
        lines.append("")
    if len(data["comments"]) > max_replies:
        lines.append(f"... and {len(data['comments']) - max_replies} more comments.")
    return "\n".join(lines)


def _format_comment_text(comment: dict) -> str:
    prefix = "  " * comment["depth"]
    lines = [f"{prefix}[u/{comment['author']} | +{comment['score']}] {comment['body']}"]
    for reply in comment.get("replies", []):
        lines.append(_format_comment_text(reply))
    return "\n".join(lines)


def format_markdown(data: dict, max_replies: int = 10) -> str:
    """Format thread data as Markdown with blockquotes for nested comments."""
    post = data["post"]
    lines = [
        f"# {post['title']}",
        f"**r/{post['subreddit']}** | u/{post['author']} | score: {post['score']} | {post['num_comments']} comments",
        f"[Permalink](https://www.reddit.com{post['permalink']})",
        "",
    ]
    if post["selftext"]:
        lines.append("## Post Body")
        lines.append(post["selftext"])
        lines.append("")
    lines.append(f"## Top Comments ({min(len(data['comments']), max_replies)} shown)")
    lines.append("")
    for c in data["comments"][:max_replies]:
        lines.append(_format_comment_md(c))
        lines.append("---")
        lines.append("")
    if len(data["comments"]) > max_replies:
        lines.append(f"*... and {len(data['comments']) - max_replies} more comments.*")
    return "\n".join(lines)


def _format_comment_md(comment: dict) -> str:
    prefix = "> " * (comment["depth"] + 1)
    lines = [f"{prefix}**u/{comment['author']}** (+{comment['score']})", f"{prefix}"]
    for line in comment["body"].split("\n"):
        lines.append(f"{prefix}{line}")
    for reply in comment.get("replies", []):
        lines.append(_format_comment_md(reply))
    return "\n".join(lines)


# ── Main ──

def main():
    parser = argparse.ArgumentParser(
        description="Scrape a Reddit thread via the public JSON API (multi-strategy fallback)"
    )
    parser.add_argument("url", help="Reddit thread URL")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--depth", type=int, default=None)
    parser.add_argument("--format", choices=["json", "text", "md"], default="text")
    parser.add_argument("--sort", choices=["hot", "new", "top", "controversial"], default="hot")
    parser.add_argument("--max-replies", type=int, default=10)
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--oauth", action="store_true")
    args = parser.parse_args()

    client_id = os.environ.get("REDDIT_CLIENT_ID", "")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")

    raw = None
    strategy_used = None

    if args.oauth or (client_id and client_secret is not None):
        try:
            raw = fetch_oauth(args.url, client_id, client_secret, sort=args.sort, limit=args.limit)
            strategy_used = "oauth"
        except Exception as e:
            if args.oauth:
                print(f"OAuth failed: {e}", file=sys.stderr)
                sys.exit(1)

    if raw is None:
        try:
            raw = fetch_unauthenticated(args.url, sort=args.sort, limit=args.limit)
            strategy_used = "unauthenticated"
        except PermissionError:
            print(
                "ERROR: Reddit blocked this IP.\n\n"
                "To scrape Reddit from this environment, either:\n"
                "  a) Set up OAuth: export REDDIT_CLIENT_ID=... and rerun with --oauth, or\n"
                "  b) Use the Exa fallback strategy (see reddit-scraper skill for details).\n\n"
                "For OAuth setup:\n"
                "  1. Go to https://www.reddit.com/prefs/apps\n"
                "  2. Create an 'installed app'\n"
                "  3. Use the client ID (string under the app name) as REDDIT_CLIENT_ID\n"
                "  4. Set REDDIT_CLIENT_SECRET to an empty string for installed apps",
                file=sys.stderr,
            )
            sys.exit(1)

    if strategy_used:
        print(f"[strategy: {strategy_used}]\n", file=sys.stderr)

    if args.raw:
        print(json.dumps(raw, indent=2))
        return

    data = parse_thread(raw)

    if args.depth is not None:
        def filter_depth(comments, current=0):
            result = []
            for c in comments:
                if current < args.depth:
                    c["replies"] = filter_depth(c.get("replies", []), current + 1)
                    result.append(c)
                elif current == args.depth:
                    stripped = dict(c)
                    stripped["replies"] = []
                    result.append(stripped)
            return result
        data["comments"] = filter_depth(data["comments"])

    if args.format == "json":
        print(json.dumps(data, indent=2))
    elif args.format == "md":
        print(format_markdown(data, max_replies=args.max_replies))
    else:
        print(format_text(data, max_replies=args.max_replies))


if __name__ == "__main__":
    main()
