"""ev new: a project from the template or from a sample, into projects/<YYYYMMDD>-<name>/."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ev import cli, projects

SCRIPT = "title: Demo\nformat: landscape\nscenes:\n  - id: hook\n    beats:\n      - id: hook\n        say: Hi.\n"


class NewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.saved = projects.PROJECTS, projects.OLD, cli.SAMPLES
        projects.PROJECTS, projects.OLD, cli.SAMPLES = root / "projects", root / "generated_videos", root / "samples"
        self.env = mock.patch.dict(os.environ, {"EV_TODAY": "20261118"})
        self.env.start()
        self.sample = cli.SAMPLES / "demo"
        (self.sample / "scenes").mkdir(parents=True)
        (self.sample / "script.yaml").write_text(SCRIPT)
        (self.sample / "scenes" / "hook.html").write_text("<p>hook</p>")
        self.made = projects.PROJECTS / "20261118-x"

    def tearDown(self):
        self.env.stop()
        projects.PROJECTS, projects.OLD, cli.SAMPLES = self.saved
        self.tmp.cleanup()

    def test_sample_copies_its_sources_into_a_dated_project(self):
        cli.new("x", "T", sample="demo")
        self.assertEqual(SCRIPT, (self.made / "script.yaml").read_text())
        self.assertTrue((self.made / "scenes" / "hook.html").is_file())

    def test_sample_never_copies_build_out_or_approvals(self):
        for name in ("build/narration.json", "out/demo.mp4", "approved.json", "Approved.json"):
            (self.sample / name).parent.mkdir(parents=True, exist_ok=True)
            (self.sample / name).write_text("x")
        cli.new("x", "T", sample="demo")
        copied = sorted(str(p.relative_to(self.made)) for p in self.made.rglob("*") if p.is_file())
        self.assertEqual(["scenes/hook.html", "script.yaml"], copied)

    def test_sample_with_a_symlink_is_refused(self):
        os.symlink("/etc/hostname", self.sample / "scenes" / "link.html")
        with self.assertRaises(SystemExit) as stop:
            cli.new("x", "T", sample="demo")
        self.assertIn("symlink", str(stop.exception.code))

    def test_sample_name_must_be_a_plain_id(self):
        with self.assertRaises(SystemExit):
            cli.new("x", "T", sample="../demo")

    def test_a_second_start_the_same_day_is_a_new_project(self):
        cli.new("x", "T", sample="demo")
        cli.new("x", "T", sample="demo")
        self.assertEqual(["20261118-x", "20261118-x-2"], sorted(p.name for p in projects.PROJECTS.iterdir()))
        self.assertEqual(projects.PROJECTS / "20261118-x-2", cli.video("x"))  # a name finds its newest project

    def test_an_existing_project_id_is_refused(self):
        cli.new("x", "T", sample="demo")
        with self.assertRaises(SystemExit) as stop:
            cli.new("20261118-x", "T", sample="demo")
        self.assertIn("already exists", str(stop.exception.code))

    def test_an_older_video_keeps_working_where_it_is(self):
        (projects.OLD / "dns").mkdir(parents=True)
        self.assertEqual(projects.OLD / "dns", cli.video("dns"))
        with self.assertRaises(SystemExit):
            cli.video("../dns")


class ProjectsTest(unittest.TestCase):
    def test_ids_names_and_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            new, old = Path(tmp) / "projects", Path(tmp) / "generated_videos"
            with mock.patch.dict(os.environ, {"EV_TODAY": "20261118"}):
                self.assertEqual("20261118-dns", projects.new_id("dns", new, old))
                (new / "20261117-dns").mkdir(parents=True)
                (new / "20261118-dns").mkdir()
                self.assertEqual("20261118-dns-2", projects.new_id("dns", new, old))
                (new / "20261118-dns-2").mkdir()
                (new / "20261118-dnssec").mkdir()
                self.assertEqual("20261118-dns-2", projects.find("dns", new, old).name)
                self.assertEqual("20261117-dns", projects.find("20261117-dns", new, old).name)
                self.assertIsNone(projects.find("web", new, old))
                self.assertEqual("20261119-web", projects.new_id("20261119-web", new, old))  # an id is kept
            with mock.patch.dict(os.environ, {"EV_TODAY": "not a date"}):
                self.assertRegex(projects.new_id("web", new, old), r"^\d{8}-web$")
            for bad in ("../x", "X", "", "a/b", "-x"):
                with self.assertRaises(SystemExit):
                    projects.new_id(bad, new, old)


if __name__ == "__main__":
    unittest.main()
