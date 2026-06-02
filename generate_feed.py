#!/usr/bin/env python3
"""Fetch new Homebrew formulas and casks and generate Atom feeds for GitHub Pages."""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree, register_namespace

ATOM_NS = "http://www.w3.org/2005/Atom"
register_namespace("", ATOM_NS)

GITHUB_API = "https://api.github.com"

KINDS = {
    "formula": {
        "repo": "Homebrew/homebrew-core",
        "search_phrase": "new formula",
        # Match: "formulaname 1.2.3 (new formula)" or "formulaname 1.2.3 (new formulae)"
        "commit_regex": re.compile(r"^(.+?)\s+([\d][^\s]*)\s+\(new\s+formula", re.IGNORECASE),
        "api_url": "https://formulae.brew.sh/api/formula.json",
        "page_url_template": "https://formulae.brew.sh/formula/{name}",
        "feed_title": "Homebrew New Formulas",
        "feed_subtitle": "New formulas added to Homebrew",
        "feed_filename": "formulas.xml",
        "metadata_key": "name",
        "alt_link": "https://github.com/Homebrew/homebrew-core",
        "label": "formula",
    },
    "cask": {
        "repo": "Homebrew/homebrew-cask",
        "search_phrase": "new cask",
        # Match: "casktoken 1.2.3 (new cask)"
        "commit_regex": re.compile(r"^(.+?)\s+([\d][^\s]*)\s+\(new\s+cask", re.IGNORECASE),
        "api_url": "https://formulae.brew.sh/api/cask.json",
        "page_url_template": "https://formulae.brew.sh/cask/{name}",
        "feed_title": "Homebrew New Casks",
        "feed_subtitle": "New casks added to Homebrew",
        "feed_filename": "casks.xml",
        "metadata_key": "token",
        "alt_link": "https://github.com/Homebrew/homebrew-cask",
        "label": "cask",
    },
}


def atom(tag):
    return f"{{{ATOM_NS}}}{tag}"


def _rate_limit_delay(http_error, attempt):
    """Seconds to wait before retrying a rate-limited GitHub request.

    Prefer the server's own guidance (Retry-After, or X-RateLimit-Reset when the
    primary quota is exhausted); otherwise back off exponentially. Capped so a
    single throttled page can't stall the run for long.
    """
    headers = http_error.headers
    retry_after = headers.get("Retry-After")
    if retry_after and retry_after.strip().isdigit():
        return min(int(retry_after), 60)
    if headers.get("X-RateLimit-Remaining") == "0":
        reset = headers.get("X-RateLimit-Reset")
        if reset and reset.strip().isdigit():
            return max(1, min(int(reset) - int(time.time()), 60))
    return min(5 * 2 ** attempt, 60)  # 5, 10, 20, 40, 60...


def _request_json(url, token=None, accept="application/vnd.github+json", max_retries=4):
    """GET `url` and parse JSON, retrying GitHub's rate-limit responses.

    The search API enforces an aggressive secondary (abuse) rate limit that
    returns 403 on bursts even while the primary quota is intact, so we retry
    403/429 responses with backoff rather than letting one throttled request
    abort the whole feed build. Other HTTP errors propagate immediately.
    """
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url)
        req.add_header("Accept", accept)
        req.add_header("User-Agent", "homebrew-new-formulas-feed")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code not in (403, 429) or attempt == max_retries:
                raise
            delay = _rate_limit_delay(exc, attempt)
            print(
                f"  Rate limited (HTTP {exc.code}); retrying in {delay}s "
                f"(attempt {attempt + 1}/{max_retries})"
            )
            time.sleep(delay)


def fetch_new_commits(kind, token=None, max_pages=3):
    """Search for commits containing the 'new formula' / 'new cask' marker in the relevant repo.

    Paginates through results because the search also matches merge commits
    that mention the phrase in the body, pushing actual new-item commits
    further down the result list.
    """
    config = KINDS[kind]
    search_query = f'repo:{config["repo"]} "{config["search_phrase"]}"'
    all_items = []
    for page in range(1, max_pages + 1):
        params = urllib.parse.urlencode({
            "q": search_query,
            "sort": "committer-date",
            "order": "desc",
            "per_page": 100,
            "page": page,
        })
        url = f"{GITHUB_API}/search/commits?{params}"

        try:
            data = _request_json(url, token)
        except urllib.error.HTTPError as exc:
            # Retries on this page are exhausted. If earlier pages already
            # returned results, proceed with those instead of failing the whole
            # run. If even page 1 fails, re-raise so the job fails loudly and
            # GitHub Pages keeps the last good feed (better than an empty one).
            if all_items:
                print(
                    f"  Page {page}: HTTP {exc.code} after retries; continuing "
                    f"with {len(all_items)} results from earlier pages"
                )
                break
            raise

        items = data.get("items", [])
        all_items.extend(items)
        print(f"  Page {page}: {len(items)} results")

        if len(items) < 100:
            break

        # Sleep between pages to stay under GitHub's search API secondary
        # rate limit, which throttles bursts more aggressively than the
        # documented 30 req/min authenticated limit.
        if page < max_pages:
            time.sleep(2)

    return all_items


def fetch_metadata(kind):
    """Fetch descriptions and homepages from the bulk Homebrew API for the given kind."""
    config = KINDS[kind]
    key_field = config["metadata_key"]
    url = config["api_url"]
    print(f"  Fetching {url} ...")
    data = _request_json(url, accept="application/json")
    descriptions = {}
    homepages = {}
    for item in data:
        name = item.get(key_field)
        if not name:
            continue
        desc = item.get("desc")
        homepage = item.get("homepage")
        if desc:
            descriptions[name] = desc
        if homepage:
            homepages[name] = homepage
    print(f"  Loaded metadata for {len(descriptions)} {config['label']}s")
    return descriptions, homepages


def generate_atom_feed(kind, commits, feed_url, descriptions=None, homepages=None):
    """Generate an Atom XML feed from commit data for the given kind."""
    config = KINDS[kind]
    descriptions = descriptions or {}
    homepages = homepages or {}
    feed = Element(atom("feed"))

    title = SubElement(feed, atom("title"))
    title.text = config["feed_title"]

    SubElement(feed, atom("link"), href=config["alt_link"], rel="alternate")
    SubElement(feed, atom("link"), href=feed_url, rel="self")

    feed_id = SubElement(feed, atom("id"))
    feed_id.text = feed_url

    subtitle = SubElement(feed, atom("subtitle"))
    subtitle.text = config["feed_subtitle"]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    updated = SubElement(feed, atom("updated"))
    updated.text = now

    marker = f"({config['search_phrase']}"

    for commit in commits:
        message = commit["commit"]["message"].split("\n")[0]

        if marker not in message.lower():
            continue

        match = config["commit_regex"].match(message)
        name = match.group(1) if match else message.split(" ")[0]
        version = match.group(2) if match else ""

        entry = SubElement(feed, atom("entry"))

        entry_title = SubElement(entry, atom("title"))
        desc = descriptions.get(name)
        if desc:
            entry_title.text = f"{name}: {desc}"
        else:
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

        page_url = config["page_url_template"].format(name=name)
        homepage = homepages.get(name)
        content = SubElement(entry, atom("content"), type="html")
        desc_html = f"<p><em>{desc}</em></p>" if desc else ""
        homepage_html = f'<p><a href="{homepage}">Homepage</a></p>' if homepage else ""
        content.text = (
            f'<p><a href="{page_url}">{name}</a> {version}</p>'
            f'{desc_html}'
            f'{homepage_html}'
            f'<p><a href="{commit["html_url"]}">View commit</a></p>'
        )

    return ElementTree(feed)


# Stable identifiers for the legacy feed.xml redirect notice. These MUST NOT
# change across runs — feed readers dedupe on id, and a drifting updated
# timestamp would cause the notice to re-appear on every 4-hour regen.
MOVED_NOTICE_ID = "urn:homebrew-new-formulas-feed:feed-moved:2026-04-09"
MOVED_NOTICE_DATE = "2026-04-09T00:00:00Z"


def write_moved_notice(base_url, out_dir):
    """Write a minimal Atom feed at feed.xml telling subscribers the feed moved.

    The legacy URL was feed.xml before the rename to formulas.xml. Existing
    feed-reader subscriptions still point there, so we keep a one-entry stub
    at that URL to nudge subscribers to the new location.
    """
    new_url = base_url + "formulas.xml"
    casks_url = base_url + "casks.xml"
    old_url = base_url + "feed.xml"

    feed = Element(atom("feed"))

    title = SubElement(feed, atom("title"))
    title.text = "Homebrew New Formulas (moved)"

    SubElement(feed, atom("link"), href=new_url, rel="alternate")
    SubElement(feed, atom("link"), href=old_url, rel="self")

    feed_id = SubElement(feed, atom("id"))
    feed_id.text = old_url

    subtitle = SubElement(feed, atom("subtitle"))
    subtitle.text = f"This feed has moved to {new_url}"

    updated = SubElement(feed, atom("updated"))
    updated.text = MOVED_NOTICE_DATE

    entry = SubElement(feed, atom("entry"))

    entry_title = SubElement(entry, atom("title"))
    entry_title.text = "This feed has moved — please update your subscription"

    SubElement(entry, atom("link"), href=new_url, rel="alternate")

    entry_id = SubElement(entry, atom("id"))
    entry_id.text = MOVED_NOTICE_ID

    entry_updated = SubElement(entry, atom("updated"))
    entry_updated.text = MOVED_NOTICE_DATE

    author = SubElement(entry, atom("author"))
    author_name = SubElement(author, atom("name"))
    author_name.text = "Homebrew New Formulas Feed"

    content = SubElement(entry, atom("content"), type="html")
    content.text = (
        f"<p>The Homebrew new formulas feed has moved to a new URL:</p>"
        f'<p><a href="{new_url}">{new_url}</a></p>'
        f"<p>Please update your feed reader subscription. There is also a "
        f'separate feed for new casks at <a href="{casks_url}">{casks_url}</a>.</p>'
    )

    tree = ElementTree(feed)
    out_path = out_dir / "feed.xml"
    tree.write(str(out_path), encoding="unicode", xml_declaration=True)
    print(f"Wrote redirect notice feed at {out_path}")


def build_feed(kind, base_url, token, out_dir):
    config = KINDS[kind]
    feed_url = base_url + config["feed_filename"]

    print(f"Fetching new {config['label']} commits from GitHub...")
    commits = fetch_new_commits(kind, token)
    print(f"Found {len(commits)} search results")

    print(f"Fetching {config['label']} metadata...")
    descriptions, homepages = fetch_metadata(kind)

    tree = generate_atom_feed(kind, commits, feed_url, descriptions, homepages)

    out_path = out_dir / config["feed_filename"]
    tree.write(str(out_path), encoding="unicode", xml_declaration=True)

    root = tree.getroot()
    entries = root.findall(atom("entry"))
    print(f"Generated feed with {len(entries)} new {config['label']} entries at {out_path}")


def main():
    token = os.environ.get("GITHUB_TOKEN")
    base_url = os.environ.get(
        "BASE_URL",
        "https://aguynamedryan.github.io/homebrew-new-formulas-feed/",
    )
    if not base_url.endswith("/"):
        base_url += "/"

    out_dir = Path("public")
    out_dir.mkdir(exist_ok=True)

    for kind in KINDS:
        build_feed(kind, base_url, token, out_dir)

    write_moved_notice(base_url, out_dir)


if __name__ == "__main__":
    main()
