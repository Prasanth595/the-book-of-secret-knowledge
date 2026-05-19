#!/usr/bin/env python3
"""Create a maintainer report for open pull requests."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


KEYWORDS = {
    "containers/orchestration": ("container", "kube", "docker", "orchestration", "platform"),
    "security": ("security", "cve", "vuln", "pentest", "opsec", "hack", "threat"),
    "web tools": ("web", "browser", "http", "headers", "pwa"),
    "cli tools": ("cli", "terminal", "command", "shell", "git", "monitor"),
    "documentation": ("docs", "readme", "image", "typo", "documentation"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="trimstray/the-book-of-secret-knowledge")
    parser.add_argument("--limit", type=int, default=0, help="Maximum PRs to include; 0 means all.")
    parser.add_argument("--json", action="store_true", help="Emit raw normalized JSON.")
    return parser.parse_args()


def fetch_page(repo: str, page: int) -> list[dict]:
    url = f"https://api.github.com/repos/{repo}/pulls?state=open&per_page=100&page={page}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "the-book-of-secret-knowledge-pr-report/1.0",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_open_prs(repo: str, limit: int) -> list[dict]:
    prs: list[dict] = []
    page = 1
    while True:
        chunk = fetch_page(repo, page)
        if not chunk:
            break
        prs.extend(chunk)
        if limit and len(prs) >= limit:
            return prs[:limit]
        page += 1
    return prs


def classify(title: str) -> str:
    lowered = title.lower()
    for category, words in KEYWORDS.items():
        if any(word in lowered for word in words):
            return category
    return "other"


def normalize(pr: dict) -> dict:
    title = pr["title"]
    return {
        "number": pr["number"],
        "title": title,
        "author": pr["user"]["login"],
        "url": pr["html_url"],
        "created_at": pr["created_at"],
        "updated_at": pr["updated_at"],
        "category": classify(title),
    }


def age_days(iso_timestamp: str) -> int:
    created = dt.datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    return (dt.datetime.now(dt.timezone.utc) - created).days


def print_markdown(repo: str, items: list[dict]) -> None:
    generated_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    counts = collections.Counter(item["category"] for item in items)
    print(f"# Open Pull Request Backlog")
    print()
    print(f"Repository: `{repo}`")
    print(f"Generated: `{generated_at}`")
    print(f"Open pull requests scanned: **{len(items)}**")
    print()
    print("## Category Snapshot")
    print()
    for category, count in counts.most_common():
        print(f"- **{category}**: {count}")
    print()
    print("## Maintainer Queue")
    print()
    print("| PR | Category | Age | Title | Author |")
    print("| --- | --- | ---: | --- | --- |")
    for item in sorted(items, key=lambda row: (row["category"], row["number"])):
        query = urllib.parse.quote(item["title"])
        title = item["title"].replace("|", "\\|")
        print(
            f"| [#{item['number']}]({item['url']}) | {item['category']} | "
            f"{age_days(item['created_at'])}d | {title} | @{item['author']} |"
        )
    print()
    print("## Triage Rules")
    print()
    print("- Merge small single-link PRs only after duplicate, category, and link checks pass.")
    print("- Close promotional or low-signal submissions with a short reason and a pointer to `CONTRIBUTING.md`.")
    print("- Convert broad PRs into smaller reviewable changes when they mix unrelated categories.")
    print("- Prefer replacing dead links with canonical upstream URLs over deleting historical resources immediately.")


def main() -> int:
    args = parse_args()
    items = [normalize(pr) for pr in fetch_open_prs(args.repo, args.limit)]
    if args.json:
        print(json.dumps(items, indent=2, sort_keys=True))
    else:
        print_markdown(args.repo, items)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
