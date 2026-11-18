"""Render: headless Chromium captures each scene page frame by frame, ffmpeg encodes it,
and the voice clips are mixed in, giving one MP4 per part and format. The 720p preview you approve is the final
video; 1080p is an optional render after it (verdict() says when it is worth it).

The voice sets the clock. A beat starts when the voice of the beat before ends, plus `gap` and `hold`.
Pages get these times in window.EV_DATA, so picture and voice cannot drift apart.

Two engines capture the frames (script.yaml `engine:`):
- playwright (default): calls EV.seek(t) and takes a full-size JPEG over the DevTools protocol, once per frame;
  ffmpeg scales it down for 720p.
- hyperframes: `hyperframes render` (HeyGen, Apache-2.0) drives EV.seek(t) as a frame source and also seeks
  <video class="clip"> elements. Playwright then only lints the beat frames.
Scenes render in parallel, EV_WORKERS at a time (default 3), each in its own Chromium; a long scene is split into
chunks of frames, so it does not keep one worker busy while the others wait. Only a 3D scene's Chromium gets
software WebGL. `stills()` captures only the frame before each next beat: a fast check while scenes are drawn.
"""
import base64
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

import numpy as np
import soundfile as sf

from ev import catalog, gates, storyboard
from ev.common import FPS, ROOT, SCALE, SIZE, SR, VENDOR, ffmpeg, formats, load, norm, progress, run, seconds
from ev.voice import narrate

WEB = ROOT / "ev" / "web"
CAPTION_CHARS = {"pop": {"landscape": 28, "story": 16}, "line": {"landscape": 42, "story": 26}}  # per caption line
ENGINES = ("playwright", "hyperframes")
JPEG = {"720p": 90, "1080p": 95}                            # screenshot quality; the MP4 is yuv420p x264 CRF 18
PRESET = {"720p": "veryfast", "1080p": "fast"}              # x264: the final 1080p gets a little more care
WORKERS = max(1, int(os.environ.get("EV_WORKERS") or 3))   # pages rendered at the same time
CAPTURE = 2                                                 # in the cache key: change it when frames come out differently
CHUNK_MIN = 240                                             # frames: a shorter chunk costs more page loads than it saves


# ---------- timing ----------

def cue_lines(words, width):
    """Group timed words into caption lines of `width` characters or fewer; break after . ? ! : ;"""
    lines, line = [], []
    for w in words:
        if line and len(" ".join(x["w"] for x in line + [w])) > width:
            lines.append(line)
            line = []
        line.append(w)
        if w["w"][-1] in ".?!:;":
            lines.append(line)
            line = []
    lines += [line] if line else []
    cues = [{"start": c[0]["start"], "end": c[-1]["end"] + 0.3, "words": c} for c in lines]
    for a, b in zip(cues, cues[1:]):
        a["end"] = min(a["end"], b["start"])
    return cues


def caption_style(spec):
    style = spec.get("captions", "pop")
    style = {True: "pop", False: "off"}.get(style, style)
    if style not in ("pop", "line", "off"):
        raise SystemExit(f"captions: use pop, line, or off, not {style!r}")
    return style


def moodboard_name(spec):
    """The video's moodboard from `moodboard:`, or None for an old `look:` video, which keeps base.css's look.
    Only `moodboard:` loads a moodboard, because only that line puts the moodboard file in the preview hash."""
    if "moodboard" not in spec:
        return None
    name = str(spec["moodboard"])
    if name == "recommend":
        raise SystemExit("moodboard: recommend is still in script.yaml: step 1 picks a moodboard (see moodboards/).")
    if name not in catalog.names("moodboard"):
        raise SystemExit(f"No moodboard named {name!r}. Moodboards: {', '.join(catalog.names('moodboard'))}")
    return name


def scene_data(spec, scene, voice, gap, fmt):
    """Everything a scene page needs, with times in seconds from the scene's start."""
    t, beats = 0.0, []
    for beat, clip in zip(scene["beats"], voice):
        beats.append({"id": clip["id"], "text": clip["text"], "show": beat.get("show", ""),
                      "start": round(t, 3), "end": round(t + clip["duration"], 3),
                      "words": [{"w": w["w"], "key": w.get("key", False),
                                 "start": round(t + w["start"], 3), "end": round(t + w["end"], 3)}
                                for w in clip["words"]]})
        t += clip["duration"] + gap + float(beat.get("hold", 0))
    frames = max(1, round(t * FPS))
    for i, b in enumerate(beats):
        b["until"] = beats[i + 1]["start"] if i + 1 < len(beats) else frames / FPS
    width, height = SIZE[fmt]
    style = caption_style(spec)
    name = moodboard_name(spec)
    if name:
        look = {"math-dark": "dark"}.get(name, name if name in ("clean", "whiteboard") else "clean")  # base.css hooks
        motion = catalog.moodboard(name)["motion"]
    else:  # an old `look:` video keeps the look and the EV defaults it was approved with
        look, motion = spec.get("look", "clean"), {}
    return {"scene": scene["id"], "format": fmt, "look": look, "moodboard": name, "motion": motion,
            "captions": style, "width": width, "height": height,
            "frames": frames, "duration": frames / FPS, "beats": beats,
            "cues": cue_lines([w for b in beats for w in b["words"]], CAPTION_CHARS["line" if style == "off" else style][fmt])}


# ---------- capture ----------

THREE_URL = "/vendor/three/"
USES_THREE = re.compile(r"""/vendor/three/|three/addons/|from\s*["']three["']|import\(\s*["']three["']""")
WEBGL = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]  # software WebGL


def three_on(spec):
    """3D is allowed only when script.yaml says `three: true` (the dashboard's 3D box, ticked by default)."""
    return spec.get("three") is True


def three_scenes(video, spec):
    """Ids of the scenes whose page loads three.js."""
    return [s["id"] for p in spec["parts"] for s in p["scenes"]
            if (video / "scenes" / f"{s['id']}.html").is_file()
            and USES_THREE.search((video / "scenes" / f"{s['id']}.html").read_text())]


def three_checks(video, spec, engine):
    """Stop a render that uses three.js where it may not: 3D off, no reason given, or the hyperframes engine."""
    scenes = {s["id"]: s for p in spec["parts"] for s in p["scenes"]}
    for sid in three_scenes(video, spec):
        if not three_on(spec):
            raise SystemExit(f"three.js is off for this video (three: false), and scene {sid} loads it. "
                             f"Draw it in 2D, or set three: true.")
        if not str(scenes[sid].get("three_why") or "").strip():
            raise SystemExit(f"add three_why for scene {sid}: one line on why 3D explains it better than 2D")
        if engine == "hyperframes":
            raise SystemExit(f"scene {sid} uses three.js, which renders with engine: playwright only")


def guard(context, port, blocked):
    """Let a page load only from this render's own server: any other URL is aborted and listed in `blocked`
    (a LINT line). WebSockets never reach a server. The container has no network either (compose.yaml), which also covers
    what a route cannot see: WebRTC, DNS, and the hyperframes engine's own Chrome."""
    local = f"http://127.0.0.1:{port}/"

    def check(route):
        if route.request.url.startswith(local):
            return route.continue_()
        blocked.append(route.request.url)
        return route.abort()

    def socket(ws):  # no connect_to_server(): the socket stays inside the page, and what it sends goes nowhere
        blocked.append(ws.url)
    context.route("**/*", check)
    context.route_web_socket(re.compile(".*"), socket)


class Files(SimpleHTTPRequestHandler):
    """Serves /ev/ (page runtime), /vendor/ (rough.js, KaTeX, and three.js when the video allows 3D),
    and the rest from the video folder."""

    def __init__(self, *args, video, three=False, **kw):
        self.video, self.three = video, three
        super().__init__(*args, **kw)

    def translate_path(self, path):
        """Map a URL to a file inside its root. A path that leaves the root (../) maps to nothing, so a scene
        cannot read another video's files or the rest of the container."""
        path = unquote(path.split("?")[0].split("#")[0])
        if path == "/ev/theme.css":  # the video's moodboard as CSS variables, written by render()
            return str(self.video / "build" / "theme.css")
        if path.startswith(THREE_URL) and not self.three:  # three: false means 2D only
            return str(VENDOR / "__three_is_off__")
        root, rest = self.video, path.lstrip("/")
        for prefix, base in (("/ev/", WEB), ("/vendor/", VENDOR)):
            if path.startswith(prefix):
                root, rest = base, path[len(prefix):]
                break
        target = (root / rest).resolve()
        return str(target) if target.is_relative_to(root.resolve()) else str(root / "__outside__")

    def log_message(self, *args):
        pass


def beat_frames(data):
    """{frame: beat} for the frame just before each next beat: the review still and lint frame of that beat."""
    return {min(data["frames"] - 1, max(0, round(b["until"] * FPS) - 2)): b for b in data["beats"]}


def open_scene(page, url, data):
    """Load a scene page and wait for EV.ready(). Returns the list that keeps collecting JS errors."""
    errors = []
    page.on("pageerror", lambda e: errors.append(f"JS error: {e}"))
    page.on("console", lambda m: errors.append(f"console.error: {m.text}") if m.type == "error" else None)
    page.add_init_script(f"window.EV_DATA = {json.dumps(data)};")
    page.goto(url)
    try:
        page.wait_for_function("window.EV_READY === true", timeout=20000)
    except Exception:
        raise SystemExit(f"{data['scene']}: the page never called EV.ready().\n  "
                         + "\n  ".join(errors or ["No JS error was caught. Check the <script> tags."]))
    page.evaluate("document.fonts.ready")
    if errors:
        raise SystemExit(f"{data['scene']}:\n  " + "\n  ".join(errors))
    return errors


def lint_marks(page, url, data):
    """HyperFrames engine: lint only the beat frames, because HyperFrames captures every frame."""
    errors = open_scene(page, url, data)
    lint = []
    for i, b in sorted(beat_frames(data).items()):
        page.evaluate("t => EV.seek(t)", i / FPS)
        lint += [f"{data['scene']}/{b['id']}: {issue}" for issue in page.evaluate("EV.lint()")]
    if errors:
        raise SystemExit(f"{data['scene']}:\n  " + "\n  ".join(errors))
    return lint + [f"{data['scene']}: {w}" for w in page.evaluate("EV.warnings")]


def shooter(page, quality="720p"):
    """A function that returns one full-size JPEG of the page (1920 x 1080 for landscape: the context's device scale
    is 1). It calls the DevTools protocol directly, with no clip and optimizeForSpeed: about 21 ms a frame, where
    page.screenshot() took about 33 ms at 720p, and PNG at 1080p took far longer. A 720p MP4 is scaled down from it
    by ffmpeg, which also keeps thin lines and small text sharper than a page drawn at a 2/3 device scale."""
    cdp = page.context.new_cdp_session(page)
    params = {"format": "jpeg", "quality": JPEG[quality], "optimizeForSpeed": True}
    return lambda: base64.b64decode(cdp.send("Page.captureScreenshot", params)["data"])


def capture(page, url, data, mp4, stills, quality, frames=None):
    """Playwright engine: render one scene page (or the `frames` range of it) to a silent MP4. Saves and lints the
    frame just before each next beat."""
    errors = open_scene(page, url, data)
    shot = shooter(page, quality)
    marks = beat_frames(data)
    width, height = (round(n * SCALE[quality]) for n in SIZE[data["format"]])
    encoder = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
         *(["-vf", f"scale={width}:{height}:flags=lanczos"] if SCALE[quality] != 1 else []),
         "-c:v", "libx264", "-preset", PRESET[quality], "-crf", "18", "-pix_fmt", "yuv420p", str(mp4)],
        stdin=subprocess.PIPE)
    lint = []
    try:
        for i in frames or range(data["frames"]):
            page.evaluate("t => EV.seek(t)", i / FPS)
            image = shot()
            encoder.stdin.write(image)
            if i in marks:
                (stills / f"{marks[i]['id']}.jpg").write_bytes(image)
                lint += [f"{data['scene']}/{marks[i]['id']}: {issue}" for issue in page.evaluate("EV.lint()")]
    finally:
        encoder.stdin.close()
    if encoder.wait():
        raise SystemExit(f"{data['scene']}: ffmpeg failed")
    if errors:
        raise SystemExit(f"{data['scene']}:\n  " + "\n  ".join(errors))
    return lint + [f"{data['scene']}: {w}" for w in page.evaluate("EV.warnings")]


# ---------- HyperFrames engine ----------

AT = re.compile(r'data-start="at:([a-z0-9-]+)(?::([^"]+))?"')


def link(src, dst):
    """Hard-link a file, or copy it where the file system cannot link."""
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def hf_project(video, scope="all"):
    """build/hf/<scope>/: a HyperFrames project with the URLs the scene pages use: /ev/, /vendor/, ../style.css,
    ../assets/. One project per scope (a scene id, or "all"), so parallel SCENE= renders do not share one."""
    proj = video / "build" / "hf" / scope
    shutil.rmtree(proj, ignore_errors=True)
    shutil.copytree(WEB, proj / "ev")
    if (video / "build" / "theme.css").is_file():
        shutil.copy2(video / "build" / "theme.css", proj / "ev" / "theme.css")
    for lib in ("roughjs/bundled", "katex/dist"):
        shutil.copytree(VENDOR / lib, proj / "vendor" / lib)
    if (video / "style.css").is_file():
        shutil.copy2(video / "style.css", proj / "style.css")
    if (video / "assets").is_dir():
        shutil.copytree(video / "assets", proj / "assets", copy_function=link)
    (proj / "scenes").mkdir()
    return proj


def at_seconds(data, m):
    """data-start="at:beat" or "at:beat:phrase" in seconds: the same time EV.at returns."""
    b = next((x for x in data["beats"] if x["id"] == m[1]), None)
    if not b:
        raise SystemExit(f"{data['scene']}: no beat {m[1]!r} for {m[0]}")
    if not m[2]:
        return b["start"]
    want, said = [norm(w) for w in m[2].split()], [norm(w["w"]) for w in b["words"]]
    hits = [i for i in range(len(said)) if said[i:i + len(want)] == want]
    if not hits:
        raise SystemExit(f"{data['scene']}: {m[2]!r} is not in beat {m[1]!r}: {b['text']}")
    return b["words"][hits[0]]["start"]


def hf_page(video, proj, data):
    """Write the scene page for HyperFrames: EV_DATA inline, at: times in seconds, and the body wrapped in a
    composition root (#ev-root) with the scene's size and length. Returns the page's path."""
    page = (video / "scenes" / f"{data['scene']}.html").read_text()
    page = AT.sub(lambda m: f'data-start="{at_seconds(data, m):.3f}"', page)
    width, height = SIZE[data["format"]]
    script = "<script>window.EV_DATA = " + json.dumps(data).replace("</", "<\\/") + ";</script>"
    root = (f'<div id="ev-root" data-composition-id="{data["scene"]}" data-start="0" '
            f'data-duration="{data["duration"]!r}" data-width="{width}" data-height="{height}" data-fps="{FPS}" '
            f'data-no-timeline style="position: absolute; left: 0; top: 0; width: {width}px; height: {height}px; '
            f'overflow: hidden">')
    page, heads = re.subn(r"<head\b[^>]*>", lambda m: m[0] + script, page, count=1, flags=re.I)
    page, bodies = re.subn(r"<body\b[^>]*>", lambda m: m[0] + root, page, count=1, flags=re.I)
    page, ends = re.subn(r"</body>", "</div></body>", page, count=1, flags=re.I)
    if not (heads and bodies and ends):
        raise SystemExit(f"{data['scene']}: the hyperframes engine needs <head>, <body>, and </body> in the page")
    path = proj / "scenes" / f"{data['scene']}-{data['format']}.html"
    path.write_text(page)
    return path


def hf_capture(video, proj, data, mp4, stills, quality):
    """HyperFrames engine: render one scene page to a silent MP4, then cut the beat stills from it."""
    raw = mp4.with_name(mp4.stem + "-hf.mp4")
    page = hf_page(video, proj, data)
    # 1080p: slow preset, CRF 15. 720p: fast capture at full size, then scaled to 2/3 like the Playwright engine.
    cmd = ["hyperframes", "render", ".", "--composition", page.relative_to(proj), "--output", raw.resolve(),
           "--fps", FPS, "--quiet", *(["--quality", "high"] if quality == "1080p" else ["--quality", "draft", "--crf", 18]),
           *(["--workers", os.environ["EV_HF_WORKERS"]] if os.environ.get("EV_HF_WORKERS") else [])]
    result = subprocess.run([str(c) for c in cmd], cwd=proj, capture_output=True, text=True)
    if result.returncode:
        tail = (result.stdout + result.stderr).strip().splitlines()[-25:]
        raise SystemExit(f"{data['scene']}: hyperframes render failed\n  " + "\n  ".join(tail))
    width, height = (round(n * SCALE[quality]) for n in SIZE[data["format"]])
    video_only = ["-c:v", "copy"] if quality == "1080p" else [
        "-vf", f"scale={width}:{height}:flags=lanczos", "-c:v", "libx264", "-preset", "veryfast", "-crf", 18,
        "-pix_fmt", "yuv420p"]
    ffmpeg("-i", raw, "-an", *video_only, mp4)
    raw.unlink()
    frames = int(run("ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                     "stream=nb_read_packets", "-of", "csv=p=0", mp4, capture_output=True, text=True).stdout)
    if frames != data["frames"]:
        raise SystemExit(f"{data['scene']}: hyperframes wrote {frames} frames, and the voice needs {data['frames']}")
    for i, b in beat_frames(data).items():
        ffmpeg("-ss", f"{(i + 0.5) / FPS:.4f}", "-i", mp4, "-frames:v", 1, "-q:v", 2, stills / f"{b['id']}.jpg")


SELFTEST_PAGE = """<!doctype html>
<html><head><link rel="stylesheet" href="/ev/base.css"><script src="/ev/ev.js"></script></head>
<body><div class="stage"></div>
<script>
EV.fromTo(".stage", { backgroundColor: "#000000" }, { backgroundColor: "#ffffff", duration: 0.3, ease: "none" }, 0);
EV.ready();
</script></body></html>
"""


THREE_PAGE = """<!doctype html>
<html><head><link rel="stylesheet" href="/ev/base.css"><script src="/ev/ev.js"></script>
<script type="importmap">{"imports": {"three": "/vendor/three/build/three.module.js"}}</script></head>
<body><div class="stage"><canvas id="c" width="480" height="270"></canvas></div>
<script type="module">
import * as THREE from "three";
const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById("c"), antialias: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(40, 16 / 9, 0.1, 100);
camera.position.set(0, 0, 6);
const cube = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(2, 2, 2)), new THREE.LineBasicMaterial({ color: 0x2ec7f0 }));
scene.add(cube);
EV.onFrame(t => { cube.rotation.set(t * 0.8, t * 1.1, 0); renderer.render(scene, camera); });
EV.ready();
</script></body></html>
"""


def three_selftest(folder):
    """For make doctor: draw a turning three.js cube in software WebGL. True when the same time gives the same
    pixels twice (in two page loads), another time gives other pixels, and the frame is not empty."""
    import hashlib as h
    from playwright.sync_api import sync_playwright
    (folder / "scenes").mkdir()
    (folder / "scenes" / "t.html").write_text(THREE_PAGE)
    data = {"scene": "t", "format": "landscape", "look": "clean", "captions": "off", "width": 1920, "height": 1080,
            "frames": 30, "duration": 1.0, "cues": [], "beats": [{"id": "t", "text": "", "show": "", "start": 0,
                                                                "end": 1.0, "until": 1.0, "words": []}]}
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Files, video=folder.resolve(), three=True))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    shots = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--font-render-hinting=none", *WEBGL])
            for t in (0.5, 0.5, 1.0):
                page = browser.new_page(viewport={"width": 480, "height": 270})
                open_scene(page, f"http://127.0.0.1:{server.server_address[1]}/scenes/t.html", data)
                page.evaluate("t => EV.seek(t)", t)
                shots.append(page.locator("#c").screenshot())
                page.close()
            browser.close()
    finally:
        server.shutdown()
    from io import BytesIO

    from PIL import Image
    a, b, c = (h.sha256(s).hexdigest() for s in shots)
    drawn = any(lo != hi for lo, hi in Image.open(BytesIO(shots[0])).convert("RGB").getextrema())
    return a == b and a != c and drawn


def hf_selftest(folder):
    """For make doctor: render a 0.5 s fade from black to white with the hyperframes engine.
    True when the first frame is dark and the beat frame is light, so EV.seek drove the frames."""
    from PIL import Image, ImageStat
    (folder / "scenes").mkdir()
    (folder / "scenes" / "t.html").write_text(SELFTEST_PAGE)
    data = {"scene": "t", "format": "landscape", "look": "clean", "captions": "off", "width": 1920, "height": 1080,
            "frames": 15, "duration": 0.5, "cues": [],
            "beats": [{"id": "t", "text": "", "show": "", "start": 0, "end": 0.5, "until": 0.5, "words": []}]}
    hf_capture(folder, hf_project(folder), data, folder / "t.mp4", folder, "720p")
    ffmpeg("-i", folder / "t.mp4", "-frames:v", 1, folder / "first.png")
    light = [ImageStat.Stat(Image.open(folder / name).convert("L")).mean[0] for name in ("first.png", "t.jpg")]
    return light[0] < 64 and light[1] > 192


# ---------- per scene ----------

def record_timing(video, engine, quality, per_frame):
    """Seconds per frame of the last 20 renders (wall time over all frames, so parallel scenes count once),
    per engine and quality, for the dashboard's estimate."""
    path = video / "build" / "timings.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        data = {}
    key = f"{engine}-{quality}"
    data[key] = (data.get(key, []) + [round(per_frame, 4)])[-20:]
    path.write_text(json.dumps(data))


def cache_base(video, data, engine, quality):
    """build/scenes/<format>-<quality>/<scene>-<hash>: the hash covers everything that changes the scene's picture."""
    key = hashlib.sha256(json.dumps(data, sort_keys=True).encode())
    key.update(f"{engine} {os.environ.get('HYPERFRAMES_VERSION', '') if engine == 'hyperframes' else ''}".encode())
    key.update(f"three {os.environ.get('THREE_VERSION', '')} capture {CAPTURE}".encode())
    for path in [video / "scenes" / f"{data['scene']}.html", video / "style.css", video / "build" / "theme.css",
                 *sorted(WEB.glob("*")), *sorted((video / "assets").glob("**/*"))]:
        if path.is_file():
            key.update(path.read_bytes())
    return video / "build" / "scenes" / f"{data['format']}-{quality}" / f"{data['scene']}-{key.hexdigest()[:12]}"


class Browsers:
    """One Playwright and up to two Chromiums for one thread: plain, and with software WebGL for 3D scenes.
    Playwright's sync API is not thread-safe, so each thread starts its own."""

    def __init__(self):
        from playwright.sync_api import sync_playwright
        self.playwright, self.open = sync_playwright().start(), {}

    def get(self, webgl):
        if webgl not in self.open:
            self.open[webgl] = self.playwright.chromium.launch(args=["--font-render-hinting=none", *(WEBGL if webgl else [])])
        return self.open[webgl]

    def context(self, port, fmt, webgl):
        """A new context at the format's full size (device scale 1: see shooter()) with the network guard.
        Returns (context, blocked URLs)."""
        width, height = SIZE[fmt]
        context = self.get(webgl).new_context(viewport={"width": width, "height": height}, device_scale_factor=1,
                                              service_workers="block")  # a service worker's requests skip routes
        blocked = []
        guard(context, port, blocked)
        return context, blocked

    def close(self):
        for browser in self.open.values():
            browser.close()
        self.playwright.stop()


def tasks_for(jobs, engine):
    """The scenes to render as tasks of about equal length, longest first, so WORKERS pages finish together.
    A long scene (Playwright engine) becomes chunks of frames; HyperFrames renders a scene in one piece."""
    total = sum(j["data"]["frames"] for j in jobs)
    target = max(CHUNK_MIN, -(-total // WORKERS))
    tasks = []
    for job in jobs:
        frames = job["data"]["frames"]
        n = -(-frames // target) if engine == "playwright" and frames > target * 1.25 else 1
        job["chunks"] = n
        for k in range(n):
            a, b = frames * k // n, frames * (k + 1) // n
            tasks.append({"job": job, "frames": range(a, b), "n": n,
                          "out": job["base"].with_suffix(".mp4") if n == 1 else job["base"] / f"chunk-{k}.mp4"})
    return sorted(tasks, key=lambda t: -len(t["frames"]))


def render_scene(browsers, port, video, task, engine, proj):
    """Render one task: a whole scene, or a chunk of its frames, to its MP4 and its beat stills. Returns its lint."""
    job = task["job"]
    data, base = job["data"], job["base"]
    base.mkdir(parents=True, exist_ok=True)
    context, blocked = browsers.context(port, data["format"], job["webgl"])
    part = f", frames {task['frames'].start}-{task['frames'].stop - 1}" if task["n"] > 1 else ""
    print(f"  scene {job['where']} {data['scene']}: {data['duration']:.1f}s ({engine}{part})", flush=True)
    url = f"http://127.0.0.1:{port}/scenes/{data['scene']}.html"
    try:
        if engine == "hyperframes":
            lint = lint_marks(context.new_page(), url, data)
            hf_capture(video, proj, data, task["out"], base, job["quality"])
        else:
            lint = capture(context.new_page(), url, data, task["out"], base, job["quality"], task["frames"])
    finally:
        context.close()
    return lint + [f"{data['scene']}: blocked a request to {u[:120]}: put the file in assets/" for u in dict.fromkeys(blocked)]


def finish_scene(job, lints):
    """Join a chunked scene's MP4s, then write <base>.lint.json, which marks the scene done."""
    base = job["base"]
    if job["chunks"] > 1:
        listing = base / "chunks.txt"
        listing.write_text("".join(f"file '{(base / f'chunk-{k}.mp4').resolve()}'\n" for k in range(job["chunks"])))
        ffmpeg("-f", "concat", "-safe", 0, "-i", listing, "-c", "copy", base.with_suffix(".mp4"))
        for k in range(job["chunks"]):
            (base / f"chunk-{k}.mp4").unlink()
        listing.unlink()
    base.with_suffix(".lint.json").write_text(json.dumps(list(dict.fromkeys(lints))))  # a chunk repeats EV.warnings


def render_all(jobs, port, video, engine, proj, label):
    """Render the scenes in `jobs`, WORKERS pages at a time, each worker with its own Chromium. The first error stops
    the workers from taking more tasks, and is raised here."""
    tasks = tasks_for(jobs, engine)
    todo, failed, lints, lock = queue.SimpleQueue(), [], {}, threading.Lock()
    for task in tasks:
        todo.put(task)

    def worker():
        browsers = None
        try:
            while not failed:
                try:
                    task = todo.get_nowait()
                except queue.Empty:
                    return
                browsers = browsers or Browsers()
                lint = render_scene(browsers, port, video, task, engine, proj)
                job = task["job"]
                with lock:
                    got = lints.setdefault(id(job), [])
                    got.append((task["frames"].start, lint))
                    whole = len(got) == job["chunks"]
                if whole:  # its last chunk: join the scene
                    finish_scene(job, [x for _, chunk in sorted(got, key=lambda g: g[0]) for x in chunk])
                    progress(video, label, f"{sum(len(v) == j['chunks'] for j in jobs for v in [lints.get(id(j), [])])} "
                                           f"of {len(jobs)} scenes done")
        except BaseException as e:  # SystemExit too: it carries the message for the person
            failed.append(e)
        finally:
            if browsers:
                browsers.close()
    threads = [threading.Thread(target=worker, daemon=True) for _ in range(min(WORKERS, len(tasks)))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if failed:
        raise failed[0]


# ---------- assemble ----------

def stamp(t, sep=","):
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", sep)


def assemble(video, stem, clips, voices, cues, length):
    """Join scene clips, place each voice clip at its beat, write SRT and VTT files, and mux the MP4
    with a subtitle track that players can switch on (off by default, because captions are in the picture)."""
    build, out_dir = video / "build" / "parts", video / "out"
    build.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(exist_ok=True)
    listing = build / f"{stem}.txt"
    listing.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    picture = build / f"{stem}-picture.mp4"
    ffmpeg("-f", "concat", "-safe", 0, "-i", listing, "-c", "copy", picture)
    mix = np.zeros(int(length * SR) + 1, np.float32)
    for t, wav in voices:
        samples, _ = sf.read(wav, dtype="float32")
        i = int(t * SR)
        n = max(0, min(len(samples), len(mix) - i))
        mix[i:i + n] += samples[:n]
    voice = build / f"{stem}-voice.wav"
    sf.write(voice, np.clip(mix, -1, 1), SR)
    srt = out_dir / f"{stem}.srt"
    srt.write_text("".join(f"{i}\n{stamp(a)} --> {stamp(b)}\n{text}\n\n" for i, (a, b, text) in enumerate(cues, 1)))
    (out_dir / f"{stem}.vtt").write_text(
        "WEBVTT\n\n" + "".join(f"{stamp(a, '.')} --> {stamp(b, '.')}\n{text}\n\n" for a, b, text in cues))
    subtitles = (["-i", srt, "-map", "0:v", "-map", "1:a", "-map", "2:s", "-c:s", "mov_text",
                  "-metadata:s:s:0", "language=eng", "-disposition:s:0", "0"] if cues else ["-map", "0:v", "-map", "1:a"])
    out = out_dir / f"{stem}.mp4"
    ffmpeg("-i", picture, "-i", voice, *subtitles, "-c:v", "copy",
           "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", 48000,
           "-movflags", "+faststart", out)
    return out


def contact_sheets(video, stem, shots, fmt):
    """Labelled sheets of 12 review frames each, for a person or an agent to check in one look."""
    from PIL import Image, ImageDraw
    tw, th, cols = (240, 427, 6) if fmt == "story" else (480, 270, 4)
    folder = video / "build" / "review"
    folder.mkdir(parents=True, exist_ok=True)
    sheets = []
    for k in range(0, len(shots), 12):
        group = shots[k:k + 12]
        sheet = Image.new("RGB", (cols * tw, -(-len(group) // cols) * (th + 24)), "white")
        draw = ImageDraw.Draw(sheet)
        for i, (image, label, _) in enumerate(group):
            x, y = i % cols * tw, i // cols * (th + 24)
            sheet.paste(Image.open(image).convert("RGB").resize((tw, th)), (x, y + 24))
            draw.text((x + 4, y + 6), f"{k + i + 1:02d} {label}", fill="black")
        path = folder / f"{stem}-contact-{k // 12 + 1}.png"
        sheet.save(path)
        sheets.append(path)
    return sheets


# ---------- main ----------

def render(video, quality, fmt=None, part=None, scene=None):
    """Render every scene (cached by content), join them per part and format, and mix in the voice.
    720p needs no approval; 1080p needs the approved preview."""
    spec = load(video)
    targets = formats(spec, fmt)
    if quality == "1080p":
        for f in targets:
            gates.require(video, quality, f)
    fp = gates.fingerprint(video, "preview")
    spec, voice = narrate(video)
    engine = prepare(video, spec)
    threes = set(three_scenes(video, spec))
    proj = hf_project(video, scene or "all") if engine == "hyperframes" else None
    server = serve(video, spec)
    try:
        parts = []  # (format, part number, [job]) in render order
        for f in targets:
            for n, p in enumerate(spec["parts"], 1):
                chosen = [s for s in p["scenes"] if not scene or s["id"] == scene]
                if (part and n != part) or not chosen:
                    continue
                jobs = []
                for s in chosen:
                    data = scene_data(spec, s, voice["scenes"][s["id"]], voice["gap"], f)
                    jobs.append({"data": data, "base": cache_base(video, data, engine, quality), "quality": quality,
                                 "voice": voice["scenes"][s["id"]], "webgl": s["id"] in threes})
                parts.append((f, n, jobs))
        every = [j for _, _, jobs in parts for j in jobs]
        for i, job in enumerate(every, 1):
            job["where"] = f"{i}/{len(every)}"
        missing = [j for j in every if not j["base"].with_suffix(".lint.json").exists()]
        for job in every:
            if job not in missing:
                print(f"  scene {job['where']} {job['data']['scene']}: cached", flush=True)
        if missing:
            label = f"Rendering {quality} {', '.join(targets)}"
            progress(video, label, f"0 of {len(missing)} scenes done")
            print(f"render {len(missing)} scene{'s' if len(missing) > 1 else ''}, {WORKERS} pages at a time", flush=True)
            started = time.monotonic()
            render_all(missing, server.server_address[1], video, engine, proj, label)
            record_timing(video, engine, quality, (time.monotonic() - started) / sum(j["data"]["frames"] for j in missing))
        many = len(spec["parts"]) > 1
        for f in targets:
            shots, outs = [], []
            for ff, n, jobs in parts:
                if ff == f:
                    out, part_shots = assemble_part(video, f, n, jobs, scene, many, quality)
                    shots, outs = shots + part_shots, outs + [out]
            if quality == "1080p" and gates.fingerprint(video, "preview") != fp:  # edited while it rendered
                for out in outs:
                    out.unlink(missing_ok=True)
                raise SystemExit("A file changed during the 1080p render, so it no longer matches the approved "
                                 "preview. The 1080p files were removed: check the change and approve the preview again.")
            if not part and not scene:
                gates.record_render(video, f, quality, fp)
                if quality == "720p":
                    save_frames(video, f, shots)
    finally:
        server.shutdown()
        progress(video, "done", "")
    if quality == "720p" and not part and not scene:
        storyboard.refresh(video, spec, voice)  # now with a frame per beat
        v = verdict(video, spec)
        (video / "build" / "verdict.json").write_text(json.dumps(v))
        print(f"VERDICT 1080p: {v['1080p']}. {v['why']}")


PICTURES = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".mp4", ".webm", ".mov"}


def verdict(video, spec):
    """Is the optional 1080p render worth it? Drawn text is 28 CSS px or more (EV.lint), which 720p shows sharply.
    A picture of a screen (a page capture from make from-html, a screenshot, a video clip) carries the source's own
    small text, which 1080p keeps readable on a big screen. {"1080p": "not needed" | "worth it for big screens",
    "why": one sentence}"""
    pages = [s["id"] for p in spec["parts"] for s in p["scenes"] if s.get("treatment") == "page"]
    pictures = [f for f in (video / "assets").glob("**/*") if f.suffix.lower() in PICTURES and "page" not in f.parts]
    if pages or pictures:  # a scene can load a picture from a script, so the assets/ folder is the signal
        what = " and ".join(x for x in (
            f"{len(pages)} page capture{'s' if len(pages) != 1 else ''}" if pages else "",
            f"{len(pictures)} screenshot{'s' if len(pictures) != 1 else ''} or clip{'s' if len(pictures) != 1 else ''}"
            f" from assets/" if pictures else "") if x)
        return {"1080p": "worth it for big screens",
                "why": f"The video shows {what}, with the source's own small text: 720p is fine on a laptop or phone, "
                       f"and 1080p keeps that text readable on a projector, a TV, or a public upload."}
    return {"1080p": "not needed",
            "why": "Every scene is drawn, with text of 28 px or more, which 720p shows sharply on any screen."}


def prepare(video, spec):
    """Write build/theme.css, check the engine and 3D rules. Returns the engine."""
    name = moodboard_name(spec)
    (video / "build" / "theme.css").write_text(catalog.theme_css(name) if name else
                                               "/* no moodboard: this video's look: comes from base.css */\n")
    engine = spec.get("engine", "playwright")
    if engine not in ENGINES:
        raise SystemExit(f"engine: use {' or '.join(ENGINES)}, not {engine!r}")
    three_checks(video, spec, engine)
    return engine


def serve(video, spec):
    """A local web server for the scene pages: the only place a page may load from."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Files, video=video.resolve(), three=three_on(spec)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def assemble_part(video, fmt, n, jobs, scene, many, quality):
    """Join one part's scene clips with its voice, print its review frames and lint. Returns the MP4 and its
    review stills, as (image, "scene/beat", show)."""
    print(f"render {fmt} {quality} part {n}", flush=True)
    clips, voices, cues, shots, lint, offset = [], [], [], [], [], 0.0
    for job in jobs:
        data, base = job["data"], job["base"]
        clips.append(base.with_suffix(".mp4"))
        lint += json.loads(base.with_suffix(".lint.json").read_text())
        for b, clip in zip(data["beats"], job["voice"]):
            voices.append((offset + b["start"], clip["wav"]))
            shots.append((base / f"{b['id']}.jpg", f"{data['scene']}/{b['id']}", b["show"]))
        lines = cue_lines([w for b in data["beats"] for w in b["words"]], CAPTION_CHARS["line"][fmt])  # SRT and VTT
        cues += [(offset + c["start"], offset + c["end"], " ".join(w["w"] for w in c["words"])) for c in lines]
        offset += data["duration"]
    stem = f"{video.name}{f'-part{n}' if many else ''}{f'-{scene}' if scene else ''}-{fmt}-{quality}"
    out = assemble(video, stem, clips, voices, cues, offset)
    print(f"DONE {out} ({seconds(out):.0f}s)")
    report(video, stem, shots, lint, fmt)
    return out, shots


def report(video, stem, shots, lint, fmt):
    """Print each review frame with its storyboard line, the contact sheets, and the LINT lines."""
    for i, (_, label, show) in enumerate(shots, 1):
        print(f"  frame {i:02d} {label}  show: {show}")
    for sheet in contact_sheets(video, stem, shots, fmt):
        print(f"  contact sheet: {sheet}")
    print("\n".join(f"LINT {x}" for x in lint) if lint else "  lint: clean")


def save_frames(video, fmt, shots):
    """One small JPEG per beat, frames/<format>/<scene>/<beat>.jpg, for storyboard.md and a sample's page.
    Full 720p renders only, so the frames always show one whole, current preview."""
    from PIL import Image
    folder = video / "frames" / fmt
    shutil.rmtree(folder, ignore_errors=True)
    for image, label, _ in shots:
        scene, beat = label.split("/")  # both checked as plain ids by load()
        out = folder / scene / f"{beat}.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        picture = Image.open(image).convert("RGB")
        picture.thumbnail((640, 640))
        picture.save(out, quality=80)


def stills(video, fmt=None, part=None, scene=None):
    """The fast check while scenes are drawn: only the frame before each next beat, linted, with a contact sheet.
    No MP4 and no cache. Uses Playwright with both engines, so a <video class="clip"> shows its first frame here."""
    spec = load(video)
    spec, voice = narrate(video)
    engine = prepare(video, spec)
    threes = set(three_scenes(video, spec))
    server = serve(video, spec)
    browsers = Browsers()
    try:
        for f in formats(spec, fmt):
            shots, lint = [], []
            for n, p in enumerate(spec["parts"], 1):
                for s in p["scenes"]:
                    if (part and n != part) or (scene and s["id"] != scene):
                        continue
                    data = scene_data(spec, s, voice["scenes"][s["id"]], voice["gap"], f)
                    folder = video / "build" / "stills" / f / s["id"]
                    shutil.rmtree(folder, ignore_errors=True)
                    folder.mkdir(parents=True)
                    context, blocked = browsers.context(server.server_address[1], f, s["id"] in threes)
                    try:
                        page = context.new_page()
                        errors = open_scene(page, f"http://127.0.0.1:{server.server_address[1]}/scenes/{s['id']}.html", data)
                        shot = shooter(page)
                        for i, b in sorted(beat_frames(data).items()):
                            page.evaluate("t => EV.seek(t)", i / FPS)
                            (folder / f"{b['id']}.jpg").write_bytes(shot())
                            lint += [f"{s['id']}/{b['id']}: {issue}" for issue in page.evaluate("EV.lint()")]
                            shots.append((folder / f"{b['id']}.jpg", f"{s['id']}/{b['id']}", b["show"]))
                        if errors:
                            raise SystemExit(f"{s['id']}:\n  " + "\n  ".join(errors))
                        lint += [f"{s['id']}: {w}" for w in page.evaluate("EV.warnings")]
                    finally:
                        context.close()
                    lint += [f"{s['id']}: blocked a request to {u[:120]}: put the file in assets/" for u in dict.fromkeys(blocked)]
            if not shots:
                raise SystemExit(f"No scene {scene!r} in script.yaml" if scene else "No scenes in script.yaml")
            stem = f"{video.name}{f'-part{part}' if part else ''}{f'-{scene}' if scene else ''}-{f}-stills"
            print(f"DONE stills {f}: {len(shots)} frames ({engine} renders the MP4 in make preview)")
            report(video, stem, shots, lint, f)
    finally:
        browsers.close()
        server.shutdown()
