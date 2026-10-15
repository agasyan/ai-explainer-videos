"""ev new: a video from the template or from a sample, into generated_videos/."""
import os
import tempfile
import unittest
from pathlib import Path

from ev import cli

SCRIPT = "title: Demo\nformat: landscape\nscenes:\n  - id: hook\n    beats:\n      - id: hook\n        say: Hi.\n"


class NewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.saved = cli.VIDEOS, cli.SAMPLES
        cli.VIDEOS, cli.SAMPLES = root / "generated_videos", root / "samples"
        self.sample = cli.SAMPLES / "demo"
        (self.sample / "scenes").mkdir(parents=True)
        (self.sample / "script.yaml").write_text(SCRIPT)
        (self.sample / "scenes" / "hook.html").write_text("<p>hook</p>")

    def tearDown(self):
        cli.VIDEOS, cli.SAMPLES = self.saved
        self.tmp.cleanup()

    def test_sample_copies_its_sources(self):
        cli.new("x", "T", sample="demo")
        self.assertEqual(SCRIPT, (cli.VIDEOS / "x" / "script.yaml").read_text())
        self.assertTrue((cli.VIDEOS / "x" / "scenes" / "hook.html").is_file())

    def test_sample_never_copies_build_out_or_approvals(self):
        for name in ("build/narration.json", "out/demo.mp4", "approved.json", "Approved.json"):
            (self.sample / name).parent.mkdir(parents=True, exist_ok=True)
            (self.sample / name).write_text("x")
        cli.new("x", "T", sample="demo")
        copied = sorted(str(p.relative_to(cli.VIDEOS / "x")) for p in (cli.VIDEOS / "x").rglob("*") if p.is_file())
        self.assertEqual(["scenes/hook.html", "script.yaml"], copied)

    def test_sample_with_a_symlink_is_refused(self):
        os.symlink("/etc/hostname", self.sample / "scenes" / "link.html")
        with self.assertRaises(SystemExit) as stop:
            cli.new("x", "T", sample="demo")
        self.assertIn("symlink", str(stop.exception.code))

    def test_sample_name_must_be_a_plain_id(self):
        with self.assertRaises(SystemExit):
            cli.new("x", "T", sample="../demo")

    def test_existing_target_is_refused(self):
        (cli.VIDEOS / "x").mkdir(parents=True)
        with self.assertRaises(SystemExit) as stop:
            cli.new("x", "T", sample="demo")
        self.assertIn("already exists", str(stop.exception.code))


    def test_a_consent_folder_keeps_only_the_consent(self):
        import json
        (cli.VIDEOS / "x").mkdir(parents=True)
        (cli.VIDEOS / "x" / "approved.json").write_text(json.dumps({"auto": {"until": "preview", "by": "t", "at": "now"},
                                                                    "plan": {"hash": "forged"}}))
        cli.new("x", "T", sample="demo")
        self.assertEqual(["auto"], list(json.loads((cli.VIDEOS / "x" / "approved.json").read_text())))
        self.assertTrue((cli.VIDEOS / "x" / "script.yaml").is_file())


if __name__ == "__main__":
    unittest.main()
