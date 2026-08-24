import unittest

from generate_feed import ATOM_NS, generate_atom_feed


def atom(tag):
    return f"{{{ATOM_NS}}}{tag}"


COMMIT = {
    "html_url": "https://github.com/Homebrew/homebrew-core/commit/abc123",
    "sha": "abc123",
    "commit": {
        "message": "widget 1.2.3 (new formula)",
        "committer": {"date": "2026-08-24T12:00:00Z"},
        "author": {"name": "Homebrew"},
    },
}


class GenerateAtomFeedTests(unittest.TestCase):
    def entry_link(self, homepages):
        tree = generate_atom_feed(
            "formula",
            [COMMIT],
            "https://example.test/formulas.xml",
            homepages=homepages,
        )
        entry = tree.getroot().find(atom("entry"))
        return entry.find(atom("link")).attrib["href"]

    def test_entry_primary_link_uses_project_homepage(self):
        self.assertEqual(
            self.entry_link({"widget": "https://widget.example/"}),
            "https://widget.example/",
        )

    def test_entry_primary_link_falls_back_to_homebrew_page(self):
        self.assertEqual(
            self.entry_link({}),
            "https://formulae.brew.sh/formula/widget",
        )


if __name__ == "__main__":
    unittest.main()
