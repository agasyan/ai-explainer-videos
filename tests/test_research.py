"""research.md: claims, their sources, and the narrate checks."""
import tempfile
import unittest
from pathlib import Path

from ev import research

TABLE = """# Research
| id | claim | source 1 | source 2 | status |
|----|-------|----------|----------|--------|
| c1 | Sperry flew hands-off in 1914 | [NASM](https://airandspace.si.edu/x) | [FAA](https://www.faa.gov/y) | two sources |
| c2 | Bainbridge, 1983 | [Crossref](https://api.crossref.org/z) | | one source |
| c3 | A guess | | | no source |
"""


def spec(*beats):
    return {"parts": [{"scenes": [{"id": "hook", "beats": list(beats)}]}]}


class ResearchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "research.md"
        self.path.write_text(TABLE)

    def tearDown(self):
        self.tmp.cleanup()

    def test_summary_counts_sources(self):
        self.assertEqual({"claims": 3, "one_source": 1, "no_source": 1}, research.summary(self.path))

    def test_unknown_source_id(self):
        issues = research.checks(spec({"id": "b1", "say": "Hello.", "sources": ["c9"]}), self.path)
        self.assertEqual(["hook/b1 cites c9, which research.md lacks"], issues)

    def test_number_without_a_source(self):
        issues = research.checks(spec({"id": "b1", "say": "It flew in 1914."}), self.path)
        self.assertEqual(["hook/b1 has a number and no source: add sources: [c<n>] from research.md"], issues)

    def test_spelled_number_without_a_source(self):
        self.assertTrue(research.checks(spec({"id": "b1", "say": "Slower by nineteen percent."}), self.path))

    def test_cited_number_and_small_words_pass(self):
        self.assertEqual([], research.checks(spec({"id": "b1", "say": "In 1914 he flew.", "sources": ["c1"]},
                                                  {"id": "b2", "say": "If one zone fails, search stops."}), self.path))

    def test_no_research_file_means_no_checks(self):
        self.assertEqual([], research.checks(spec({"id": "b1", "say": "In 1914."}), Path(self.tmp.name) / "none.md"))
