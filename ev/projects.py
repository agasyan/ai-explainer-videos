"""Where a video lives. A new video is a project: projects/<YYYYMMDD>-<name>/, made when the work starts, and every
file of that work stays inside it: the research and source notes (research.md, sources/), a copied page, the script,
the scenes, and the renders. Videos made before projects existed stay in generated_videos/<slug>/ and keep working.
Both folders are gitignored: their content can be confidential.

Standard library only: the container (ev/cli.py), the host (ev/intake.py, ev/samples.py), and the dashboard use it.
"""
import os
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"
OLD = ROOT / "generated_videos"
NAME = re.compile(r"[a-z0-9][a-z0-9-]*")
DATED = re.compile(r"(\d{8})-([a-z0-9][a-z0-9-]*)")


def check(name):
    if not isinstance(name, str) or not NAME.fullmatch(name) or len(name) > 80:
        raise SystemExit(f"SLUG must be lowercase letters, digits, and dashes, for example how-dns-works, not {name!r}")
    return name


def today():
    """YYYYMMDD on the host. The Makefile passes EV_TODAY into Docker, whose clock runs in UTC."""
    value = os.environ.get("EV_TODAY", "")
    return value if re.fullmatch(r"\d{8}", value) else time.strftime("%Y%m%d")


def exact(slug, projects=None, old=None):
    """The folder named exactly `slug`, in projects/ and then generated_videos/, or None."""
    check(slug)
    for root in (projects or PROJECTS, old or OLD):
        if (root / slug).is_dir():
            return root / slug
    return None


def find(slug, projects=None, old=None):
    """The folder of an existing video: named exactly `slug`, else the newest project for that name
    (projects/<date>-<slug>, or <date>-<slug>-2 for a second one that day). None when there is none."""
    found = exact(slug, projects, old)
    if found:
        return found
    pattern = re.compile(rf"(\d{{8}})-{re.escape(slug)}(?:-(\d+))?")
    root = projects or PROJECTS
    matches = [(m[1], int(m[2] or 1), p) for p in (root.iterdir() if root.is_dir() else [])
               if p.is_dir() and (m := pattern.fullmatch(p.name))]
    return max(matches)[2] if matches else None


def new_id(name, projects=None, old=None):
    """A free project id for a new video: <today>-<name>, else <today>-<name>-2, -3, and so on. A name that starts
    with a date is a project id already (the dashboard makes it first): it is kept, and must be free."""
    check(name)
    if DATED.fullmatch(name):
        if exact(name, projects, old):
            raise SystemExit(f"projects/{name} already exists. Use another name.")
        return name
    base = f"{today()}-{name}"
    for n in range(1, 1000):
        candidate = base if n == 1 else f"{base}-{n}"
        if not exact(candidate, projects, old):
            return candidate
    raise SystemExit(f"Too many projects named {name} today")


def all_videos(projects=None, old=None):
    """Every video folder (with a script.yaml or a copied page), projects first."""
    out = []
    for root in (projects or PROJECTS, old or OLD):
        if root.is_dir():
            out += [d for d in sorted(root.iterdir()) if d.is_dir() and NAME.fullmatch(d.name)
                    and ((d / "script.yaml").is_file() or (d / "assets" / "page" / "index.html").is_file())]
    return out
