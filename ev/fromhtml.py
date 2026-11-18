"""make from-html, inside Docker: an HTML page becomes a source of a project. The host first copies the page to
assets/page/index.html (ev/intake.py) and its CDN files to assets/page/vendor/ (ev/vendor.py). Then sections():

- opens the page with no network, freezes it, finds its sections (<section> elements, else the blocks between <h2>
  headings, else the whole page), and captures each one as a PNG per format, at 2x;
- writes build/sections.json (heading, text, size, and the boxes of tables, charts, and code) and sources/page.md
  (the page's text, section by section), and adds the page to sources/index.md;
- starts the project from templates/video (intent.md, script.yaml, style.css, scenes/) where files are missing;
- writes scenes/page-<id>.html for each section: a ready scene that shows that part of the page, for a beat that
  needs the evidence (zoom into a table with p.zoom). A whole page tour is an option, not the default.

The agent then reads the page like any source and re-explains it in its own story: intent first, then the script.
"""
import base64
import json
import shutil

from ev.common import SIZE, copy_template, formats, load
from ev.vendor import page_of, vendor  # noqa: F401 (vendor: step 2, on the host; also `ev vendor` in Docker)

# ---------- 2. sections (no network) ----------

FREEZE = """async () => {
  document.querySelectorAll("img[loading]").forEach(i => { i.loading = "eager"; });
  document.querySelectorAll("details").forEach(d => { d.open = true; });
  const style = document.createElement("style");
  style.textContent = "*,*::before,*::after{animation-duration:0s!important;animation-delay:0s!important;" +
    "animation-iteration-count:1!important;transition:none!important;caret-color:transparent!important;" +
    "scroll-behavior:auto!important}";
  document.head.append(style);
  const frame = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  for (let y = 0; y < document.documentElement.scrollHeight; y += innerHeight * 0.8) { scrollTo(0, y); await frame(); }
  scrollTo(0, 0);
  for (const e of document.querySelectorAll("body *")) {
    const p = getComputedStyle(e).position;
    if (p === "fixed") e.style.setProperty("visibility", "hidden", "important");
    else if (p === "sticky") e.style.setProperty("position", "relative", "important");
  }
  await Promise.all([...document.images].map(i => (i.complete ? 0 : i.decode().catch(() => 0))));
  await document.fonts.ready;
  await frame();
}"""

FIND = """(limit) => {
  const clean = t => (t || "").replace(/\\s+/g, " ").trim();
  const visible = e => { const s = getComputedStyle(e); return s.display !== "none" && s.visibility !== "hidden"; };
  const shown = e => { const r = e.getBoundingClientRect(); return visible(e) && r.width >= 120 && r.height >= 40; };
  const box = e => { const r = e.getBoundingClientRect();
    return { x: Math.max(0, Math.floor(r.left + scrollX)), y: Math.max(0, Math.floor(r.top + scrollY)),
             w: Math.ceil(r.width), h: Math.ceil(r.height) }; };
  const solid = c => c && c !== "transparent" && !/rgba\\(.*,\\s*0\\)$/.test(c);
  const pageBg = [document.body, document.documentElement].map(e => getComputedStyle(e).backgroundColor).find(solid)
    || "rgb(255, 255, 255)";
  const bgOf = e => { for (let x = e; x; x = x.parentElement) { const c = getComputedStyle(x).backgroundColor;
    if (solid(c)) return c; } return pageBg; };
  const root = document.querySelector("main, article, [role=main]") || document.body;
  let kind, items;
  const sections = [...document.querySelectorAll("section")].filter(e => shown(e) && !e.parentElement.closest("section"));
  const h2s = [...root.querySelectorAll("h2")].filter(shown);
  if (sections.length >= 2) {
    kind = "section";
    items = sections.map(e => ({ ...box(e), el: e, start: e,
      heading: clean((e.querySelector("h1, h2, h3, h4") || {}).innerText), text: clean(e.innerText), bg: bgOf(e) }));
  } else if (h2s.length >= 2) {
    kind = "h2";
    const rb = box(root);
    items = h2s.map((h, i) => {
      const top = Math.max(0, box(h).y - 24);
      const end = i + 1 < h2s.length ? box(h2s[i + 1]).y - 24 : rb.y + rb.h;
      const range = document.createRange();
      range.setStartBefore(h);
      if (i + 1 < h2s.length) range.setEndBefore(h2s[i + 1]); else range.setEndAfter(root.lastChild || root);
      return { x: rb.x, y: top, w: rb.w, h: end - top, start: h, heading: clean(h.innerText), text: clean(range.toString()),
               bg: bgOf(h) };
    });
  } else {
    kind = "page";
    items = [{ ...box(root), start: root, heading: clean(document.title), text: clean(root.innerText), bg: pageBg }];
  }
  items = items.filter(it => it.h >= 80);
  if (kind !== "page" && items.length && items[0].y > 100) {  // the title area above the first section
    const range = document.createRange();
    range.setStartBefore(document.body.firstChild || document.body);
    range.setEndBefore(items[0].start);
    const h1 = document.querySelector("h1");
    // Crop to what shows above the first section: visible text and pictures, not a full-width band or a hidden nav.
    const seen = [...document.body.querySelectorAll("*")].filter(e => range.intersectsNode(e) && visible(e)
      && getComputedStyle(e).visibility === "visible"  // a hidden fixed nav's children inherit "hidden"
      && (/^(IMG|SVG|CANVAS|VIDEO)$/i.test(e.tagName) || [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())))
      .map(box).filter(b => b.w > 0 && b.h > 0 && b.y < items[0].y);
    if (seen.length) {
      const pad = 32, left = Math.max(0, Math.min(...seen.map(b => b.x)) - pad);
      const top = Math.max(0, Math.min(...seen.map(b => b.y)) - pad);
      const right = Math.min(document.documentElement.clientWidth, Math.max(...seen.map(b => b.x + b.w)) + pad);
      const bottom = Math.min(items[0].y, Math.max(...seen.map(b => b.y + b.h)) + pad, top + 1600);
      items.unshift({ x: left, y: top, w: right - left, h: bottom - top, title: true,
        heading: clean(h1 ? h1.innerText : document.title), text: clean(range.toString()), bg: pageBg });
    }
  }
  const PARTS = "h3, table, svg, pre, img, figure, blockquote";
  // Text the page does not show at first (closed tabs, hidden panels): the captures miss it, page.md keeps it.
  const hidden = [];
  for (const e of document.body.querySelectorAll("*")) {
    if (/^(script|style|template|noscript|svg)$/i.test(e.tagName) || getComputedStyle(e).display !== "none") continue;
    if (e.parentElement && e.parentElement.closest("[data-ev-hidden]")) continue;
    const text = clean(e.textContent);
    if (text.length < 200) continue;
    e.setAttribute("data-ev-hidden", "");
    const name = e.getAttribute("aria-label") || (e.querySelector("h1, h2, h3, h4") || {}).textContent || e.id || e.tagName;
    hidden.push({ label: clean(name).slice(0, 80), text: text.slice(0, 8000) });
  }
  return { kind, title: clean(document.title), bg: pageBg, height: document.documentElement.scrollHeight,
    hidden: hidden.slice(0, 12),
    sections: items.slice(0, limit).map(it => {
      const inside = [...document.querySelectorAll(PARTS)].filter(e => {
        const b = box(e);
        return visible(e) && b.y >= it.y && b.y + b.h <= it.y + it.h + 2 && b.x >= it.x - 2 && b.w >= 60 && b.h >= 24
          && !(e.parentElement && e.parentElement.closest(PARTS));
      }).slice(0, 12);
      return { x: it.x, y: it.y, w: it.w, h: it.h, title: Boolean(it.title), heading: it.heading.slice(0, 160),
        text: it.text.slice(0, 2000), bg: it.bg,
        parts: inside.map(e => { const b = box(e), tag = e.tagName.toLowerCase();
          const label = tag === "h3" ? clean(e.innerText) : tag === "img" ? clean(e.alt)
            : tag === "svg" ? clean(e.getAttribute("aria-label") || (e.querySelector("title") || {}).textContent || "chart")
            : clean(e.innerText).slice(0, 60);
          return { tag, label: label.slice(0, 80), x: b.x - it.x, y: b.y - it.y, w: b.w, h: b.h }; }) }; }),
    more: Math.max(0, items.length - limit) };
}"""

LIMIT = 30
DENSITY = 2          # captures at 2x: zoomed text stays sharp at 720p, and 1080p gets real detail
MAX_PX = 16000       # Chromium's largest capture: a taller section is captured at 1x


def capture(page, video, fmt, port):
    """Open the frozen page at this format's width, find the sections, and save one PNG per section."""
    page.goto(f"http://127.0.0.1:{port}/assets/page/index.html", wait_until="load", timeout=90000)  # a cold start can be slow
    page.wait_for_timeout(800)  # in-page CSS builders (Tailwind's browser build) and highlighters
    page.evaluate(FREEZE)
    found = page.evaluate(FIND, LIMIT)
    cdp = page.context.new_cdp_session(page)
    folder = video / "assets" / "page" / "shots" / fmt
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    for i, s in enumerate(found["sections"]):
        s["id"] = "s00" if s["title"] else f"s{i + (0 if found['sections'][0]['title'] else 1):02d}"
        h = max(1, min(s["h"], found["height"] - s["y"]))
        scale = DENSITY if h * DENSITY <= MAX_PX else 1  # a clipped capture is CSS px x scale; the page renders at 2x
        shot = cdp.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                                                   "clip": {"x": s["x"], "y": s["y"], "width": s["w"], "height": h, "scale": scale}})
        (folder / f"{s['id']}.png").write_bytes(base64.b64decode(shot["data"]))
        s["shot"] = f"assets/page/shots/{fmt}/{s['id']}.png"
    return found


def sections(video, fmt=None):
    from playwright.sync_api import sync_playwright

    from ev.render import guard, serve
    page_of(video)
    script = video / "script.yaml"
    targets = formats(load(video), fmt) if script.is_file() else formats({}, fmt)
    server = serve(video, {})
    blocked, found = [], {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--font-render-hinting=none"])
            for f in targets:
                width, height = SIZE[f]
                context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=DENSITY,
                                              service_workers="block")
                guard(context, server.server_address[1], blocked)
                errors = []
                page = context.new_page()
                page.on("pageerror", lambda e: errors.append(str(e)))
                found[f] = capture(page, video, f, server.server_address[1])
                found[f]["errors"] = errors[:10]
                context.close()
            browser.close()
    finally:
        server.shutdown()
    first = found[targets[0]]
    for f in targets[1:]:
        if [s["id"] for s in found[f]["sections"]] != [s["id"] for s in first["sections"]]:
            raise SystemExit(f"The page has {len(found[f]['sections'])} sections at the {f} width and "
                             f"{len(first['sections'])} at the {targets[0]} width. Make one format at a time: FORMAT={targets[0]}")
    manifest = {"source": json.loads((video / "assets" / "page" / "source.json").read_text()).get("file", "")
                if (video / "assets" / "page" / "source.json").is_file() else "index.html",
                "title": first["title"], "kind": first["kind"], "formats": found}
    (video / "build").mkdir(exist_ok=True)
    (video / "build" / "sections.json").write_text(json.dumps(manifest, indent=1))
    drafted = draft(video, manifest, targets)
    print(f"DONE sections: {len(first['sections'])} ({first['kind']}) in {', '.join(targets)}. "
          f"Manifest: {video}/build/sections.json")
    for s in first["sections"]:
        print(f"  {s['id']}  {s['h']:>5} px  {s['heading'][:70] or '(no heading)'}")
    if first["more"]:
        print(f"  NOTE {first['more']} more sections not captured: the page has over {LIMIT}")
    for u in dict.fromkeys(blocked):
        print(f"  NOTE blocked a request to {u[:120]}: run make from-html again with network, or the page lacks it")
    for e in first.get("errors", []):
        print(f"  NOTE page JS error: {e[:160]}")
    print("\n".join(f"  wrote {x}" for x in drafted))
    print(f"Next (step 1): read sources/page.md, fill in intent.md, then make approve SLUG={video.name} STEP=intent")


# ---------- the draft ----------

def q(text):
    """A YAML string: JSON's double-quoted form is valid YAML."""
    return json.dumps(str(text))


def draft(video, manifest, targets):
    """The project's files from the page: the template where files are missing, sources/page.md, a line in
    sources/index.md, and scenes/page-<id>.html for each section when missing. Returns what it wrote."""
    wrote = []
    first = manifest["formats"][targets[0]]
    before = {p.relative_to(video) for p in video.rglob("*") if p.is_file()}
    copy_template(video, manifest["title"] or video.name)
    wrote += sorted(str(p.relative_to(video)) for p in video.rglob("*")
                    if p.is_file() and p.relative_to(video) not in before and "assets" not in p.parts)
    lines = [f"# {manifest['title'] or 'The page'}", "",
             f"The text of the HTML page {manifest['source']}, section by section (make from-html). A scene "
             f"`scenes/page-<id>.html` shows each section as it looks; `build/sections.json` has the boxes of its parts.", ""]
    for sec in first["sections"]:
        lines += [f"## {sec['id']}: {sec['heading'] or '(no heading)'}", "", sec["text"] or "(no text)", ""]
        lines += [f"- part: {x['tag']} \"{x['label']}\" at x {x['x']}, y {x['y']}, {x['w']} x {x['h']} px"
                  for x in sec["parts"]]
        lines += [""] if sec["parts"] else []
    if first.get("hidden"):
        lines += ["## Hidden parts", "", "Text the page does not show at first: closed tabs and hidden panels. No capture shows it.", ""]
        for part in first["hidden"]:
            lines += [f"### {part['label'] or '(no name)'}", "", part["text"], ""]
    (video / "sources" / "page.md").write_text("\n".join(lines))
    index = video / "sources" / "index.md"
    entry = f"- `page.md`: the HTML page {manifest['source']}, as text by section; copied to `assets/page/` (make from-html)"
    text = index.read_text() if index.is_file() else "# Sources\n\nWhat this video read, and where each came from.\n\n"
    if "`page.md`" not in text:
        index.write_text(text.rstrip("\n") + "\n" + entry + "\n")
    wrote += ["sources/page.md"]
    for sec in first["sections"]:
        path = video / "scenes" / f"page-{sec['id']}.html"
        if not path.exists():
            opts = {"bg": sec["bg"], "w": sec["w"], "parts": [{k: x[k] for k in ("tag", "label", "x", "y", "w", "h")}
                                                             for x in sec["parts"]]}
            path.write_text(SCENE.format(id=sec["id"], what="the title area" if sec["title"] else f"section {sec['id'][1:]}",
                                         opts=json.dumps(opts).replace("</", "<\\/")))
            wrote.append(f"scenes/page-{sec['id']}.html")
    return wrote


SCENE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="/ev/base.css">
<link rel="stylesheet" href="/ev/theme.css">
<link rel="stylesheet" href="../style.css">
<script src="/ev/ev.js"></script>
<script src="/ev/page.js"></script>
</head>
<body>
<div class="stage">
  <div class="safe"></div>
</div>
<script>
// {what} of the page (make from-html): evidence for a beat. parts: its tables, charts, and code, for p.mark and
// p.zoom (see ev/web/page.js). Give the scene id page-{id} in script.yaml, with treatment: page.
EV.page("{id}", {opts}).then(p => {{
  EV.ready();
}});
</script>
</body>
</html>
"""
