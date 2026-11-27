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

    def test_a_link_that_was_not_opened_is_not_a_source(self):
        self.path.write_text(TABLE + "| c4 | A study | [A](https://a.example/x) | https://b.example/y (not opened: 403) | |\n")
        row = research.rows(self.path)[-1]
        self.assertEqual(["https://a.example/x"], row["links"])
        self.assertEqual("one source", row["status"])

    def test_summary_counts_sources(self):
        self.assertEqual({"claims": 3, "one_source": 1, "no_source": 1, "conflict": 0}, research.summary(self.path))

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

    def test_a_number_with_no_research_file_is_one_check(self):
        missing = Path(self.tmp.name) / "none.md"
        issues = research.checks(spec({"id": "b1", "say": "In 1914."}, {"id": "b2", "say": "Up nineteen percent."}), missing)
        self.assertEqual(1, len(issues))
        self.assertTrue(issues[0].startswith("research.md is missing, and 2 beats state a number (hook/b1, hook/b2)"))
        self.assertEqual([], research.checks(spec({"id": "b1", "say": "Hello there."}), missing))

    def test_a_project_file_counts_as_a_source(self):
        self.path.write_text(TABLE
                             + "| c4 | Each refresh brings only new fares | page s05 (`sources/page.md`) | `src/poll/Search.java:L40-L52` | |\n"
                             + "| c5 | The cost is 16K a month | page s03 (`sources/page.md`) | - | one source (the page) |\n"
                             + "| c6 | Same page twice | `sources/page.md` | `sources/page.md:L9` | |\n")
        c4, c5, c6 = research.rows(self.path)[-3:]
        self.assertEqual(("two sources", ["sources/page.md", "src/poll/Search.java"]), (c4["status"], c4["files"]))
        self.assertEqual("one source", c5["status"])
        self.assertEqual("one source", c6["status"])  # one file named twice is one source

    def test_a_conflict_blocks_the_beat_that_cites_it(self):
        self.path.write_text(TABLE + "| c4 | 16K a month | `sources/page.md` | `cost/model.py:L12` | conflict: the code says 12K |\n")
        self.assertEqual("conflict", research.rows(self.path)[-1]["status"])
        self.assertEqual(1, research.summary(self.path)["conflict"])
        issues = research.checks(spec({"id": "b1", "say": "It costs 16 thousand.", "sources": ["c4"]}), self.path)
        self.assertEqual(["hook/b1 cites c4, where the sources disagree: settle it with the user, or leave it out"], issues)
