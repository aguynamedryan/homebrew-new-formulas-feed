# Homebrew New Formulas Feed

An Atom feed of new formulas added to [Homebrew](https://brew.sh/).

**Subscribe:** [`https://aguynamedryan.github.io/homebrew-new-formulas-feed/feed.xml`](https://aguynamedryan.github.io/homebrew-new-formulas-feed/feed.xml)

Add that URL to any RSS/Atom reader (Feedly, FreshRSS, NetNewsWire, Vienna, etc.) to get notified when new formulas land in homebrew-core.

## Why?

Homebrew's [homebrew-core](https://github.com/Homebrew/homebrew-core) repo has hundreds of commits per day (version bumps, bottle updates, merge commits). The GitHub commits atom feed only shows the last 20 entries, so new formula additions get buried almost immediately.

This project uses GitHub's commit search API to find all commits with `(new formula)` in the message and generates a clean Atom feed from them, updated every 4 hours via GitHub Actions and served on GitHub Pages.

## How it works

1. A GitHub Action runs on a schedule (every 4 hours) and on manual trigger
2. `generate_feed.py` queries the GitHub commit search API for `"new formula"` commits in homebrew-core
3. It filters to only include commits where the first line matches `formulaname X.Y.Z (new formula)`
4. The resulting Atom feed is deployed to GitHub Pages

Each feed entry includes:
- The formula name and version
- A link to the [formulae.brew.sh](https://formulae.brew.sh/) page
- A link to the commit on GitHub
