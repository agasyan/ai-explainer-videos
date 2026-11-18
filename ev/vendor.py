"""make from-html, step 2: copy the scripts, styles, and fonts a page loads from the CDNs in HOSTS into
assets/page/vendor/, and point the page at the copies, so the capture and the render need no network.

Runs on the host, with your Mac's network and DNS, like the intake before it (ev/intake.py): Colima's DNS can stop
answering inside its VM. Standard library only. It sends GET requests for those files only: the page's own text
never leaves the machine, and no page code runs here. A redirect is followed only to an https host on the list.
"""
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # last, so a stray file cannot shadow the standard library
from ev import projects  # noqa: E402 (standard library only)

HOSTS = ("cdnjs.cloudflare.com", "cdn.jsdelivr.net", "unpkg.com", "cdn.tailwindcss.com", "code.jquery.com",
         "fonts.googleapis.com", "fonts.gstatic.com")
# Google Fonts sends woff2 files only to a browser it knows.
AGENT = "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
MAX_FILE = 15 << 20
TAG = re.compile(r"<(script|link)\b[^>]*>", re.I)
STYLE = re.compile(r"(<style\b[^>]*>)(.*?)(</style>)", re.I | re.S)
CSS_URL = re.compile(r"""url\(\s*(["']?)([^"')]+?)\1\s*\)|@import\s+(["'])([^"']+)\3""", re.I)
LINKS = ("stylesheet", "preload", "modulepreload", "icon")


def attr(name):
    return re.compile(rf"""\s{name}\s*=\s*(["'])(.*?)\1""", re.I | re.S)


def page_of(video):
    page = video / "assets" / "page" / "index.html"
    if not page.is_file():
        raise SystemExit(f"No page in {video}/assets/page/: run make from-html SLUG={video.name} FILE=<page.html>")
    return page


def allowed(url):
    parts = urllib.parse.urlsplit(url)
    return parts.scheme == "https" and parts.hostname in HOSTS


def local_path(folder, url, css):
    """vendor/<host>/<path>. A URL with a query (Google Fonts CSS) or no extension gets a short hash in its name."""
    parts = urllib.parse.urlsplit(url)
    names = [re.sub(r"[^A-Za-z0-9._@+-]", "_", p) for p in parts.path.split("/") if p not in ("", ".", "..")] or ["index"]
    stem, ext = os.path.splitext(names[-1])
    if parts.query or not ext:
        ext = ext or (".css" if css else ".bin")
        names[-1] = f"{stem}-{hashlib.sha1(url.encode()).hexdigest()[:8]}{ext}"
    return folder.joinpath(parts.hostname, *names)


class Redirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to an allowed URL, checked before the next request is sent, at most 5 hops."""
    max_redirections = 5

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise urllib.error.URLError(f"redirect to a host not on the list: {urllib.parse.urlsplit(newurl).hostname}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = urllib.request.build_opener(Redirects)


class Vendor:
    """Downloads allowed URLs once each; rewrites url() and @import inside CSS to the local copies."""

    def __init__(self, folder):
        self.folder, self.done, self.notes = folder, {}, []

    def fetch(self, url, depth=0):
        if url in self.done:
            return self.done[url]
        try:
            with OPENER.open(urllib.request.Request(url, headers={"User-Agent": AGENT}), timeout=30) as r:
                kind, data = r.headers.get_content_type(), r.read(MAX_FILE + 1)
        except (urllib.error.URLError, OSError, ValueError) as e:
            self.notes.append(f"not copied: {url} ({getattr(e, 'reason', e)})")
            self.done[url] = None
            return None
        if len(data) > MAX_FILE:
            self.notes.append(f"not copied: {url} is over 15 MB")
            self.done[url] = None
            return None
        css = kind == "text/css" or urllib.parse.urlsplit(url).path.endswith(".css")
        target = local_path(self.folder, url, css)
        self.done[url] = target  # before the CSS pass, so a loop of @imports stops here
        if css and depth < 3:
            data = self.css(data.decode("utf-8", "replace"), url, target, depth + 1).encode()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    def css(self, text, base, at, depth):
        def swap(m):
            ref = (m[2] or m[4] or "").strip()
            if not ref or ref.lower().startswith(("data:", "#", "%23", "about:")):  # %23: an encoded #fragment
                return m[0]
            url = urllib.parse.urljoin(base, ref)
            got = self.fetch(url, depth) if allowed(url) else None
            return m[0].replace(ref, os.path.relpath(got, at.parent)) if got else m[0]
        return CSS_URL.sub(swap, text)


def vendor(video):
    """Copy the page's CDN files and point the page at them. A second run finds nothing to fetch."""
    page = page_of(video)
    html = page.read_text(errors="replace")
    v = Vendor(page.parent / "vendor")

    def tag(m):
        text, name = m[0], m[1].lower()
        found = attr("src" if name == "script" else "href").search(text)
        if not found:
            return text
        if name == "link":
            rel = attr("rel").search(text)
            if not rel or not any(k in rel[2].lower() for k in LINKS):
                return text
        raw = found[2].strip()
        if not re.match(r"(https?:)?//", raw, re.I):
            return text  # a local file: ev/intake.py copied it
        url = "https:" + raw if raw.startswith("//") else raw
        if not allowed(url):
            v.notes.append(f"not copied (host not on the list): {urllib.parse.urlsplit(url).hostname} in a <{name}>")
            return text
        got = v.fetch(url)
        if not got:
            return text
        text = text[:found.start(2)] + os.path.relpath(got, page.parent) + text[found.end(2):]
        # A copied script keeps its bytes, so its integrity hash still guards it. A CSS file whose url()s now point
        # at local copies has new bytes, so its old hash would block it.
        return attr("integrity").sub("", text) if got.suffix == ".css" else text

    html = TAG.sub(tag, html)
    html = STYLE.sub(lambda m: m[1] + v.css(m[2], "https://page.invalid/", page, 1) + m[3], html)
    page.write_text(html)
    copied = {u: str(p.relative_to(page.parent)) for u, p in v.done.items() if p}
    if copied:
        (page.parent / "vendor").mkdir(exist_ok=True)
        (page.parent / "vendor" / "vendor.json").write_text(json.dumps(copied, indent=1) + "\n")
    print(f"DONE vendor: {len(copied)} file{'s' if len(copied) != 1 else ''} copied into assets/page/vendor/")
    for note in dict.fromkeys(v.notes):
        print(f"  NOTE {note}")


def main(argv):
    if len(argv) != 1:
        raise SystemExit("Usage: python3 -I ev/vendor.py <project id>")
    folder = projects.exact(argv[0])
    if not folder:
        raise SystemExit(f"No project {argv[0]} in projects/ or generated_videos/")
    vendor(folder)


if __name__ == "__main__":
    main(sys.argv[1:])
