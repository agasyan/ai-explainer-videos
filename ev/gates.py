"""Approval checks: 2 stops. The intent (what the video says, to whom, how) before any script, and the 720p preview,
which is the final video and also covers the script and the voice. 1080p is an optional render after the preview.

Standard library only: ev (in Docker) and dashboard/server.py (on the host) both use it.
An approval stores a hash of what it covers. If that changes later, the approval stops counting.

- intent covers intent.md. A video with an intent.md makes no voice and no picture until it is approved
  (require_intent). A video made before the intent step has none, and skips it.
- plan covers script.yaml, except the top-level `format`, `look`, `moodboard`, `three`, `captions`, and `engine`
  lines and each beat's `hold` (timing, look, and renderer, which the preview check covers), plus research.md.
  Nobody stops for it: approving the preview approves the plan it was made from.
- preview covers script.yaml, style.css, scenes/, and assets/.

Approvals count only from a file named exactly approved.json (see exact()).
"""
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

STEPS = ("intent", "plan", "preview")
CHECK = {
    "intent": "Is the key message right? The viewers? The story, the look, and the length? What the video keeps and "
              "cuts? Anything missing? The script and the voice come next, and you check them with the preview.",
    "plan": "Right story for the viewer? Facts match the source? Each beat's words and picture make sense? "
            "Did you listen to build/narration.wav?",
    "preview": "Right story, and facts that match the source? Each frame shows its storyboard line? Nothing cut off, "
               "overlapping, or too small? Zero customer data or secrets? Right audience (internal or public)? "
               "This 720p video is the final video; 1080p is optional.",
}
# Keys the plan hash skips: these at the top level only (picks.moodboard is plan), and a beat's `hold` at any depth.
# ev.common.load() refuses a script where skipping these lines would hide more than the keys.
PLAN_FREE = ("format", "look", "moodboard", "three", "captions", "engine")
_NOT_PLAN = re.compile(rf"({'|'.join(PLAN_FREE)})\s*:|\s*hold\s*:")
_MOODBOARD = re.compile(r"moodboard:[ \t]*([a-z0-9][a-z0-9-]*)[ \t]*(#.*)?")
MOODBOARDS = Path(__file__).resolve().parent.parent / "moodboards"


def fingerprint(video, step):
    video, h = Path(video), hashlib.sha256()
    if step == "intent":
        path = video / "intent.md"
        h.update(path.read_bytes() if exact(path) else b"")
    elif step == "plan":
        path = video / "script.yaml"
        text = path.read_text() if path.exists() else ""
        h.update("\n".join(line.rstrip() for line in text.splitlines() if not _NOT_PLAN.match(line)).encode())
        if exact(video / "research.md"):  # approving the plan approves the facts; absent, the hash stays as before
            h.update(b"\0research.md\0" + (video / "research.md").read_bytes())
    else:
        files = [video / "script.yaml", video / "style.css", *moodboard_file(video),
                 *sorted((video / "scenes").glob("**/*")), *sorted((video / "assets").glob("**/*"))]
        for path in files:
            if path.is_file():
                label = path.relative_to(video) if path.is_relative_to(video) else Path("moodboards") / path.parent.name
                h.update(str(label).encode() + b"\0" + path.read_bytes() + b"\0")
    return h.hexdigest()[:16]


def declared_moodboard(text):
    """The value of the one plain `moodboard: <name>` line at the top level, else None. ev.common.load() refuses a
    script whose YAML reads another value (quoted, repeated, nested), so the hash and the render see one moodboard."""
    lines = re.findall(r"^moodboard\b.*$", text, re.M)
    match = _MOODBOARD.fullmatch(lines[0]) if len(lines) == 1 else None
    return match[1] if match else None


def moodboard_file(video):
    """The moodboard file of a video that names one: a change to the look changes the preview.
    An old `look:` video does not load a moodboard, so it has none."""
    path = Path(video) / "script.yaml"
    name = declared_moodboard(path.read_text() if path.exists() else "")
    file = MOODBOARDS / name / "moodboard.md" if name else None
    return [file] if file and file.is_file() else []


def exact(path):
    """True when the file exists under exactly this name and no other case of it. On a case-insensitive
    disk, Approved.json also opens as approved.json, so an agent could write approvals past a rule that
    names approved.json."""
    path = Path(path)
    try:
        names = os.listdir(path.parent)
    except FileNotFoundError:
        return False
    return path.name in names and sum(n.lower() == path.name.lower() for n in names) == 1


def read(video, name):
    path = Path(video) / name
    return json.loads(path.read_text()) if exact(path) else {}


def approved(video, step):
    entry = read(video, "approved.json").get(step)
    return bool(entry) and entry["hash"] == fingerprint(video, step)


def write(video, data):
    for other in os.listdir(video):  # a case variant would keep its name and hide the new approval
        if other.lower() == "approved.json" and other != "approved.json":
            os.remove(Path(video) / other)
    (Path(video) / "approved.json").write_text(json.dumps(data, indent=1) + "\n")


def preview_formats(video):
    """Formats with a full 720p render of the current files."""
    fp = fingerprint(video, "preview")
    return sorted(k.split("-")[0] for k, v in read(video, "build/rendered.json").items()
                  if k.endswith("-720p") and v == fp)


def has_intent(video):
    """True for a video that has the intent step: intent.md exists (templates/video/intent.md since 2026-11-18)."""
    return exact(Path(video) / "intent.md")


def require_intent(video):
    """Stop the voice and the picture until the intent is approved. A video with no intent.md skips the step."""
    if has_intent(video) and not approved(video, "intent"):
        name = Path(video).name
        raise SystemExit(f"Approval check: the intent is not approved, or intent.md changed after approval.\n"
                         f"Check intent.md, then: make approve SLUG={name} STEP=intent")


def ready(video, step):
    """True when the step's output exists and matches the current files."""
    video = Path(video)
    if step == "intent":
        return has_intent(video) and "(fill in" not in (video / "intent.md").read_text()
    if step == "plan":
        path = video / "script.yaml"
        return (path.exists() and "(fill in)" not in path.read_text()
                and read(video, "build/narration.json").get("source") == fingerprint(video, "plan"))
    return bool(preview_formats(video))


def status(video):
    """{step: "approved" | "ready" (waiting for your check) | "changed" (edited after approval) | "waiting"
    | "none" (intent only: a video made before the intent step)}. A plan that is "ready" needs no action:
    the preview check covers it."""
    approvals = read(video, "approved.json")
    return {step: "none" if step == "intent" and not has_intent(video)
            else "approved" if approved(video, step) else "changed" if step in approvals
            else "ready" if ready(video, step) else "waiting" for step in STEPS}


def require(video, quality, fmt):
    """Stop the optional 1080p render unless the preview is approved for this format. 720p needs no approval."""
    name = Path(video).name
    if quality != "1080p":
        return
    if not approved(video, "preview"):
        raise SystemExit(f"Approval check: the 720p preview is not approved, or a file changed after approval.\n"
                         f"Run make preview SLUG={name}, check it, then: make approve SLUG={name} STEP=preview")
    if fmt not in read(video, "approved.json")["preview"]["formats"]:
        raise SystemExit(f"Approval check: no approved {fmt} preview. "
                         f"Run make preview SLUG={name} FORMAT={fmt}, then approve it.")


def approve(video, step, expected=None):
    """Record an approval. `expected` is the fingerprint the person looked at (the dashboard sends it):
    if the files changed since, the approval would cover something nobody saw, so it is refused."""
    name = Path(video).name
    if step not in STEPS:
        raise SystemExit(f"STEP must be one of: {', '.join(STEPS)}")
    if expected is not None and expected != fingerprint(video, step):
        raise SystemExit("Changed since you looked: check again")
    if step != "intent":
        require_intent(video)
    with_preview = step == "preview" and not approved(video, "plan")
    if with_preview and not ready(video, "plan"):
        raise SystemExit(f"The plan changed after the preview: run make narrate and a full make preview SLUG={name}")
    if not ready(video, step):
        hint = {"intent": "fill in intent.md first", "plan": "run make narrate after the last edit"}.get(
            step, "run a full make preview after the last edit")
        raise SystemExit(f"Nothing to approve for {step}: {hint}. See make status SLUG={name}")
    data = read(video, "approved.json")
    stamp = {"by": os.environ.get("EV_USER") or os.environ.get("USER") or "unknown",
             "at": datetime.now(timezone.utc).isoformat(timespec="minutes")}
    data[step] = {"hash": fingerprint(video, step), **stamp}
    if step == "preview":
        data[step]["formats"] = preview_formats(video)
    if with_preview:  # the preview shows the plan in full, so this one check approves both
        data["plan"] = {"hash": fingerprint(video, "plan"), **stamp, "with": "preview"}
    data.pop("auto", None)  # an old consent from before the plan check became optional
    write(video, data)
    return data[step]


def record_render(video, fmt, quality, fp):
    """Remember which files a full render was made from."""
    data = read(video, "build/rendered.json")
    data[f"{fmt}-{quality}"] = fp
    (Path(video) / "build" / "rendered.json").write_text(json.dumps(data, indent=1))
