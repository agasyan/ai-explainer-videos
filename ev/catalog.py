"""Two committed catalogs, read-only to agents: moodboards (the look) and video formats (the structure).

moodboards/<name>/moodboard.md and video-formats/<name>/format.md hold YAML between --- lines, then prose.
A video picks one of each in script.yaml (`moodboard:`, `video_format:`). `make catalog` checks every entry,
renders each moodboard's swatch.jpg, and writes catalog.json for the dashboard (which has no YAML library).
"""
import json
import re
from pathlib import Path

import yaml

from ev.common import ID, ROOT

MOODBOARDS = ROOT / "moodboards"
FORMATS = ROOT / "video-formats"
ALIASES = {"dark": "math-dark"}  # the old `look:` names keep working
COLOR_ROLES = ("bg", "ink", "muted", "panel", "line", "accent", "accent-2", "good", "bad")
FONTS = {"Inter", "Noto Sans", "Noto Serif", "Noto Serif Display", "JetBrains Mono", "Caveat", "Liberation Sans Narrow"}
TREATMENTS = ("title", "big-number", "flow", "compare", "timeline", "quote", "stage-3d")
ENTERS = ("fade", "fade-up", "draw", "pop", "type")
EASE = re.compile(r"none|(power[0-4]|sine|expo|circ|back|elastic|bounce)\.(in|out|inOut)")
HEX = re.compile(r"#[0-9a-fA-F]{6}")
RGBA = re.compile(r"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9.]+)\s*\)")
MOOD_SECTIONS = ("## Overview", "## When to use", "## Treatments", "## Do and don't")
FORMAT_SECTIONS = ("## When to use", "## Example arc")


def front(path):
    """(YAML front matter as a dict, the prose after it)."""
    text = Path(path).read_text()
    match = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    if not match:
        raise SystemExit(f"{path}: needs YAML between --- lines at the top")
    return yaml.safe_load(match[1]) or {}, match[2]


def names(kind):
    folder = MOODBOARDS if kind == "moodboard" else FORMATS
    file = "moodboard.md" if kind == "moodboard" else "format.md"
    return sorted(d.name for d in folder.glob("*") if (d / file).is_file()) if folder.is_dir() else []


def moodboard(name):
    name = ALIASES.get(name, name)
    path = MOODBOARDS / name / "moodboard.md"
    if not ID.fullmatch(str(name)) or not path.is_file():
        raise SystemExit(f"No moodboard named {name!r}. Moodboards: {', '.join(names('moodboard'))}")
    return front(path)[0]


def video_format(name):
    path = FORMATS / str(name) / "format.md"
    if not ID.fullmatch(str(name)) or not path.is_file():
        raise SystemExit(f"No video format named {name!r}. Video formats: {', '.join(names('video_format'))}")
    return front(path)[0]


# ---------- color ----------

def rgb(value, over="#ffffff"):
    """(r, g, b) of #rrggbb, or of rgba(...) blended over `over`."""
    if HEX.fullmatch(value):
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    match = RGBA.fullmatch(value.strip())
    if not match:
        raise ValueError(f"not a color: {value}")
    base, alpha = rgb(over), float(match[4])
    return tuple(round(int(match[i + 1]) * alpha + base[i] * (1 - alpha)) for i in range(3))


def contrast(a, b):
    """WCAG 2 contrast ratio of two colors (b may be rgba, blended over a white page)."""
    def lum(c):
        ch = [x / 255 for x in c]
        ch = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in ch]
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


# ---------- checks ----------

def problems(kind, name):
    """Every way an entry breaks the schema; [] when it is fine."""
    path = (MOODBOARDS / name / "moodboard.md") if kind == "moodboard" else (FORMATS / name / "format.md")
    try:
        data, body = front(path)
    except SystemExit as e:
        return [str(e)]
    out = [] if data.get("name") == name else [f"name: must be {name!r}"]
    out += [f"description: one line" for _ in [0] if not isinstance(data.get("description"), str)]
    out += [f"fits: a list of topics" for _ in [0] if not isinstance(data.get("fits"), list) or not data.get("fits")]
    sections = MOOD_SECTIONS if kind == "moodboard" else FORMAT_SECTIONS
    out += [f"missing section {s!r}" for s in sections if s not in body]
    return out + (mood_problems(data) if kind == "moodboard" else format_problems(data))


def mood_problems(m):
    out = []
    colors = m.get("colors") or {}
    for role in COLOR_ROLES:
        if not HEX.fullmatch(str(colors.get(role, ""))):
            out.append(f"colors.{role}: a #rrggbb value")
    if out:
        return out
    bg = colors["bg"]
    for role, floor in (("ink", 4.5), ("muted", 3.0), ("accent", 3.0)):
        ratio = contrast(rgb(colors[role]), rgb(bg))
        if ratio < floor:
            out.append(f"colors.{role} {colors[role]} on bg {bg}: contrast {ratio}, needs {floor}")
    for role in ("display", "body", "mono"):
        if (m.get("typography") or {}).get(role) not in FONTS:
            out.append(f"typography.{role}: one of {sorted(FONTS)}")
    shape = m.get("shape") or {}
    if not (isinstance(shape.get("radius"), int) and 0 <= shape["radius"] <= 40):
        out.append("shape.radius: 0 to 40 (px)")
    if not (isinstance(shape.get("stroke"), int) and 1 <= shape["stroke"] <= 8):
        out.append("shape.stroke: 1 to 8 (px)")
    if shape.get("style") not in ("crisp", "rough"):
        out.append("shape.style: crisp or rough")
    motion = m.get("motion") or {}
    if not EASE.fullmatch(str(motion.get("ease", ""))):
        out.append("motion.ease: an EV ease such as power2.out")
    if not (isinstance(motion.get("duration"), (int, float)) and 0.2 <= motion["duration"] <= 1.5):
        out.append("motion.duration: 0.2 to 1.5 (s)")
    if not (isinstance(motion.get("stagger"), (int, float)) and 0 <= motion["stagger"] <= 0.5):
        out.append("motion.stagger: 0 to 0.5 (s)")
    if motion.get("enter") not in ENTERS:
        out.append(f"motion.enter: one of {ENTERS}")
    captions = m.get("captions") or {}
    try:
        cap_bg = rgb(str(captions.get("bg")), over=bg) if captions.get("bg") != "transparent" else rgb(bg)
        ratio = contrast(rgb(str(captions.get("ink"))), cap_bg)
        if ratio < 4.5:
            out.append(f"captions.ink on captions.bg: contrast {ratio}, needs 4.5")
        for role in ("now", "key"):
            rgb(str(captions.get(role)))
    except (ValueError, TypeError):
        out.append("captions: ink, bg, now, key as #rrggbb (bg may be rgba(...) or transparent)")
    three = m.get("three") or {}
    if not isinstance(three.get("fit"), bool):
        out.append("three.fit: true or false")
    treatments = m.get("treatments") or []
    if "title" not in treatments or not set(treatments) <= set(TREATMENTS):
        out.append(f"treatments: include title; only {TREATMENTS}")
    if "stage-3d" in treatments and not three.get("fit"):
        out.append("treatments: stage-3d needs three.fit: true")
    return out


def format_problems(f):
    out = []
    acts = f.get("acts")
    if not isinstance(acts, list) or not 2 <= len(acts) <= 6:
        return ["acts: 2 to 6 acts"]
    for i, act in enumerate(acts):
        beats = act.get("beats") if isinstance(act, dict) else None
        if not (isinstance(act, dict) and act.get("name") and act.get("goal") and isinstance(beats, list)
                and len(beats) == 2 and 1 <= beats[0] <= beats[1] <= 6):
            out.append(f"acts[{i}]: name, goal, and beats [min, max] from 1 to 6")
    scenes = f.get("scenes")
    if not (isinstance(scenes, list) and len(scenes) == 2 and 1 <= scenes[0] <= scenes[1] <= 12):
        out.append("scenes: [min, max] from 1 to 12")
    if not isinstance(f.get("ending"), str):
        out.append("ending: the win and one next action, as a sentence")
    return out


# ---------- use ----------

def theme_css(name):
    """CSS variables for a moodboard, on top of ev/web/base.css (:root:root beats base.css's [data-look] rules)."""
    m = moodboard(name)
    c, t, s, cap = m["colors"], m["typography"], m["shape"], m["captions"]
    lines = [f"  --{role}: {c[role]};" for role in COLOR_ROLES]
    lines += [f'  --font: "{t["body"]}", "Noto Color Emoji", sans-serif;', f'  --display: "{t["display"]}", "{t["body"]}", sans-serif;',
              f'  --mono: "{t["mono"]}", monospace;', f"  --radius: {s['radius']}px;", f"  --stroke: {s['stroke']}px;",
              f"  --cap-ink: {cap['ink']};", f"  --cap-bg: {cap['bg']};", f"  --cap-now: {cap['now']};", f"  --cap-key: {cap['key']};"]
    return f"/* moodboard {m['name']}: generated from moodboards/{m['name']}/moodboard.md */\n:root:root {{\n" + "\n".join(lines) + "\n}\n"


def index():
    """What the dashboard shows of both catalogs (written to catalog.json by `make catalog`)."""
    moods = []
    for name in names("moodboard"):
        m = moodboard(name)
        moods.append({"name": name, "description": m["description"], "fits": m["fits"], "three": m["three"]["fit"],
                      "colors": [m["colors"][r] for r in ("bg", "ink", "accent", "accent-2")]})
    formats = [{"name": n, **{k: video_format(n)[k] for k in ("description", "fits", "ending")},
                "acts": [a["name"] for a in video_format(n)["acts"]]} for n in names("video_format")]
    return {"moodboards": moods, "video_formats": formats}


def write_index():
    for folder, key in ((MOODBOARDS, "moodboards"), (FORMATS, "video_formats")):
        (folder / "catalog.json").write_text(json.dumps(index()[key], indent=1) + "\n")
