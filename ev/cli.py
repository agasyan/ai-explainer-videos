"""ev: the pipeline's command line. Runs inside Docker; use the Makefile.

1 intent   intent.md: key message, viewers, story, look, keep and cut  -> approve intent
2 plan     research, script.yaml, and `narrate`                     (no stop: the preview check covers it)
3 preview  scenes/*.html rendered at 720p with review frames        -> approve preview: the final video
4 1080p    optional: the same files at 1080p, when verdict.json says it is worth it and you want it
`make from-html` starts step 1 from an HTML page: vendor and sections draft the script and the scenes.
A new video is a project, projects/<YYYYMMDD>-<name>/ (ev/projects.py); commands take its name or its id.
"""
import argparse
import html
import json
import os
import shutil
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

from ev import gates, projects
from ev.common import MODELS, ROOT, SAMPLES, VENDOR, WHISPER, copy_template, ffmpeg, run, seconds
from ev.samples import copy_sources


def legacy_videos():
    """Video folders still in the old place, videos/<slug>/ (samples excluded)."""
    return sorted(d.name for d in (ROOT / "videos").glob("*")
                  if d.is_dir() and d.name != "samples" and (d / "script.yaml").exists())


def video(slug):
    """The folder of an existing video, from its name or its project id (ev/projects.py). A name finds its newest
    project, and says which one, so you never work on a project you did not mean."""
    found = projects.find(slug)
    if not found:
        sys.exit(f"No video named {slug} in projects/ or generated_videos/. Start one: make new SLUG={slug} TITLE=...")
    if found.name != slug:
        print(f"SLUG={slug} is {found.parent.name}/{found.name}", file=sys.stderr)
    return found


def exact_video(slug):
    """The folder of exactly this project id (or older slug). An approval and a 1080p render name the one video
    you checked: a name could point at a newer project with the same name."""
    found = projects.exact(slug)
    if not found:
        newest = projects.find(slug)
        sys.exit(f"Give the full project id, for example SLUG={newest.name}" if newest
                 else f"No video named {slug} in projects/ or generated_videos/")
    return found


def new(slug, title, sample=None):
    """Start a project: projects/<today>-<slug>/ (or -2, -3 the same day), from the template or a sample.
    The work of this video (research, source notes, script, scenes, renders) stays in that folder."""
    if sample and (not projects.NAME.fullmatch(sample) or not (SAMPLES / sample / "script.yaml").is_file()):
        sys.exit(f"No sample named {sample!r} in videos/samples/")
    made = projects.PROJECTS / slug  # the dashboard makes the folder first when it copies your files into sources/
    if projects.DATED.fullmatch(slug) and made.is_dir() and not (made / "script.yaml").exists() and not sample:
        pid, folder = slug, made
    else:
        pid = projects.new_id(slug)
        folder = projects.PROJECTS / pid
    if sample:
        copy_sources(SAMPLES / sample, folder)
        print(f"DONE projects/{pid}/ from the sample {sample}. Use SLUG={pid} in each next command. "
              f"Next: make narrate SLUG={pid}")
        return
    folder.mkdir(parents=True, exist_ok=True)
    copy_template(folder, title)
    print(f"DONE projects/{pid}/: intent.md, script.yaml, style.css, scenes/, sources/. Use SLUG={pid} in each next "
          f"command. Next (step 1): read the sources into sources/, fill in intent.md, then make approve SLUG={pid} "
          f"STEP=intent.")


def verdict(video):
    """build/verdict.json from the last full 720p render: is the optional 1080p render worth it?"""
    v = gates.read(video, "build/verdict.json")
    return v if isinstance(v.get("1080p"), str) else None


def status(video):
    st, approvals = gates.status(video), gates.read(video, "approved.json")
    notes = {"intent": {"ready": "READY for your check: intent.md", "changed": "CHANGED after approval: check again",
                        "waiting": "waiting: Claude fills in intent.md", "none": "none (a video made before the intent step)"},
             "plan": {"ready": "ready: the preview check covers it",
                      "changed": "CHANGED after approval: the preview check covers it", "waiting": "waiting"},
             "preview": {"ready": "READY for your check: this 720p video is the final",
                         "changed": "CHANGED after approval: check again", "waiting": "waiting"}}
    for i, step in enumerate(gates.STEPS, 1):
        a = approvals.get(step, {})
        with_preview = " with the preview" if a.get("with") == "preview" else ""
        print(f"{i} {step:<8} " + (f"approved{with_preview} {a['at']} by {a['by']}" if st[step] == "approved"
                                   else notes[step][st[step]]))
    v = verdict(video)
    hd = f" Verdict: {v['1080p']}. {v['why']}" if v else ""
    print("4 1080p    " + (f"optional: make video SLUG={video.name}.{hd}" if st["preview"] == "approved"
                           else "optional, after the preview check"))
    if st["intent"] in ("waiting",):
        print(f"next: read the sources into sources/, fill in intent.md, then ask: make approve SLUG={video.name} STEP=intent")
    elif st["intent"] in ("ready", "changed"):
        print(f"next: check the intent. {gates.CHECK['intent']}\n      make approve SLUG={video.name} STEP=intent")
    elif st["preview"] in ("ready", "changed"):
        print(f"next: check the preview. {gates.CHECK['preview']}\n      make approve SLUG={video.name} STEP=preview")
    elif st["preview"] == "approved":
        print(f"next: share the 720p video, or ask for 1080p.{hd}")
    elif st["plan"] in ("waiting", "changed") and not gates.ready(video, "plan"):
        print(f"next: fill in script.yaml, then make narrate SLUG={video.name}")
    else:
        print(f"next: write scenes/, check them with make stills SLUG={video.name} SCENE=<id>, "
              f"then make preview SLUG={video.name}")


def approve(video, step):
    a = gates.approve(video, step)
    print(f"APPROVED {step} for {video.name}: {a['hash']}, {a['at']}, {a['by']}")


def storyboard_command(video):
    """Rewrite storyboard.md from script.yaml and the current narration, and print it as JSON."""
    from ev import storyboard
    from ev.common import load
    narration = gates.read(video, "build/narration.json")
    if narration.get("source") != gates.fingerprint(video, "plan"):
        sys.exit(f"The narration is older than script.yaml: run make narrate SLUG={video.name} first")
    print(json.dumps(storyboard.refresh(video, load(video), narration), indent=1))


def reference(path):
    """Study a reference video: words and cuts per minute, and a contact sheet of 12 frames."""
    from PIL import Image

    from ev.voice import transcribe
    transcribe(path)
    length = seconds(path)
    words = len(path.with_suffix(".txt").read_text().split())
    log = run("ffmpeg", "-hide_banner", "-i", path, "-vf", "select='gt(scene,0.3)',showinfo", "-f", "null", "-",
              capture_output=True, text=True).stderr
    cuts = log.count("pts_time:")
    with tempfile.TemporaryDirectory() as tmp:
        shots = []
        for i in range(12):
            png = Path(tmp) / f"{i:02d}.png"
            ffmpeg("-ss", length * (i + 0.5) / 12, "-i", path, "-frames:v", 1, "-vf", "scale=480:-2", png)
            shots.append(Image.open(png).convert("RGB"))
        w, h = shots[0].size
        sheet = Image.new("RGB", (w * 4, h * 3))
        for i, shot in enumerate(shots):
            sheet.paste(shot.resize((w, h)), (i % 4 * w, i // 4 * h))
        out = path.with_suffix(".contact.png")
        sheet.save(out)
    print(f"DONE {path.name}: {length:.0f}s, {words / length * 60:.0f} words per minute, "
          f"{cuts / length * 60:.1f} cuts per minute\n  transcript: {path.with_suffix('.txt')}\n  contact sheet: {out}")


SWATCH = """<!doctype html><html data-format="landscape" data-look="{look}"><head><meta charset="utf-8">
<style>{css}
.sw {{ position: absolute; inset: 0; padding: 0 96px; display: flex; flex-direction: column; justify-content: center; gap: 36px; zoom: 1.45; }}
.chips {{ display: flex; gap: 14px; }} .chip {{ width: 96px; height: 96px; border-radius: var(--radius, 16px); border: 3px solid var(--line); }}
.ev-captions {{ position: static; }}
</style></head><body><div class="stage"><div class="sw">
<div class="small">{name}</div>
<div class="title" style="text-align: left">Aa: the title</div>
<div class="row" style="justify-content: flex-start">
  <div class="card"><div class="label">A card</div><div class="small">Body text, muted</div></div>
  <svg width="140" height="40"><path d="M 5 20 H 120 M 105 6 L 125 20 L 105 34" fill="none" stroke="var(--accent)" stroke-width="8"/></svg>
  <div class="card"><div class="label accent">Accent</div><div class="small accent-2">Second accent</div></div>
</div>
<div class="chips">{chips}</div>
<div class="ev-captions" data-style="pop"><span class="line"><span class="w on">Captions</span> <span class="w on key">key</span> <span class="w on now">word</span></span></div>
</div></div></body></html>"""


def catalog_command(write):
    """Check every moodboard and video format; with --write, render swatches and write both catalog.json files."""
    from ev import catalog
    bad = [(kind, name, p) for kind in ("moodboard", "video_format") for name in catalog.names(kind)
           for p in catalog.problems(kind, name)]
    for kind, name, problem in bad:
        print(f"FAIL {kind} {name}: {problem}")
    print(f"{'FAIL' if bad else 'ok  '} {len(catalog.names('moodboard'))} moodboards, "
          f"{len(catalog.names('video_format'))} video formats")
    if bad:
        sys.exit(1)
    if not write:
        return
    from playwright.sync_api import sync_playwright
    base = (ROOT / "ev" / "web" / "base.css").read_text()
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--font-render-hinting=none"])
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=0.5)
        for name in catalog.names("moodboard"):
            mood = catalog.moodboard(name)
            chips = "".join(f'<div class="chip" style="background: {mood["colors"][r]}"></div>' for r in catalog.COLOR_ROLES)
            look = {"math-dark": "dark"}.get(name, name if name in ("clean", "whiteboard") else "clean")
            page.set_content(SWATCH.format(css=base + catalog.theme_css(name), look=look, name=html.escape(name), chips=chips))
            page.evaluate("document.fonts.ready")
            page.screenshot(path=str(catalog.MOODBOARDS / name / "swatch.jpg"), type="jpeg", quality=85)
        browser.close()
    catalog.write_index()
    print(f"DONE swatches and catalog.json for {len(catalog.names('moodboard'))} moodboards")


def doctor():
    from ev.voice import hear, speak
    checks = [
        ("ffmpeg", shutil.which("ffmpeg")),
        ("whisper-cli", shutil.which("whisper-cli")),
        (f"whisper model {WHISPER.name}", WHISPER.exists()),
        ("Kokoro model", (MODELS / "kokoro-v1.0.onnx").exists()),
        ("rough.js, KaTeX", all((VENDOR / p).exists() for p in ("roughjs/bundled/rough.js", "katex/dist/katex.min.js"))),
    ]
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content("<p>ok</p>")
            checks.append((f"Chromium (playwright {version('playwright')})", page.inner_text("p") == "ok"))
            browser.close()
    except Exception as e:
        checks.append((f"Chromium: {e}", False))
    try:
        from ev.render import three_selftest
        with tempfile.TemporaryDirectory() as tmp:
            checks.append((f"three.js WebGL ({os.environ.get('THREE_VERSION', '?')}): same frame twice, same pixels",
                           three_selftest(Path(tmp))))
    except (Exception, SystemExit) as e:
        checks.append((f"three.js WebGL: {e}", False))
    try:
        from ev.render import hf_selftest
        hf = run("hyperframes", "--version", capture_output=True, text=True).stdout.strip().splitlines()[0]
        with tempfile.TemporaryDirectory() as tmp:
            checks.append((f"HyperFrames engine ({hf}): EV drives its frames", hf_selftest(Path(tmp))))
    except (Exception, SystemExit) as e:
        checks.append((f"HyperFrames engine: {e}", False))
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "t.wav"
        speak("Testing one two three.", wav, "af_heart", 1.0)
        heard = " ".join(h["w"] for h in hear(wav))
    checks.append((f"voice round trip, heard {heard!r}", "testing" in heard.lower()))
    for name, good in checks:
        print(f"{'ok  ' if good else 'FAIL'} {name}")
    sys.exit(0 if all(good for _, good in checks) else 1)


def main():
    ap = argparse.ArgumentParser(prog="ev")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new", help="start projects/<YYYYMMDD>-<slug> from templates/video or a sample")
    p.add_argument("slug")
    p.add_argument("--title", default="")
    p.add_argument("--sample", help="a folder name in videos/samples/")
    for name in ("narrate", "status", "storyboard", "vendor"):
        sub.add_parser(name).add_argument("video", type=video)
    p = sub.add_parser("approve")
    p.add_argument("video", type=exact_video)
    p.add_argument("step", choices=gates.STEPS)
    p = sub.add_parser("render")
    p.add_argument("video")  # a name for 720p; the exact id for 1080p (see main)
    p.add_argument("--quality", required=True, choices=["720p", "1080p"])
    p.add_argument("--format", choices=["landscape", "story", "both"])
    p.add_argument("--part", type=int)
    p.add_argument("--scene")
    p = sub.add_parser("stills", help="only the frame before each next beat, linted, with a contact sheet")
    p.add_argument("video", type=video)
    p.add_argument("--format", choices=["landscape", "story", "both"])
    p.add_argument("--part", type=int)
    p.add_argument("--scene")
    p = sub.add_parser("sections", help="make from-html: capture the page's sections and draft the video")
    p.add_argument("video", type=video)
    p.add_argument("--format", choices=["landscape", "story", "both"])
    sub.add_parser("reference").add_argument("file", type=Path)
    p = sub.add_parser("transcribe")
    p.add_argument("file", type=Path, nargs="?")
    p.add_argument("--sources", type=video, help="every recording in this project's sources/")
    p.add_argument("--model", default="base.en")
    sub.add_parser("voices", help="render voices/<voice>.m4a for the dashboard")
    sub.add_parser("doctor")
    sub.add_parser("test", help="run the unit tests in tests/")
    sub.add_parser("catalog", help="check moodboards and video formats").add_argument("--write", action="store_true")
    a = ap.parse_args()
    for old in legacy_videos():
        print(f"Move videos/{old} to generated_videos/{old}: local videos live there now.", file=sys.stderr)
    if a.cmd == "new":
        new(a.slug, a.title or a.slug, a.sample)
    elif a.cmd == "narrate":
        from ev.voice import narrate
        narrate(a.video)
    elif a.cmd == "status":
        status(a.video)
    elif a.cmd == "approve":
        approve(a.video, a.step)
    elif a.cmd == "stills":
        from ev.render import stills
        stills(a.video, a.format, a.part, a.scene)
    elif a.cmd == "vendor":
        from ev.vendor import vendor
        vendor(a.video)
    elif a.cmd == "sections":
        from ev.fromhtml import sections
        sections(a.video, a.format)
    elif a.cmd == "storyboard":
        storyboard_command(a.video)
    elif a.cmd == "render":
        from ev.render import render
        render(exact_video(a.video) if a.quality == "1080p" else video(a.video), a.quality, a.format, a.part, a.scene)
    elif a.cmd == "reference":
        reference(a.file)
    elif a.cmd == "transcribe":
        from ev.voice import transcribe, transcribe_sources
        if a.sources:
            transcribe_sources(a.sources, a.model)
        elif a.file:
            transcribe(a.file, a.model)
        else:
            sys.exit("Give FILE=<recording> or SLUG=<project id>")
    elif a.cmd == "voices":
        from ev.voice import voice_samples
        voice_samples(ROOT / "voices")
    elif a.cmd == "catalog":
        catalog_command(a.write)
    elif a.cmd == "test":
        import unittest
        result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover("tests", top_level_dir="."))
        sys.exit(0 if result.wasSuccessful() else 1)
    else:
        doctor()


if __name__ == "__main__":
    main()
