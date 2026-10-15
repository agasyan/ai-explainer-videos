"""ev: the pipeline's command line. Runs inside Docker; use the Makefile.

1 plan     script.yaml (brief + storyboard) and `narrate`   -> approve plan
2 preview  scenes/*.html rendered at 720p with review frames -> approve preview
3 final    the same files rendered at 1080p
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

from ev import gates
from ev.common import ID, MODELS, ROOT, SAMPLES, VENDOR, VIDEOS, WHISPER, ffmpeg, run, seconds
from ev.samples import copy_sources


def legacy_videos():
    """Video folders still in the old place, videos/<slug>/ (samples excluded)."""
    return sorted(d.name for d in (ROOT / "videos").glob("*")
                  if d.is_dir() and d.name != "samples" and (d / "script.yaml").exists())


def new(slug, title, sample=None):
    if not ID.fullmatch(slug):
        sys.exit("SLUG must be lowercase letters, digits, and dashes, for example: how-dns-works")
    folder = VIDEOS / slug
    consent = None
    if folder.exists():  # the dashboard makes the folder first when you tick auto: it holds only your consent
        if sorted(p.name for p in folder.iterdir()) != ["approved.json"]:
            sys.exit(f"generated_videos/{slug} already exists. Use another slug.")
        consent = {k: v for k, v in gates.read(folder, "approved.json").items() if k == "auto"}  # nothing else
        shutil.rmtree(folder)
    if sample:
        if not ID.fullmatch(sample) or not (SAMPLES / sample / "script.yaml").is_file():
            sys.exit(f"No sample named {sample!r} in videos/samples/")
        copy_sources(SAMPLES / sample, folder)
        if consent:
            gates.write(folder, consent)
        print(f"DONE generated_videos/{slug}/ from the sample {sample}. Next: make narrate SLUG={slug}")
        return
    shutil.copytree(ROOT / "templates" / "video", folder)
    for path in folder.rglob("*"):
        if path.is_file():
            value = json.dumps(title) if path.suffix == ".yaml" else html.escape(title)
            path.write_text(path.read_text().replace("__TITLE__", value))
    if consent:
        gates.write(folder, consent)
    print(f"DONE generated_videos/{slug}/: script.yaml, style.css, scenes/. Next: fill in script.yaml (step 1).")


def status(video):
    st, approvals = gates.status(video), gates.read(video, "approved.json")
    notes = {"ready": "READY for your check", "changed": "CHANGED after approval: check again", "waiting": "waiting"}
    if st["plan"] == "auto":
        a = approvals["auto"]
        notes["auto"] = f"AUTO: you check it with the preview (consent {a['at']} by {a['by']})"
    for i, step in enumerate(gates.STEPS, 1):
        a = approvals.get(step, {})
        with_preview = " with the preview" if a.get("with") == "preview" else ""
        print(f"{i} {step:<8} " + (f"approved{with_preview} {a['at']} by {a['by']}" if st[step] == "approved"
                                   else notes[st[step]]))
    print("3 final    " + ("unlocked: make video SLUG=" + video.name if st["preview"] == "approved"
                           else "locked until the preview is approved"))
    todo = next((s for s in gates.STEPS if st[s] not in ("approved", "auto")), None)
    if todo and gates.ready(video, todo):
        print(f"next: check the {todo}. {gates.CHECK[todo]}\n      make approve SLUG={video.name} STEP={todo}")
    elif todo == "plan":
        print(f"next: fill in script.yaml, then make narrate SLUG={video.name}")
    elif todo == "preview":
        print(f"next: write scenes/, then make preview SLUG={video.name}")


def approve(video, step):
    a = gates.approve(video, step)
    print(f"APPROVED {step} for {video.name}: {a['hash']}, {a['at']}, {a['by']}")


def auto(video):
    if not (video / "script.yaml").is_file():
        sys.exit(f"No video at {video}: run make new first")
    a = gates.consent(video)
    print(f"AUTO until the preview for {video.name}: {a['at']}, {a['by']}. The plan stop is skipped; "
          f"you check the plan and the 720p preview together.")


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
    p = sub.add_parser("new", help="start generated_videos/<slug> from templates/video or a sample")
    p.add_argument("slug")
    p.add_argument("--title", default="")
    p.add_argument("--sample", help="a folder name in videos/samples/")
    for name in ("narrate", "status", "auto", "storyboard"):
        sub.add_parser(name).add_argument("video", type=Path)
    p = sub.add_parser("approve")
    p.add_argument("video", type=Path)
    p.add_argument("step", choices=gates.STEPS)
    p = sub.add_parser("render")
    p.add_argument("video", type=Path)
    p.add_argument("--quality", required=True, choices=["720p", "1080p"])
    p.add_argument("--format", choices=["landscape", "story", "both"])
    p.add_argument("--part", type=int)
    p.add_argument("--scene")
    for name in ("reference", "transcribe"):
        p = sub.add_parser(name)
        p.add_argument("file", type=Path)
        if name == "transcribe":
            p.add_argument("--model", default="base.en")
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
    elif a.cmd == "auto":
        auto(a.video)
    elif a.cmd == "storyboard":
        storyboard_command(a.video)
    elif a.cmd == "render":
        from ev.render import render
        render(a.video, a.quality, a.format, a.part, a.scene)
    elif a.cmd == "reference":
        reference(a.file)
    elif a.cmd == "transcribe":
        from ev.voice import transcribe
        transcribe(a.file, a.model)
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
