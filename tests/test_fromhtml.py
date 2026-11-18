"""make from-html: the host copy (ev/intake.py), the CDN copy (vendor), and the section capture (sections)."""
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ev import fromhtml, intake

PAGE = """<!doctype html><html><head><title>Partner sort</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/lib@1.0.0/lib.min.css" integrity="sha384-x" crossorigin="anonymous">
<link rel="preconnect" href="https://fonts.googleapis.com">
<script src="https://cdn.jsdelivr.net/npm/tool@2.0.0/dist/tool.min.js"></script>
<script src="https://evil.example.com/x.js"></script>
<style>@import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap");</style>
</head><body><a href="https://example.slack.com/archives/x">thread</a></body></html>"""


class FakeResponse(io.BytesIO):
    def __init__(self, url, body, kind):
        super().__init__(body)
        self.url, self.headers = url, mock.Mock(get_content_type=lambda: kind)

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def fake_cdn(request, timeout=30):
    url = request.full_url
    if url.endswith("lib.min.css"):
        return FakeResponse(url, b".a{background:url(img/dot.png)}", "text/css")
    if "fonts.googleapis.com/css2" in url:
        return FakeResponse(url, b"@font-face{src:url(https://fonts.gstatic.com/s/inter/v1/a.woff2)}", "text/css")
    return FakeResponse(url, b"bytes of " + url.encode(), "application/octet-stream")


class IntakeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.projects = self.root / "projects"
        self.src = self.root / "ask" / "report"
        (self.src / "img").mkdir(parents=True)
        (self.root / "secret.txt").write_text("no")

    def tearDown(self):
        self.tmp.cleanup()

    def copy(self, slug, file, base=None):
        return intake.copy(slug, file, base=base, root=self.projects)

    def test_copies_the_page_and_only_its_local_files(self):
        (self.src / "page.html").write_text('<img src="img/a.png?v=2"><link href="style.css" rel="stylesheet">'
                                            '<a href="../../secret.txt">x</a><a href="notes.md">n</a>'
                                            '<div style="background: url(\'img/b.svg\')"></div><img src="data:x">'
                                            '<script src="https://cdn.jsdelivr.net/x.js"></script>')
        (self.src / "img" / "a.png").write_bytes(b"a")
        (self.src / "img" / "b.svg").write_text("<svg/>")
        (self.src / "style.css").write_text("p{}")
        (self.src / "notes.md").write_text("n")
        folder, _, copied, skipped = self.copy("rep", self.src / "page.html")
        self.assertRegex(folder.name, r"^\d{8}-rep$")  # a name starts a dated project
        self.assertEqual(["img/a.png", "style.css", "img/b.svg"], copied)
        self.assertTrue(any(s.startswith("../../secret.txt: outside") for s in skipped))
        self.assertTrue(any(s.startswith("notes.md: not a file type") for s in skipped))
        page = folder / "assets" / "page"
        self.assertTrue((page / "index.html").is_file())
        self.assertTrue((folder / "sources").is_dir())
        self.assertFalse((page / "secret.txt").exists())

    def test_a_symlink_is_never_followed_out_of_the_folder(self):
        (self.src / "page.html").write_text('<img src="leak.png">')
        os.symlink(self.root / "secret.txt", self.src / "leak.png")
        _, _, copied, skipped = self.copy("rep", self.src / "page.html")
        self.assertEqual([], copied)
        self.assertIn("leak.png: outside the page's folder", skipped)

    def test_only_an_html_file_and_a_from_html_project(self):
        (self.src / "page.html").write_text("<p>x</p>")
        with self.assertRaisesRegex(SystemExit, "must be an .html"):
            self.copy("rep", self.root / "secret.txt")
        with self.assertRaisesRegex(SystemExit, "lowercase"):
            self.copy("../x", self.src / "page.html")
        (self.projects / "20261118-drawn").mkdir(parents=True)
        (self.projects / "20261118-drawn" / "script.yaml").write_text("title: x\n")
        with self.assertRaisesRegex(SystemExit, "not a from-html project"):
            self.copy("20261118-drawn", self.src / "page.html")
        first = self.copy("rep", self.src / "page.html")[0]
        (first / "script.yaml").write_text("kept")
        again = self.copy(first.name, self.src / "page.html")[0]  # its id: the page is replaced, the script stays
        self.assertEqual((first, "kept"), (again, (again / "script.yaml").read_text()))

    def test_a_relative_path_is_read_from_the_base_folder(self):
        (self.src / "page.html").write_text("<p>x</p>")
        _, src, _, _ = self.copy("rep", "ask/report/page.html", base=self.root)
        self.assertEqual(self.src.resolve() / "page.html", src)


class VendorTest(unittest.TestCase):
    def test_cdn_files_are_copied_and_the_page_points_at_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "rep"
            page = video / "assets" / "page"
            page.mkdir(parents=True)
            (page / "index.html").write_text(PAGE)
            with mock.patch.object(fromhtml.urllib.request, "urlopen", side_effect=fake_cdn) as fetch:
                fromhtml.vendor(video)
                html = (page / "index.html").read_text()
                calls = fetch.call_count
                fromhtml.vendor(video)  # nothing left to fetch
                self.assertEqual(calls, fetch.call_count)
            self.assertIn('href="vendor/cdn.jsdelivr.net/npm/lib@1.0.0/lib.min.css"', html)
            self.assertNotIn("integrity", html)  # the CSS changed, so its hash would fail
            self.assertIn('src="vendor/cdn.jsdelivr.net/npm/tool@2.0.0/dist/tool.min.js"', html)
            self.assertIn("https://evil.example.com/x.js", html)  # not on the list: left, and blocked at capture
            self.assertIn("https://example.slack.com/archives/x", html)  # a link, not a file the page loads
            self.assertIn('href="https://fonts.googleapis.com"', html)  # preconnect is no file
            css = (page / "vendor/cdn.jsdelivr.net/npm/lib@1.0.0/lib.min.css").read_text()
            self.assertIn("url(img/dot.png)", css)
            self.assertTrue((page / "vendor/cdn.jsdelivr.net/npm/lib@1.0.0/img/dot.png").is_file())
            fonts = next((page / "vendor" / "fonts.googleapis.com").glob("css2-*.css")).read_text()
            self.assertIn("url(../fonts.gstatic.com/s/inter/v1/a.woff2)", fonts)
            self.assertIn("vendor/fonts.googleapis.com/css2-", html)
            urls = [c.args[0].full_url for c in fetch.call_args_list]
            self.assertFalse(any("evil" in u or "slack" in u for u in urls))

    def test_only_https_on_the_list_counts(self):
        self.assertTrue(fromhtml.allowed("https://cdnjs.cloudflare.com/ajax/libs/x.js"))
        self.assertFalse(fromhtml.allowed("http://cdnjs.cloudflare.com/ajax/libs/x.js"))
        self.assertFalse(fromhtml.allowed("https://cdnjs.cloudflare.com.evil.example/x.js"))


SECTIONS = """<!doctype html><html><head><title>Demo page</title>
<style>body{margin:0;font:18px sans-serif;background:#fafafa} header{height:300px} section{padding:40px;margin:20px auto;
width:900px;background:#fff} .tall{height:2600px} nav{position:fixed;top:0;left:0;right:0;height:60px;background:red}
.in{animation:fade 5s both} @keyframes fade{from{opacity:0}to{opacity:1}}</style></head>
<body><nav>menu</nav><header><h1>Demo page</h1><p>Intro words.</p></header>
<section><h2>First</h2><p class="in">One.</p><table style="width:400px"><tr><td>a</td><td>b</td></tr></table></section>
<section class="tall"><h2>Second</h2><pre>code here</pre></section>
<section><h2>Third</h2><p>Three.</p></section></body></html>"""


class SectionsTest(unittest.TestCase):
    def test_sections_are_captured_and_the_video_is_drafted(self):
        try:
            import playwright  # noqa: F401
        except ImportError:
            self.skipTest("Playwright runs in the Docker image (make test)")
        from PIL import Image

        from ev.common import load
        from ev.storyboard import build
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "demo"
            (video / "assets" / "page").mkdir(parents=True)
            (video / "assets" / "page" / "index.html").write_text(SECTIONS)
            fromhtml.sections(video)
            manifest = json.loads((video / "build" / "sections.json").read_text())
            found = manifest["formats"]["landscape"]["sections"]
            self.assertEqual(["s00", "s01", "s02", "s03"], [s["id"] for s in found])
            self.assertEqual(("Demo page", True), (found[0]["heading"], found[0]["title"]))
            self.assertEqual(["table"], [p["tag"] for p in found[1]["parts"] if p["tag"] != "h3"])
            self.assertIn("One.", found[1]["text"])
            tall = Image.open(video / found[2]["shot"])
            self.assertEqual((found[2]["w"] * 2, found[2]["h"] * 2), tall.size)  # captured at 2x
            first = Image.open(video / found[1]["shot"]).convert("RGB")
            self.assertNotEqual((255, 0, 0), first.getpixel((5, 5)))  # the fixed nav is hidden
            spec = load(video)
            self.assertEqual(["s00", "s01", "s02", "s03"], [s["id"] for s in spec["parts"][0]["scenes"]])
            self.assertTrue(all(s["treatment"] == "page" for s in spec["parts"][0]["scenes"]))
            scene = (video / "scenes" / "s02.html").read_text()
            self.assertIn('EV.page("s02", {"bg": "rgb(255, 255, 255)", "w": 980,', scene)  # 900 px + 2 x 40 px padding
            self.assertIn('"tag": "pre"', scene)
            narration = {"gap": 0.35, "scenes": {s["id"]: [{"id": f"{s['id']}-a", "text": "x", "duration": 1, "words": [], "match": 1}]
                                                for s in spec["parts"][0]["scenes"]}}
            from ev import catalog
            mood = catalog.moodboard("clean")
            self.assertFalse([c for c in build(spec, narration, mood)["checks"] if "treatment" in c])
            (video / "script.yaml").write_text((video / "script.yaml").read_text().replace("(fill in) narration", "Kept"))
            fromhtml.sections(video)  # again: the stills are new, the script stays
            self.assertIn("Kept", (video / "script.yaml").read_text())


class VerdictTest(unittest.TestCase):
    def test_drawn_scenes_need_no_1080p_and_pictures_of_screens_do(self):
        from ev.render import verdict
        with tempfile.TemporaryDirectory() as tmp:
            video, spec = Path(tmp), {"parts": [{"scenes": [{"id": "a"}]}]}
            self.assertEqual("not needed", verdict(video, spec)["1080p"])
            (video / "assets").mkdir()
            (video / "assets" / "motion.js").write_text("")
            self.assertEqual("not needed", verdict(video, spec)["1080p"])
            (video / "assets" / "queue.jpg").write_bytes(b"x")  # a screenshot a script loads
            self.assertEqual("worth it for big screens", verdict(video, spec)["1080p"])
            (video / "assets" / "queue.jpg").unlink()
            spec["parts"][0]["scenes"][0]["treatment"] = "page"
            self.assertIn("1 page capture", verdict(video, spec)["why"])


if __name__ == "__main__":
    unittest.main()
