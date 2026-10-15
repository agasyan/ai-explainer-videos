"""three.js: used only where allowed, with a reason, 2 per part at most; frames repeat exactly; renders stay local."""
import tempfile
import threading
import unittest
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

from ev import catalog, storyboard
from ev.common import VENDOR
from ev.render import Files, guard, three_checks, three_selftest

THREE_PAGE = '<script type="importmap">{"imports": {"three": "/vendor/three/build/three.module.js"}}</script>' \
             '<script type="module">import * as THREE from "three"; EV.ready();</script>'
FLAT_PAGE = "<script>EV.ready();</script>"


def spec(three=True, why=True, n=1):
    scenes = [{"id": f"s{i}", "treatment": "stage-3d", "beats": [{"id": "b", "say": "Hi.", "show": "x"}],
               **({"three_why": "rotation is the idea"} if why else {})} for i in range(n)]
    return {"three": three, "moodboard": "instrument", "parts": [{"title": "One", "scenes": scenes}]}


class ThreeRulesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.video = Path(self.tmp.name)
        (self.video / "scenes").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def page(self, html, sid="s0"):
        (self.video / "scenes" / f"{sid}.html").write_text(html)

    def test_three_off_and_a_scene_that_loads_it_stops(self):
        self.page(THREE_PAGE)
        with self.assertRaisesRegex(SystemExit, "three.js is off for this video"):
            three_checks(self.video, spec(three=False), "playwright")

    def test_three_on_without_a_reason_stops(self):
        self.page(THREE_PAGE)
        with self.assertRaisesRegex(SystemExit, "add three_why for scene s0"):
            three_checks(self.video, spec(why=False), "playwright")

    def test_three_with_hyperframes_stops(self):
        self.page(THREE_PAGE)
        with self.assertRaises(SystemExit):
            three_checks(self.video, spec(), "hyperframes")

    def test_a_2d_scene_needs_nothing(self):
        self.page(FLAT_PAGE)
        three_checks(self.video, spec(three=False, why=False), "hyperframes")

    def test_vendor_three_is_not_served_when_off(self):
        off = Files.translate_path(type("F", (), {"video": self.video, "three": False})(), "/vendor/three/build/three.module.js")
        on = Files.translate_path(type("F", (), {"video": self.video, "three": True})(), "/vendor/three/build/three.module.js")
        self.assertFalse(Path(off).exists())
        self.assertTrue(on.endswith("three/build/three.module.js"))


class ThreeStoryboardTest(unittest.TestCase):
    def board(self, s):
        narration = {"source": "x", "gap": 0.3, "scenes": {sc["id"]: [{"id": "b", "text": "Hi.", "duration": 1.0}]
                                                           for sc in s["parts"][0]["scenes"]}}
        known = {"video_format": catalog.names("video_format"), "moodboard": catalog.names("moodboard")}
        return storyboard.build(s, narration, catalog.moodboard("instrument"), known)

    def test_three_scenes_in_one_part_is_a_check(self):
        self.assertIn("Part 1: 3D in 3 scenes: keep 3D for spatial ideas, 2 per part at most", self.board(spec(n=3))["checks"])
        self.assertEqual([], self.board(spec(n=2))["checks"])

    def test_3d_with_three_off_or_no_reason_is_a_check(self):
        self.assertTrue(any("three is off" in c for c in self.board(spec(three=False))["checks"]))
        self.assertTrue(any("add three_why" in c for c in self.board(spec(why=False))["checks"]))


@unittest.skipUnless((VENDOR / "three" / "build" / "three.module.js").is_file(), "three.js is not in this image yet")
class ThreeRenderTest(unittest.TestCase):
    def test_same_time_gives_the_same_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(three_selftest(Path(tmp)))

    def test_a_scene_cannot_reach_the_internet(self):
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "p.html").write_text('<img src="https://example.com/a.png"><script>fetch("https://example.com/b")'
                                              '.catch(() => {}); new WebSocket("wss://example.com/c");</script>')
            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Files, video=Path(tmp)))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            blocked = []
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch()
                    context = browser.new_context(service_workers="block")
                    guard(context, server.server_address[1], blocked)
                    page = context.new_page()
                    page.goto(f"http://127.0.0.1:{server.server_address[1]}/p.html")
                    page.wait_for_timeout(500)
                    browser.close()
            finally:
                server.shutdown()
        self.assertTrue(any("example.com/a.png" in u for u in blocked), blocked)
        self.assertTrue(any("example.com/b" in u for u in blocked), blocked)
        self.assertTrue(any(u.startswith("wss://example.com/c") for u in blocked), blocked)


if __name__ == "__main__":
    unittest.main()
