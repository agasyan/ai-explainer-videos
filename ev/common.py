"""Shared paths, sizes, and small helpers."""
import os
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MODELS = Path(os.environ.get("EV_MODELS", "/models"))
WHISPER = Path(os.environ.get("EV_WHISPER_MODEL", MODELS / "ggml-base.en.bin"))
VENDOR = Path(os.environ.get("EV_VENDOR", "/opt/vendor"))
VIDEOS = ROOT / "generated_videos"                       # local videos: gitignored, the only folder Docker may write
SAMPLES = ROOT / "videos" / "samples"                    # committed samples: read-only, copied with `ev new --sample`
SR = 24000                                                 # every voice clip is 24 kHz mono
FPS = 30
SIZE = {"landscape": (1920, 1080), "story": (1080, 1920)}  # page size in CSS px
SCALE = {"720p": 2 / 3, "1080p": 1.0}                      # device scale factor: same layout, fewer pixels
ID = re.compile(r"[a-z0-9][a-z0-9-]*")


def run(*cmd, **kw):
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def ffmpeg(*args):
    run("ffmpeg", "-loglevel", "error", "-y", *args)


def seconds(media):
    return float(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", media,
                     capture_output=True, text=True).stdout)


def norm(word):
    return re.sub(r"[^a-z0-9']", "", word.lower())


def _drop_hold(node):
    if isinstance(node, dict):
        return {k: _drop_hold(v) for k, v in node.items() if k != "hold"}
    return [_drop_hold(v) for v in node] if isinstance(node, list) else node


def _plan_part(spec, keys):
    """The YAML the plan hash covers: without the top-level `keys`, and without `hold` at any depth."""
    if not isinstance(spec, dict):
        return _drop_hold(spec)
    return _drop_hold({k: v for k, v in spec.items() if k not in keys})


def same_as_hash(text, spec):
    """True when the approval hash (ev/gates.py, which reads lines, not YAML) sees what YAML sees. The plan hash
    skips `format:`, `hold:` and the like; skipping must remove only those keys, never a line of a `say:` block."""
    from ev import gates
    kept = "\n".join(line for line in text.splitlines() if not gates._NOT_PLAN.match(line))
    try:
        stripped = yaml.safe_load(kept)
    except yaml.YAMLError:
        return False
    want = spec.get("moodboard") if isinstance(spec, dict) else None
    return (_plan_part(spec, gates.PLAN_FREE) == _plan_part(stripped, gates.PLAN_FREE)
            and (None if want is None else str(want)) == gates.declared_moodboard(text))


def progress(video, step, detail):
    """build/progress.json: what the pipeline is doing now, for the dashboard (it reads it while a job runs)."""
    import json
    import time
    try:
        (video / "build").mkdir(exist_ok=True)
        (video / "build" / "progress.json").write_text(json.dumps({"step": step, "detail": detail, "at": time.time()}))
    except OSError:
        pass  # progress is a nicety; never stop the work for it


def load(video):
    """Read script.yaml. A script without `parts:` is one part."""
    text = (video / "script.yaml").read_text()
    spec = yaml.safe_load(text)
    if not same_as_hash(text, spec):
        raise SystemExit("script.yaml: write hold, format, look, moodboard, captions, and engine as plain `key: value` "
                         "lines (moodboard once, at the top level, unquoted), and never start a line of a say or show "
                         "text with one of those words and a colon. The approval check reads those lines on their own.")
    if "parts" not in spec:
        spec["parts"] = [{"title": spec.get("title", video.name), "scenes": spec.pop("scenes")}]
    seen = set()
    for part in spec["parts"]:
        for scene in part["scenes"]:
            if not ID.fullmatch(str(scene["id"])):
                raise SystemExit(f"Scene id {scene['id']!r}: use lowercase letters, digits, and dashes "
                                 f"(it names scenes/<id>.html)")
            if scene["id"] in seen:
                raise SystemExit(f"Scene id {scene['id']!r} is used twice: each scene needs its own id")
            seen.add(scene["id"])
            beats = [str(b.get("id", i)) for i, b in enumerate(scene["beats"])]
            for bid in beats:
                if not ID.fullmatch(bid):
                    raise SystemExit(f"Beat id {scene['id']}/{bid!r}: use lowercase letters, digits, and dashes "
                                     f"(it names frames/<format>/{scene['id']}/<id>.jpg)")
            if len(set(beats)) != len(beats):
                raise SystemExit(f"Scene {scene['id']}: two beats have the same id")
    return spec


def formats(spec, fmt=None):
    """The formats to render: the --format option, else the script's `format`."""
    fmt = fmt or spec.get("format", "landscape")
    return ["landscape", "story"] if fmt == "both" else [fmt]
