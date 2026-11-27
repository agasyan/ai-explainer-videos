"""Captions and chapters: a line caption is a whole sentence in 1 or 2 lines with one highlighted word, pop
captions keep one short line, and each scene becomes a chapter mark in the MP4."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from ev import render

ROOT = Path(__file__).resolve().parent.parent


def words(text, each=0.4):
    """Timed words, `each` seconds apart, as the voice step writes them."""
    return [{"w": w, "key": False, "start": round(i * each, 3), "end": round(i * each + each - 0.05, 3)}
            for i, w in enumerate(text.split())]


def lines(text, width=42, count=2):
    return [render.cue_text(c) for c in render.cue_lines(words(text), width, count)]


class LineCaptionsTest(unittest.TestCase):
    def test_a_short_sentence_is_one_caption_of_one_line(self):
        cues = render.cue_lines(words("Checkout fails for two percent of users."), 42, 2)
        self.assertEqual(["Checkout fails for two percent of users."], [render.cue_text(c) for c in cues])
        self.assertIsNone(cues[0]["break"])

    def test_each_sentence_gets_its_own_caption(self):
        self.assertEqual(["The cache stores it.", "Does it expire?", "Yes!"],
                         lines("The cache stores it. Does it expire? Yes!"))

    def test_a_longer_sentence_takes_2_near_equal_lines(self):
        cue = render.cue_lines(words("The cache stores the result for five minutes and then drops it."), 42, 2)[0]
        first, second = render.cue_text(cue).split("\n")
        self.assertLessEqual(max(len(first), len(second)), 42)
        self.assertLessEqual(abs(len(first) - len(second)), 12)
        self.assertEqual(first.split()[-1], cue["words"][cue["break"] - 1]["w"])

    def test_a_colon_does_not_end_a_line_caption(self):
        self.assertEqual(["One rule: test the slow path."], lines("One rule: test the slow path."))

    def test_a_sentence_too_long_for_2_lines_breaks_after_a_clause(self):
        got = lines("The cause is a timeout in the payment call, which nobody saw before the release, "
                    "because the test suite never waits that long.")
        self.assertEqual(2, len(got))
        self.assertTrue(got[0].endswith("release,"))
        for caption in got:
            self.assertLessEqual(max(len(line) for line in caption.split("\n")), 42)
            self.assertLessEqual(caption.count("\n"), 1)

    def test_no_caption_is_left_with_fewer_than_3_words_of_a_long_sentence(self):
        got = lines("This sentence has no comma at all and it runs on and on for a long time until the two lines "
                    "are full and more words follow after that point")
        self.assertGreaterEqual(min(len(c.split()) for c in got), 3)

    def test_story_captions_use_narrow_lines(self):
        for caption in lines("However, the cache stores the result for five minutes and every later request reads it.",
                             width=26):
            self.assertLessEqual(max(len(line) for line in caption.split("\n")), 26)

    def test_a_word_longer_than_2_lines_still_shows(self):
        got = render.cue_lines(words("Pneumonoultramicroscopicsilicovolcanoconiosis ok."), 16, 2)
        self.assertEqual(["Pneumonoultramicroscopicsilicovolcanoconiosis", "ok."], [render.cue_text(c) for c in got])
        self.assertIsNone(got[0]["break"])

    def test_a_caption_stays_five_sixths_of_a_second_or_until_the_next_one(self):
        alone = render.cue_lines(words("Yes."), 42, 2)[0]
        self.assertAlmostEqual(5 / 6, alone["end"] - alone["start"], places=3)
        first, second = render.cue_lines(words("Yes. No."), 42, 2)
        self.assertEqual(second["start"], first["end"])

    def test_every_word_keeps_its_time_and_order(self):
        said = words("The cause is a timeout in the payment call, which nobody saw before the release. Yes.")
        self.assertEqual(said, [w for c in render.cue_lines(said, 42, 2) for w in c["words"]])


class PopCaptionsTest(unittest.TestCase):
    def test_pop_keeps_one_short_line_and_breaks_after_a_colon(self):
        cues = render.cue_lines(words("The cause is a timeout in the payment call. Yes: no."), 28, 1)
        self.assertEqual(["The cause is a timeout in", "the payment call.", "Yes:", "no."],
                         [render.cue_text(c) for c in cues])
        self.assertEqual([None] * 4, [c["break"] for c in cues])


class CaptionStyleTest(unittest.TestCase):
    def test_line_is_the_default(self):
        self.assertEqual("line", render.caption_style({}))
        self.assertEqual("line", render.caption_style({"captions": True}))
        self.assertEqual("off", render.caption_style({"captions": False}))
        self.assertEqual("pop", render.caption_style({"captions": "pop"}))

    def test_an_unknown_style_stops(self):
        with self.assertRaises(SystemExit):
            render.caption_style({"captions": "karaoke"})


class CaptionPictureTest(unittest.TestCase):
    """The page itself: the whole sentence is on screen before the voice reaches it, and one word is highlighted."""

    def test_a_line_caption_shows_the_sentence_with_one_highlighted_word(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Playwright runs in the Docker image (make test)")
        said = words("The cache stores the result for five minutes and then drops it.")
        cues = render.cue_lines(said, 42, 2)
        data = {"scene": "verdict-card", "format": "landscape", "look": "clean", "moodboard": None, "motion": {},
                "captions": "line", "width": 1920, "height": 1080, "frames": 180, "duration": 6.0, "cues": cues,
                "beats": [{"id": b, "text": "", "show": "", "start": 2.0 * i, "end": 2.0 * i + 1.6, "until": 2.0 * (i + 1),
                           "words": said if i == 0 else []} for i, b in enumerate("abc")]}
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "captions"
            (video / "scenes").mkdir(parents=True)
            (video / "build").mkdir()
            (video / "build" / "theme.css").write_text("")
            (video / "style.css").write_text("")
            shutil.copy2(ROOT / "templates" / "patterns" / "verdict-card.html", video / "scenes" / "verdict-card.html")
            server = render.serve(video, {"three": False})
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(args=["--font-render-hinting=none"])
                    context = browser.new_context(viewport={"width": 1920, "height": 1080}, service_workers="block")
                    render.guard(context, server.server_address[1], [])
                    page = context.new_page()
                    render.open_scene(page, f"http://127.0.0.1:{server.server_address[1]}/scenes/verdict-card.html", data)
                    page.evaluate("t => EV.seek(t)", said[2]["start"] + 0.1)  # the voice says word 3
                    got = page.evaluate("""() => {
                        const box = document.querySelector(".ev-captions"), safe = document.querySelector(".safe");
                        return {text: [...box.querySelectorAll(".w")].map(w => w.textContent).join(" "),
                                now: [...box.querySelectorAll(".w.now")].map(w => w.textContent),
                                dim: [...box.querySelectorAll(".w:not(.on)")].length,
                                faint: Math.min(...[...box.querySelectorAll(".w")].map(w => +getComputedStyle(w).opacity)),
                                breaks: box.querySelectorAll("br").length,
                                moved: [...box.querySelectorAll(".w")].filter(w => w.style.transform).length,
                                top: box.getBoundingClientRect().top, safe: safe.getBoundingClientRect().bottom};
                    }""")
                    browser.close()
            finally:
                server.shutdown()
        self.assertEqual(" ".join(w["w"] for w in said), got["text"])  # the whole sentence, not only the words said
        self.assertEqual([said[2]["w"]], got["now"])
        self.assertEqual(len(said) - 3, got["dim"])
        self.assertGreaterEqual(got["faint"], 0.75)  # words to come stay easy to read
        self.assertEqual(1, got["breaks"])
        self.assertEqual(0, got["moved"])  # a line caption does not pop
        self.assertGreaterEqual(got["top"], got["safe"])  # 2 lines stay below the content


class ChaptersTest(unittest.TestCase):
    def test_a_chapter_takes_the_scene_title_or_its_id_in_words(self):
        self.assertEqual("Why checkout failed", render.chapter_title({"id": "why", "title": " Why checkout  failed "}))
        self.assertEqual("Hook plan", render.chapter_title({"id": "hook-plan"}))

    def test_the_list_reads_as_minutes_and_seconds(self):
        self.assertEqual("0:00 The answer\n1:05 Why\n", render.chapter_list([(0.0, "The answer"), (65.4, "Why")]))

    def test_the_metadata_has_one_mark_per_chapter_and_escapes_the_title(self):
        meta = render.chapter_meta([(0.0, "Cost = time; twice"), (12.5, "Fix")], 30.0)
        self.assertEqual(2, meta.count("[CHAPTER]"))
        self.assertIn("START=0\nEND=12500\ntitle=Cost \\= time\\; twice\n", meta)
        self.assertIn("START=12500\nEND=30000\ntitle=Fix\n", meta)

    def test_the_mp4_carries_the_chapter_marks(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg runs in the Docker image (make test)")
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "demo"
            video.mkdir()
            clips = []
            for name, color in (("a", "red"), ("b", "blue")):
                clip = video / f"{name}.mp4"
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"color={color}:s=320x180:r=30",
                                "-t", "1", "-pix_fmt", "yuv420p", clip], check=True)
                clips.append(clip)
            cues = [(0.0, 0.9, "First line\nsecond line"), (1.0, 1.9, "Next.")]
            out = render.assemble(video, "demo-landscape-720p", clips, [], cues, 2.0, [(0.0, "The answer"), (1.0, "Why")])
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_chapters", "-of", "csv=p=0", out], check=True,
                                   capture_output=True, text=True).stdout
            self.assertEqual(2, len(probe.strip().splitlines()))
            self.assertIn("The answer", probe)
            self.assertEqual("0:00 The answer\n0:01 Why\n", (video / "out" / "demo-landscape-720p.chapters.txt").read_text())
            self.assertIn("First line\nsecond line", (video / "out" / "demo-landscape-720p.srt").read_text())
            render.assemble(video, "demo-landscape-720p", clips, [], cues, 2.0, [(0.0, "Only")])  # one scene: no marks
            self.assertFalse((video / "out" / "demo-landscape-720p.chapters.txt").exists())


if __name__ == "__main__":
    unittest.main()
