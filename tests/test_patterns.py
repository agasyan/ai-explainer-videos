"""templates/patterns/: every starter scene loads with no JS error, and passes the layout lint on each beat's frame."""
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = sorted((ROOT / "templates" / "patterns").glob("*.html"))


def data(scene):
    """EV_DATA for 3 beats (a, b, c) of 2 s each, as scene_data() writes it."""
    beats = [{"id": b, "text": "", "show": "", "start": 2.0 * i, "end": 2.0 * i + 1.6, "until": 2.0 * (i + 1),
              "words": []} for i, b in enumerate("abc")]
    return {"scene": scene, "format": "landscape", "look": "clean", "moodboard": None, "motion": {}, "captions": "off",
            "width": 1920, "height": 1080, "frames": 180, "duration": 6.0, "beats": beats, "cues": []}


class PatternsTest(unittest.TestCase):
    def test_every_pattern_renders_and_passes_lint(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Playwright runs in the Docker image (make test)")
        from PIL import Image

        from ev.render import WEBGL, guard, open_scene, serve
        self.assertGreaterEqual(len(PATTERNS), 12)
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "patterns"
            (video / "scenes").mkdir(parents=True)
            (video / "build").mkdir()
            (video / "build" / "theme.css").write_text("")
            (video / "style.css").write_text("")
            shot = video / "assets" / "page" / "shots" / "landscape"
            shot.mkdir(parents=True)
            Image.new("RGB", (2400, 1400), "white").save(shot / "s01.png")  # the zoom pattern's page capture, at 2x
            for path in PATTERNS:
                shutil.copy2(path, video / "scenes" / path.name)
            server = serve(video, {"three": True})
            problems = {}
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(args=["--font-render-hinting=none", *WEBGL])
                    for path in PATTERNS:
                        context = browser.new_context(viewport={"width": 1920, "height": 1080}, service_workers="block")
                        blocked = []
                        guard(context, server.server_address[1], blocked)
                        page = context.new_page()
                        url = f"http://127.0.0.1:{server.server_address[1]}/scenes/{path.name}"
                        try:
                            open_scene(page, url, data(path.stem))
                            found = []
                            for t in (1.9, 3.9, 5.9):  # the frame before each next beat, as the render lints it
                                page.evaluate("t => EV.seek(t)", t)
                                found += page.evaluate("EV.lint()")
                            found += page.evaluate("EV.warnings") + [f"blocked {u}" for u in blocked]
                        except SystemExit as e:
                            found = [str(e)]
                        if found:
                            problems[path.name] = found
                        context.close()
                    browser.close()
            finally:
                server.shutdown()
        self.assertEqual({}, problems)


if __name__ == "__main__":
    unittest.main()
