"""Intake for make from-html: copy one HTML page, and the local files it links, into a project:
projects/<YYYYMMDD>-<name>/assets/page/ (ev/projects.py). The page becomes assets/page/index.html.

Runs on the host, before Docker, because the page can be anywhere on your disk and the container sees only this
repo. The dashboard calls copy() for its New video form; `make from-html FILE=...` runs this file.
Standard library only. Copies only regular files: never a symlink, never a file outside the page's own folder,
and only the file types a page loads (KINDS). Links to other sites stay as they are: `ev vendor` copies the
scripts, styles, and fonts from the CDNs it allows, and the render blocks everything else.
"""
import json
import os
import re
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # last, so a stray file cannot shadow the standard library
from ev import projects  # noqa: E402 (standard library only)

PAGES = (".html", ".htm")
KINDS = {".css", ".js", ".mjs", ".json", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif", ".ico",
         ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".webm"}
MAX_FILE, MAX_TOTAL = 20 << 20, 200 << 20
# src=, href=, poster= values, and url(...) in CSS. Only relative paths count: no scheme, no //, no /, no #.
REF = re.compile(r"""(?:\b(?:src|href|poster)\s*=\s*["']([^"']+)["'])|(?:url\(\s*["']?([^"')]+)["']?\s*\))""", re.I)


def page_path(file, base=None):
    """The page as an absolute path. A relative path is read from `base` (the dashboard's first extra folder); with
    no base it is refused, because this tool's own folder is never where the page is. Refuses anything but a regular
    .html or .htm file of 20 MB or less."""
    path = Path(os.path.expanduser(str(file).strip()))
    if not path.is_absolute():
        if not base:
            raise SystemExit(f"{file} is a relative path: give the full path (it starts with / or ~), or put its "
                             f"folder in More options, Extra folders")
        path = Path(os.path.expanduser(str(base))) / path
    path = Path(os.path.realpath(path))
    if path.suffix.lower() not in PAGES:
        raise SystemExit(f"FILE must be an .html or .htm page, not {path.name}")
    try:
        info = path.stat()
    except OSError:
        raise SystemExit(f"No page at {path}") from None
    if not stat.S_ISREG(info.st_mode):
        raise SystemExit(f"Not a file: {path}")
    if info.st_size > MAX_FILE:
        raise SystemExit(f"{path.name} is over 20 MB")
    return path


def local_refs(text):
    """Relative paths the page links: [str], without ?query or #fragment, each once, in page order."""
    out = []
    for match in REF.finditer(text):
        ref = (match[1] or match[2] or "").strip()
        if not ref or re.match(r"^[a-z][a-z0-9+.-]*:", ref, re.I) or ref.startswith(("//", "/", "#")):
            continue
        ref = ref.split("#")[0].split("?")[0]
        if ref and ref not in out:
            out.append(ref)
    return out


def copy_file(src, dst):
    """Copy one regular file, refusing a symlink at the last step (O_NOFOLLOW)."""
    fd = os.open(src, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("not a regular file")
        dst.parent.mkdir(parents=True, exist_ok=True)
        with os.fdopen(fd, "rb", closefd=False) as f, open(dst, "wb") as out:
            shutil.copyfileobj(f, out)
    finally:
        os.close(fd)


def copy(slug, file, base=None, root=None):
    """Copy the page into a project. A name starts a new project, projects/<today>-<name>/. An existing project id
    refreshes that project's page (its script and scenes stay); it must be a from-html project.
    Returns (project folder, page path, [copied relative paths], [skipped refs with the reason])."""
    projects.check(slug)
    root = root or projects.PROJECTS
    src = page_path(file, base)
    if (root / slug).is_dir():
        folder = root / slug
        if not (folder / "assets" / "page").is_dir():
            raise SystemExit(f"projects/{slug} is not a from-html project. Use a new name.")
    else:
        folder = root / projects.new_id(slug, projects=root)
    page = folder / "assets" / "page"
    text = src.read_text(errors="replace")
    root = src.parent
    copied, skipped, total = [], [], src.stat().st_size
    shutil.rmtree(page, ignore_errors=True)
    copy_file(src, page / "index.html")
    for ref in local_refs(text):
        target = Path(os.path.realpath(root / ref))
        if not target.is_relative_to(root):
            skipped.append(f"{ref}: outside the page's folder")
        elif target.suffix.lower() not in KINDS:
            skipped.append(f"{ref}: not a file type a page loads")
        elif not target.is_file():
            skipped.append(f"{ref}: no such file")
        elif target.stat().st_size > MAX_FILE or total + target.stat().st_size > MAX_TOTAL:
            skipped.append(f"{ref}: too large (20 MB per file, 200 MB in all)")
        else:
            rel = target.relative_to(root)
            try:
                copy_file(target, page / rel)
            except OSError as e:
                skipped.append(f"{ref}: {e.strerror or e}")
                continue
            total += target.stat().st_size
            copied.append(str(rel))
    (page / "source.json").write_text(json.dumps({
        "file": src.name, "copied": copied, "skipped": skipped,
        "at": datetime.now(timezone.utc).isoformat(timespec="minutes")}, indent=1) + "\n")
    (folder / "sources").mkdir(exist_ok=True)
    return folder, src, copied, skipped


def main(argv):
    if len(argv) != 2:
        raise SystemExit("Usage: python3 -I ev/intake.py <name or project id> <page.html>")
    folder, src, copied, skipped = copy(argv[0], argv[1])
    say = lambda text: print(text, file=sys.stderr)  # noqa: E731 (stdout carries only the project id, for make)
    say(f"Copied {src.name} and {len(copied)} linked file{'s' if len(copied) != 1 else ''} into "
        f"projects/{folder.name}/assets/page/. Use SLUG={folder.name} in each next command.")
    for line in skipped:
        say(f"  NOTE not copied: {line}")
    print(folder.name)


if __name__ == "__main__":
    main(sys.argv[1:])
