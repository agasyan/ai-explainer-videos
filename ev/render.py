"""Render: headless Chromium captures each scene page frame by frame, ffmpeg encodes it,
and the voice clips are mixed in, giving one MP4 per part and format.

The voice sets the clock. A beat starts when the voice of the beat before ends, plus `gap` and `hold`.
Pages get these times in window.EV_DATA, so picture and voice cannot drift apart.

Two engines capture the frames (script.yaml `engine:`):
- playwright (default): calls EV.seek(t) and takes a screenshot, once per frame, in one page.
- hyperframes: `hyperframes render` (HeyGen, Apache-2.0) drives EV.seek(t) as a frame source, in parallel
  Chrome workers, and also seeks <video class="clip"> elements. Playwright then only lints the beat frames.
"""
import hashlib
import json
import os
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


def capture(page, url, data, mp4, stills, lossless):
    """Playwright engine: render one scene page to a silent MP4. Saves and lints the frame just before each next beat."""
    errors = open_scene(page, url, data)
    ext = "png" if lossless else "jpg"
    marks = beat_frames(data)
    encoder = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS),
         "-c:v", "png" if lossless else "mjpeg", "-i", "-", "-c:v", "libx264",
         "-preset", "medium" if lossless else "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(mp4)],
        stdin=subprocess.PIPE)
    lint = []
    for i in range(data["frames"]):
        page.evaluate("t => EV.seek(t)", i / FPS)
        shot = page.screenshot(type="png") if lossless else page.screenshot(type="jpeg", quality=90)
        encoder.stdin.write(shot)
        if i in marks:
            (stills / f"{marks[i]['id']}.{ext}").write_bytes(shot)
            lint += [f"{data['scene']}/{marks[i]['id']}: {issue}" for issue in page.evaluate("EV.lint()")]
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
    ext = "png" if quality == "1080p" else "jpg"
    for i, b in beat_frames(data).items():
        ffmpeg("-ss", f"{(i + 0.5) / FPS:.4f}", "-i", mp4, "-frames:v", 1, *(["-q:v", 2] if ext == "jpg" else []),
               stills / f"{b['id']}.{ext}")


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
    """Seconds per frame of the last 20 renders, per engine and quality, for the dashboard's estimate."""
    path = video / "build" / "timings.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        data = {}
    key = f"{engine}-{quality}"
    data[key] = (data.get(key, []) + [round(per_frame, 4)])[-20:]
    path.write_text(json.dumps(data))


def render_scene(browser, port, video, quality, data, engine, proj, where=""):
    """Render a scene unless the same inputs were rendered before. Returns (mp4, stills folder, lint).
    Prints "scene i/n" for each scene, cached or not, so the dashboard can show progress."""
    key = hashlib.sha256(json.dumps(data, sort_keys=True).encode())
    key.update(f"{engine} {os.environ.get('HYPERFRAMES_VERSION', '') if engine == 'hyperframes' else ''}".encode())
    key.update(f"three {os.environ.get('THREE_VERSION', '')}".encode())
    for path in [video / "scenes" / f"{data['scene']}.html", video / "style.css", video / "build" / "theme.css",
                 *sorted(WEB.glob("*")), *sorted((video / "assets").glob("**/*"))]:
        if path.is_file():
            key.update(path.read_bytes())
    base = video / "build" / "scenes" / f"{data['format']}-{quality}" / f"{data['scene']}-{key.hexdigest()[:12]}"
    mp4, lint_file = base.with_suffix(".mp4"), base.with_suffix(".lint.json")
    if lint_file.exists():
        print(f"  scene {where} {data['scene']}: cached", flush=True)
    else:
        started = time.monotonic()
        base.mkdir(parents=True, exist_ok=True)
        width, height = SIZE[data["format"]]
        context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=SCALE[quality],
                                      service_workers="block")  # a service worker's requests skip routes
        blocked = []
        guard(context, port, blocked)
        print(f"  scene {where} {data['scene']}: {data['duration']:.1f}s ({engine})", flush=True)
        i, _, n = where.partition("/")
        progress(video, f"Rendering {quality} {data['format']}", f"scene {i} of {n} ({data['scene']})")
        url = f"http://127.0.0.1:{port}/scenes/{data['scene']}.html"
        if engine == "hyperframes":
            lint = lint_marks(context.new_page(), url, data)
            hf_capture(video, proj, data, mp4, base, quality)
        else:
            lint = capture(context.new_page(), url, data, mp4, base, quality == "1080p")
        context.close()
        lint += [f"{data['scene']}: blocked a request to {u[:120]}: put the file in assets/" for u in dict.fromkeys(blocked)]
        lint_file.write_text(json.dumps(lint))
        record_timing(video, engine, quality, (time.monotonic() - started) / data["frames"])
    return mp4, base, json.loads(lint_file.read_text())


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
    spec = load(video)
    targets = formats(spec, fmt)
    for f in targets:
        gates.require(video, quality, f)
    fp = gates.fingerprint(video, "preview")
    spec, voice = narrate(video)
    name = moodboard_name(spec)
    (video / "build" / "theme.css").write_text(catalog.theme_css(name) if name else
                                               "/* no moodboard: this video's look: comes from base.css */\n")
    engine = spec.get("engine", "playwright")
    if engine not in ENGINES:
        raise SystemExit(f"engine: use {' or '.join(ENGINES)}, not {engine!r}")
    three_checks(video, spec, engine)
    webgl = WEBGL if three_scenes(video, spec) else []
    proj = hf_project(video, scene or "all") if engine == "hyperframes" else None
    from playwright.sync_api import sync_playwright
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Files, video=video.resolve(), three=three_on(spec)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--font-render-hinting=none", *webgl])
            for f in targets:
                shots, outs = render_format(browser, server.server_address[1], video, spec, voice, f, quality, part,
                                            scene, engine, proj)
                if quality == "1080p" and gates.fingerprint(video, "preview") != fp:  # edited while it rendered
                    for out in outs:
                        out.unlink(missing_ok=True)
                    raise SystemExit("A file changed during the 1080p render, so it no longer matches the approved "
                                     "preview. The 1080p files were removed: check the change and approve the preview again.")
                if not part and not scene:
                    gates.record_render(video, f, quality, fp)
                    if quality == "720p":
                        save_frames(video, f, shots)
            browser.close()
    finally:
        server.shutdown()
        progress(video, "done", "")
    if quality == "720p" and not part and not scene:
        storyboard.refresh(video, spec, voice)  # now with a frame per beat


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


def render_format(browser, port, video, spec, voice, fmt, quality, part, scene, engine, proj):
    """Render each part in one format. Returns every beat's review still, as (image, "scene/beat", show)."""
    many = len(spec["parts"]) > 1
    ext = "png" if quality == "1080p" else "jpg"
    every, outs = [], []
    todo = [(n, s) for n, p in enumerate(spec["parts"], 1) if not part or n == part
            for s in p["scenes"] if not scene or s["id"] == scene]
    for n, p in enumerate(spec["parts"], 1):
        chosen = [s for s in p["scenes"] if not scene or s["id"] == scene]
        if (part and n != part) or not chosen:
            continue
        print(f"render {fmt} {quality} part {n}", flush=True)
        clips, voices, cues, shots, lint, offset = [], [], [], [], [], 0.0
        for s in chosen:
            clips_voice = voice["scenes"][s["id"]]
            data = scene_data(spec, s, clips_voice, voice["gap"], fmt)
            mp4, stills, issues = render_scene(browser, port, video, quality, data, engine, proj,
                                               f"{todo.index((n, s)) + 1}/{len(todo)}")
            clips.append(mp4)
            lint += issues
            for b, clip in zip(data["beats"], clips_voice):
                voices.append((offset + b["start"], clip["wav"]))
                shots.append((stills / f"{b['id']}.{ext}", f"{s['id']}/{b['id']}", b["show"]))
            lines = cue_lines([w for b in data["beats"] for w in b["words"]], CAPTION_CHARS["line"][fmt])  # SRT and VTT
            cues += [(offset + c["start"], offset + c["end"], " ".join(w["w"] for w in c["words"])) for c in lines]
            offset += data["duration"]
        stem = f"{video.name}{f'-part{n}' if many else ''}{f'-{scene}' if scene else ''}-{fmt}-{quality}"
        out = assemble(video, stem, clips, voices, cues, offset)
        outs.append(out)
        print(f"DONE {out} ({seconds(out):.0f}s)")
        for i, (_, label, show) in enumerate(shots, 1):
            print(f"  frame {i:02d} {label}  show: {show}")
        for sheet in contact_sheets(video, stem, shots, fmt):
            print(f"  contact sheet: {sheet}")
        print("\n".join(f"LINT {x}" for x in lint) if lint else "  lint: clean")
        every += shots
    return every, outs
