"""Host-side reads and writes inside a video folder.

Code in the container can change a video folder (projects/ and generated_videos/ are its only writable mounts), so
it can put a symlink where the host expects a folder or a file: projects/x/sources -> ~/.ssh, for example. Each
function here opens every step of the path with O_NOFOLLOW, starting from a folder the container cannot replace
(projects/ or generated_videos/ themselves, or a test's temporary folder). A symlink anywhere on the path makes
the call fail with OSError, instead of reading or writing a file outside the video.

Each function takes a video folder and a path inside it: safe.write(video, "sources/brief.md", text). The walk
starts at the video's parent folder. The relative path has no ".", "..", or empty part. Standard library only:
the host runs it (ev/intake.py, ev/vendor.py, the dashboard).
"""
import os
import stat
from pathlib import Path, PurePosixPath

DIR = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def parts(video, rel=None):
    """(the trusted start folder, [the video's name, then each part of rel])."""
    video = Path(video)
    names = [video.name] + ([] if rel is None else list(PurePosixPath(str(rel)).parts))
    if (rel is not None and PurePosixPath(str(rel)).is_absolute()) or any(x in ("", ".", "..") for x in names):
        raise OSError(f"not a plain path inside the video: {rel}")
    return video.parent, names


def walk(root, names, create=False):
    """A file descriptor for root/names... (a folder). Makes missing folders when create."""
    if create:
        os.makedirs(root, exist_ok=True)  # the trusted start (projects/): only its own path, not the walk below
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0))
    try:
        for name in names:
            if create:
                try:
                    os.mkdir(name, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
            nxt = os.open(name, DIR, dir_fd=fd)  # a symlink here: ELOOP or ENOTDIR
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


def regular(f, rel):
    st = os.fstat(f.fileno())
    if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
        f.close()
        raise OSError(f"{rel}: not a plain file")
    return f


def create(video, rel, append=False):
    """video/rel open for writing (binary), its folders made. Replaces the file, or adds to its end when append."""
    root, (*dirs, name) = parts(video, rel)
    fd = walk(root, dirs, create=True)
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | (os.O_APPEND if append else os.O_TRUNC)
        out = os.open(name, flags | getattr(os, "O_CLOEXEC", 0), 0o644, dir_fd=fd)
    finally:
        os.close(fd)
    return regular(os.fdopen(out, "ab" if append else "wb"), rel)


def write(video, rel, data, append=False):
    with create(video, rel, append) as f:
        f.write(data.encode() if isinstance(data, str) else data)


def read(video, rel):
    """video/rel as bytes. FileNotFoundError when it is missing."""
    root, (*dirs, name) = parts(video, rel)
    fd = walk(root, dirs)
    try:
        f = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0), dir_fd=fd)
    finally:
        os.close(fd)
    with regular(os.fdopen(f, "rb"), rel) as h:
        return h.read()


def is_dir(video, rel=None):
    """True when video/rel (or the video itself) is a folder reached with no symlink on the way."""
    try:
        os.close(walk(*parts(video, rel)))
        return True
    except OSError:
        return False


def mkdirs(video, rel=None):
    root, names = parts(video, rel)
    os.close(walk(root, names, create=True))


def remove_tree(video, rel):
    """Delete the folder video/rel and everything in it. A symlink inside is removed, never followed."""
    root, (*dirs, name) = parts(video, rel)
    try:
        fd = walk(root, dirs)
    except FileNotFoundError:
        return
    try:
        try:
            sub = os.open(name, DIR, dir_fd=fd)
        except FileNotFoundError:
            return
        try:
            empty(sub)
        finally:
            os.close(sub)
        os.rmdir(name, dir_fd=fd)
    finally:
        os.close(fd)


def empty(fd):
    for entry in list(os.scandir(fd)):
        if entry.is_dir(follow_symlinks=False):
            sub = os.open(entry.name, DIR, dir_fd=fd)
            try:
                empty(sub)
            finally:
                os.close(sub)
            os.rmdir(entry.name, dir_fd=fd)
        else:
            os.unlink(entry.name, dir_fd=fd)
