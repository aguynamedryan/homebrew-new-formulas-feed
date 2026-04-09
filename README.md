# Homebrew New Formulas Feed

Atom feeds of new formulas and casks added to [Homebrew](https://brew.sh/).

**Subscribe:**
- Formulas: [`https://aguynamedryan.github.io/homebrew-new-formulas-feed/formulas.xml`](https://aguynamedryan.github.io/homebrew-new-formulas-feed/formulas.xml)
- Casks: [`https://aguynamedryan.github.io/homebrew-new-formulas-feed/casks.xml`](https://aguynamedryan.github.io/homebrew-new-formulas-feed/casks.xml)

Add either URL to any RSS/Atom reader (Feedly, FreshRSS, NetNewsWire, Vienna, etc.) to get notified when new formulas or casks land.

## Why?

Homebrew's [homebrew-core](https://github.com/Homebrew/homebrew-core) and [homebrew-cask](https://github.com/Homebrew/homebrew-cask) repos have hundreds of commits per day (version bumps, bottle updates, merge commits). The GitHub commits atom feed only shows the last 20 entries, so new formula and cask additions get buried almost immediately.

This project uses GitHub's commit search API to find all commits with `(new formula)` or `(new cask)` in the message and generates clean Atom feeds from them, updated every 4 hours via GitHub Actions and served on GitHub Pages.

## How it works

1. A GitHub Action runs on a schedule (every 4 hours) and on manual trigger
2. `generate_feed.py` queries the GitHub commit search API for `"new formula"` commits in homebrew-core and `"new cask"` commits in homebrew-cask
3. It filters to only include commits where the first line matches `name X.Y.Z (new formula)` or `name X.Y.Z (new cask)`
4. The resulting Atom feeds are deployed to GitHub Pages

Each feed entry includes:
- The formula/cask name and version
- A link to the [formulae.brew.sh](https://formulae.brew.sh/) page
- A link to the commit on GitHub
