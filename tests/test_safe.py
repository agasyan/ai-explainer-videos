"""Host-side writes into a project never follow a symlink: ev/safe.py, and the code that uses it."""
import os
import tempfile
import unittest
from pathlib import Path

from ev import intake, safe
from ev import vendor as cdn


class SafeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.video, self.outside = root / "projects" / "20260101-x", root / "outside"
        self.video.mkdir(parents=True)
        self.outside.mkdir()
        (self.outside / "keep.txt").write_text("mine")

    def test_writes_reads_and_makes_folders(self):
        safe.write(self.video, "sources/files/a.md", "one")
        safe.write(self.video, "sources/files/a.md", " two", append=True)
        self.assertEqual(b"one two", safe.read(self.video, "sources/files/a.md"))
        self.assertTrue(safe.is_dir(self.video, "sources/files"))
        safe.remove_tree(self.video, "sources")
        self.assertFalse((self.video / "sources").exists())

    def test_a_symlink_on_the_path_is_refused(self):
        os.symlink(self.outside, self.video / "sources")
        for call in (lambda: safe.write(self.video, "sources/keep.txt", "x"),
                     lambda: safe.read(self.video, "sources/keep.txt"),
                     lambda: safe.mkdirs(self.video, "sources/new"),
                     lambda: safe.remove_tree(self.video, "sources")):
            with self.assertRaises(OSError):
                call()
        self.assertFalse(safe.is_dir(self.video, "sources"))
        self.assertEqual(["keep.txt"], [p.name for p in self.outside.iterdir()])
        self.assertEqual("mine", (self.outside / "keep.txt").read_text())

    def test_a_symlink_as_the_file_is_refused(self):
        os.symlink(self.outside / "keep.txt", self.video / "brief.md")
        with self.assertRaises(OSError):
            safe.write(self.video, "brief.md", "x")
        with self.assertRaises(OSError):
            safe.read(self.video, "brief.md")
        self.assertEqual("mine", (self.outside / "keep.txt").read_text())

    def test_a_symlink_inside_a_removed_folder_is_unlinked_not_followed(self):
        (self.video / "page").mkdir()
        os.symlink(self.outside, self.video / "page" / "link")
        safe.remove_tree(self.video, "page")
        self.assertFalse((self.video / "page").exists())
        self.assertEqual("mine", (self.outside / "keep.txt").read_text())

    def test_dots_and_absolute_paths_are_refused(self):
        for rel in ("../outside/keep.txt", "/etc/hosts", "a/../../outside/keep.txt"):
            with self.assertRaises(OSError, msg=rel):
                safe.write(self.video, rel, "x")

    def test_a_symlinked_video_folder_is_refused(self):
        link = self.video.parent / "20260101-y"
        os.symlink(self.outside, link)
        with self.assertRaises(OSError):
            safe.write(link, "a.txt", "x")
        self.assertFalse((self.outside / "a.txt").exists())

    def test_the_page_copy_refuses_a_planted_symlink(self):
        page = Path(self.tmp.name) / "report.html"
        page.write_text("<p>report</p>")
        (self.video / "assets").mkdir()
        os.symlink(self.outside, self.video / "assets" / "page")  # the project was from-html, then changed
        with self.assertRaises(SystemExit):
            intake.copy(self.video.name, str(page), root=self.video.parent)
        self.assertEqual(["keep.txt"], [p.name for p in self.outside.iterdir()])

    def test_the_cdn_step_refuses_a_page_that_is_a_symlink(self):
        (self.video / "assets" / "page").mkdir(parents=True)
        os.symlink(self.outside / "keep.txt", self.video / "assets" / "page" / "index.html")
        with self.assertRaises(SystemExit):
            cdn.vendor(self.video)
        self.assertEqual("mine", (self.outside / "keep.txt").read_text())


class ModelTest(unittest.TestCase):
    def test_transcribe_takes_only_a_whisper_model_name(self):
        from ev import voice
        for bad in ("../../x", "base.en/../../y", "small?x=1", "", "large-v9"):
            with self.assertRaises(SystemExit, msg=bad):
                voice.transcribe(Path("talk.m4a"), bad)
        for good in ("base.en", "small", "medium.en", "large-v3", "large-v3-turbo"):
            self.assertTrue(voice.MODELS.fullmatch(good), good)


if __name__ == "__main__":
    unittest.main()
