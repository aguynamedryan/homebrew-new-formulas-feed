#!/usr/bin/env python3
"""Fetch new Homebrew formulas and generate an Atom feed for GitHub Pages."""

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree, register_namespace

ATOM_NS = "http://www.w3.org/2005/Atom"
register_namespace("", ATOM_NS)

GITHUB_API = "https://api.github.com"
SEARCH_QUERY = 'repo:Homebrew/homebrew-core "new formula"'
# Match: "formulaname 1.2.3 (new formula)" or "formulaname 1.2.3 (new formulae)"
FORMULA_RE = re.compile(r"^(.+?)\s+([\d][^\s]*)\s+\(new\s+formula", re.IGNORECASE)


def atom(tag):
    return f"{{{ATOM_NS}}}{tag}"


def fetch_new_formula_commits(token=None, max_pages=5):
    """Search for commits containing 'new formula' in homebrew-core.

    Paginates through results because the search also matches merge commits
    that mention 'new formula' in the body, pushing actual new formula commits
    further down the result list.
    """
    all_items = []
    for page in range(1, max_pages + 1):
        params = urllib.parse.urlencode({
            "q": SEARCH_QUERY,
            "sort": "committer-date",
            "order": "desc",
            "per_page": 100,
            "page": page,
        })
        url = f"{GITHUB_API}/search/commits?{params}"

        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())

        items = data.get("items", [])
        all_items.extend(items)
        print(f"  Page {page}: {len(items)} results")

        if len(items) < 100:
            break

    return all_items


def generate_atom_feed(commits, feed_url):
    """Generate an Atom XML feed from commit data."""
    feed = Element(atom("feed"))

    title = SubElement(feed, atom("title"))
    title.text = "Homebrew New Formulas"

    SubElement(feed, atom("link"), href="https://github.com/Homebrew/homebrew-core", rel="alternate")
    SubElement(feed, atom("link"), href=feed_url, rel="self")

    feed_id = SubElement(feed, atom("id"))
    feed_id.text = feed_url

    subtitle = SubElement(feed, atom("subtitle"))
    subtitle.text = "New formulas added to Homebrew"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    updated = SubElement(feed, atom("updated"))
    updated.text = now

    for commit in commits:
        message = commit["commit"]["message"].split("\n")[0]

        if "(new formula" not in message.lower():
            continue

        match = FORMULA_RE.match(message)
        formula_name = match.group(1) if match else message.split(" ")[0]
        version = match.group(2) if match else ""

        entry = SubElement(feed, atom("entry"))

        entry_title = SubElement(entry, atom("title"))
        entry_title.text = message

        SubElement(entry, atom("link"), href=commit["html_url"], rel="alternate")

        entry_id = SubElement(entry, atom("id"))
        entry_id.text = commit["sha"]

        date_str = commit["commit"]["committer"]["date"]
        entry_updated = SubElement(entry, atom("updated"))
        entry_updated.text = date_str

        author = SubElement(entry, atom("author"))
        author_name = SubElement(author, atom("name"))
        author_name.text = commit["commit"]["author"]["name"]

        brew_url = f"https://formulae.brew.sh/formula/{formula_name}"
        content = SubElement(entry, atom("content"), type="html")
        content.text = (
            f'<p><a href="{brew_url}">{formula_name}</a> {version}</p>'
            f'<p><a href="{commit["html_url"]}">View commit</a></p>'
        )

    return ElementTree(feed)


def main():
    token = os.environ.get("GITHUB_TOKEN")
    feed_url = os.environ.get(
        "FEED_URL",
        "https://aguynamedryan.github.io/homebrew-new-formulas-feed/feed.xml",
    )

    print("Fetching new formula commits from GitHub...")
    commits = fetch_new_formula_commits(token)
    print(f"Found {len(commits)} search results")

    tree = generate_atom_feed(commits, feed_url)

    out_dir = Path("public")
    out_dir.mkdir(exist_ok=True)

    out_path = out_dir / "feed.xml"
    tree.write(str(out_path), encoding="unicode", xml_declaration=True)

    # Count entries
    root = tree.getroot()
    entries = root.findall(atom("entry"))
    print(f"Generated feed with {len(entries)} new formula entries at {out_path}")


if __name__ == "__main__":
    main()
