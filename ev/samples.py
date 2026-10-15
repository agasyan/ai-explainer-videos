"""Samples: committed example videos in videos/samples/<slug>/, sources only.

Standard library only: `ev new --sample` uses copy_sources() in Docker, and maintainers publish an approved
local video on the host with `make sample SLUG=<slug>` (python3 -I ev/samples.py <slug>).
"""
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "videos" / "samples"
LOCAL = ROOT / "generated_videos"
ID = re.compile(r"[a-z0-9][a-z0-9-]*")
SOURCES = ("script.yaml", "research.md", "style.css", "scenes/*.html", "assets/**/*")
PUBLISHED = SOURCES + ("storyboard.md", "frames/**/*.jpg")  # a sample also shows its storyboard and frames


def open_beneath(root_fd, rel):
    """Open root/rel for reading, refusing a symlink at every step. Checking first and copying later would leave
    a gap in which code in the container could swap a file for a link to, say, ~/.ssh/id_rsa."""
    fd = os.dup(root_fd)
    try:
        for part in rel.parts[:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return os.open(rel.parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
    except OSError as e:
        raise SystemExit(f"Refusing to copy {rel}: {e.strerror} (a symlink, or the file changed)") from None
    finally:
        os.close(fd)


def copy_sources(src, dst, patterns=SOURCES):
    """Copy the files that match `patterns` and nothing else: never build/, out/, or approvals, never a symlink."""
    src, dst = Path(src), Path(dst)
    for here, dirs, files in os.walk(src):
        for name in dirs + files:
            if (Path(here) / name).is_symlink():
                raise SystemExit(f"{src.name} has a symlink ({(Path(here) / name).relative_to(src)}): refusing to copy it")
    root_fd = os.open(src, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        dst.mkdir(parents=True)
        for pattern in patterns:
            for path in sorted(src.glob(pattern)):
                rel = path.relative_to(src)
                if path.is_symlink():
                    raise SystemExit(f"Refusing to copy {rel}: it became a symlink")
                if not path.is_file():
                    continue
                fd = open_beneath(root_fd, rel)
                with os.fdopen(fd, "rb") as source:
                    if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                        raise SystemExit(f"Refusing to copy {rel}: not a regular file")
                    (dst / rel).parent.mkdir(parents=True, exist_ok=True)
                    with open(dst / rel, "wb") as target:
                        shutil.copyfileobj(source, target)
    finally:
        os.close(root_fd)


def field(text, key):
    """A top-level `key: value` from script.yaml, read without a YAML library (the host has none)."""
    match = re.search(rf"^{key}:\s*(.+?)\s*(?:#.*)?$", text, re.M)
    return match[1].strip().strip("\"'") if match else ""


def publish(slug):
    sys.path.append(str(ROOT))  # last, after the standard library
    from ev import gates
    if not ID.fullmatch(slug):
        raise SystemExit("SLUG must be lowercase letters, digits, and dashes")
    src, dst = LOCAL / slug, SAMPLES / slug
    if not (src / "script.yaml").is_file():
        raise SystemExit(f"No video at generated_videos/{slug}/")
    if not gates.approved(src, "preview"):
        raise SystemExit(f"Approve the preview of {slug} first: a sample is a video someone checked")
    if dst.exists():
        shutil.rmtree(dst)
    copy_sources(src, dst, PUBLISHED)
    text = (src / "script.yaml").read_text()
    info = {"slug": slug, "title": field(text, "title") or slug, "format": field(text, "format") or "landscape",
            "moodboard": field(text, "moodboard") or field(text, "look") or "clean",
            "video_format": field(text, "video_format"), "three": field(text, "three") == "true"}
    (dst / "sample.json").write_text(json.dumps(info, indent=1) + "\n")
    print(f"DONE videos/samples/{slug}/: {sum(1 for p in dst.rglob('*') if p.is_file())} files. Review them, then commit.")


if __name__ == "__main__":
    publish(sys.argv[1] if len(sys.argv) > 1 else "")
