"""Moodboards and video formats: every entry passes the schema, and the index the dashboard reads is current."""
import json
import unittest

from ev import catalog

MOODBOARDS = ("archival", "blueprint", "clean", "editorial", "flat-vector", "instrument", "math-dark", "whiteboard")
FORMATS = ("compare", "history-lesson", "how-it-works", "incident-review", "problem-fix", "system-tour")


class CatalogTest(unittest.TestCase):
    def test_all_entries_exist(self):
        self.assertEqual(list(MOODBOARDS), catalog.names("moodboard"))
        self.assertEqual(list(FORMATS), catalog.names("video_format"))

    def test_every_moodboard_passes(self):
        for name in MOODBOARDS:
            self.assertEqual([], catalog.problems("moodboard", name), name)

    def test_every_video_format_passes(self):
        for name in FORMATS:
            self.assertEqual([], catalog.problems("video_format", name), name)

    def test_contrast_matches_wcag(self):
        self.assertEqual(21.0, catalog.contrast(catalog.rgb("#000000"), catalog.rgb("#ffffff")))
        self.assertEqual(1.0, catalog.contrast(catalog.rgb("#777777"), catalog.rgb("#777777")))

    def test_rgba_blends_over_the_background(self):
        self.assertEqual((128, 128, 128), catalog.rgb("rgba(0, 0, 0, 0.5)", over="#ffffff"))

    def test_low_contrast_ink_is_refused(self):
        bad = {"colors": {r: "#777777" for r in catalog.COLOR_ROLES}}
        self.assertTrue(any("contrast" in p for p in catalog.mood_problems(bad)))

    def test_old_dark_look_is_math_dark(self):
        self.assertEqual("math-dark", catalog.moodboard("dark")["name"])

    def test_names_must_be_plain_ids(self):
        with self.assertRaises(SystemExit):
            catalog.moodboard("../clean")
        with self.assertRaises(SystemExit):
            catalog.video_format("../compare")

    def test_theme_css_carries_the_moodboard(self):
        css = catalog.theme_css("instrument")
        self.assertIn(f"--bg: {catalog.moodboard('instrument')['colors']['bg']};", css)
        self.assertTrue(css.lstrip("/* ").startswith("moodboard instrument"))

    def test_stage_3d_only_where_3d_fits(self):
        for name in MOODBOARDS:
            mood = catalog.moodboard(name)
            if "stage-3d" in mood["treatments"]:
                self.assertTrue(mood["three"]["fit"], name)

    def test_old_look_keeps_old_motion(self):
        from ev.render import scene_data
        scene = {"id": "a", "beats": []}
        self.assertEqual({}, scene_data({"look": "dark"}, scene, [], 0.35, "landscape")["motion"])
        self.assertEqual(1.0, scene_data({"moodboard": "math-dark"}, scene, [], 0.35, "landscape")["motion"]["duration"])

    def test_committed_index_is_current(self):
        index = catalog.index()
        for folder, key in ((catalog.MOODBOARDS, "moodboards"), (catalog.FORMATS, "video_formats")):
            self.assertEqual(index[key], json.loads((folder / "catalog.json").read_text()), f"run make catalog ({key})")


if __name__ == "__main__":
    unittest.main()
