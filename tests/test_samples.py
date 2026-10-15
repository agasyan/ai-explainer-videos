"""make sample: publish only an approved video, sources and frames only."""
import json
import tempfile
import unittest
from pathlib import Path

from ev import gates, samples

SCRIPT = 'title: "Autopilot"\nformat: landscape   # aspect\nthree: true\nscenes:\n  - id: hook\n    beats:\n      - id: hook\n        say: Hi.\n'


class PublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.saved = samples.LOCAL, samples.SAMPLES
        samples.LOCAL, samples.SAMPLES = root / "generated_videos", root / "samples"
        self.video = samples.LOCAL / "auto"
        for name, text in (("script.yaml", SCRIPT), ("scenes/hook.html", "<p></p>"), ("storyboard.md", "# s"),
                           ("frames/landscape/hook/hook.jpg", "jpg"), ("build/narration.json", "{}")):
            (self.video / name).parent.mkdir(parents=True, exist_ok=True)
            (self.video / name).write_text(text)

    def tearDown(self):
        samples.LOCAL, samples.SAMPLES = self.saved
        self.tmp.cleanup()

    def approve_preview(self):
        (self.video / "approved.json").write_text(json.dumps(
            {"preview": {"hash": gates.fingerprint(self.video, "preview"), "formats": ["landscape"]}}))

    def test_field_reads_top_level_values(self):
        self.assertEqual("Autopilot", samples.field(SCRIPT, "title"))
        self.assertEqual("landscape", samples.field(SCRIPT, "format"))
        self.assertEqual("", samples.field(SCRIPT, "look"))

    def test_unapproved_video_is_refused(self):
        with self.assertRaises(SystemExit) as stop:
            samples.publish("auto")
        self.assertIn("Approve the preview", str(stop.exception.code))

    def test_publish_copies_sources_and_frames_only(self):
        self.approve_preview()
        samples.publish("auto")
        dst = samples.SAMPLES / "auto"
        files = sorted(str(p.relative_to(dst)) for p in dst.rglob("*") if p.is_file())
        self.assertEqual(["frames/landscape/hook/hook.jpg", "sample.json", "scenes/hook.html", "script.yaml",
                          "storyboard.md"], files)
        info = json.loads((dst / "sample.json").read_text())
        self.assertEqual(("Autopilot", "landscape", True), (info["title"], info["format"], info["three"]))

    def test_a_file_swapped_for_a_symlink_after_the_scan_is_refused(self):
        """The race: the scan passes, then a source file becomes a link to a secret before the copy."""
        import os
        secret = Path(self.tmp.name) / "secret.txt"
        secret.write_text("private key")
        real_walk = samples.os.walk

        def walk_then_swap(top, *args, **kw):
            yield from real_walk(top, *args, **kw)
            target = self.video / "scenes" / "hook.html"
            target.unlink()
            os.symlink(secret, target)

        samples.os.walk = walk_then_swap
        try:
            with self.assertRaises(SystemExit):
                samples.copy_sources(self.video, Path(self.tmp.name) / "out", samples.SOURCES)
        finally:
            samples.os.walk = real_walk
        copied = Path(self.tmp.name) / "out" / "scenes" / "hook.html"
        self.assertFalse(copied.exists() and copied.read_text() == "private key")

    def test_slug_must_be_a_plain_id(self):
        with self.assertRaises(SystemExit):
            samples.publish("../x")


if __name__ == "__main__":
    unittest.main()
