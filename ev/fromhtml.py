"""make from-html, inside Docker: turn one HTML page into a video draft. The host first copies the page to
assets/page/index.html (ev/intake.py). Then:

1. vendor (ev/vendor.py, on the host): copy the scripts, styles, and fonts the page loads from a short list of CDNs
   into assets/page/vendor/, and point the page at the copies. It sends GET requests for those files and nothing
   else: the page's own text never leaves the machine.
2. sections(): open the page with no network, freeze it, find its sections (<section> elements, else the
   blocks between <h2> headings, else the whole page), and capture each one as a PNG per format. Writes
   build/sections.json (heading, text, size, and the boxes of tables, charts, and code for highlights), and drafts
   script.yaml (one scene per section, `say: (fill in)`), style.css, and scenes/<id>.html when they do not exist yet.

An agent then writes the narration from build/sections.json, and the usual narrate and preview steps follow.
"""
import base64
import json
import shutil

from ev.common import ROOT, SIZE, formats, load
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
  return { kind, title: clean(document.title), bg: pageBg, height: document.documentElement.scrollHeight,
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
    page.goto(f"http://127.0.0.1:{port}/assets/page/index.html", wait_until="load")
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
    print("\n".join(f"  wrote {x}" for x in drafted) if drafted else "  script.yaml and scenes/ exist: kept as they are")
    print(f"Next: write each beat's say from build/sections.json, then make narrate SLUG={video.name}")


# ---------- the draft ----------

def q(text):
    """A YAML string: JSON's double-quoted form is valid YAML."""
    return json.dumps(str(text))


def draft(video, manifest, targets):
    """script.yaml, style.css, and scenes/<id>.html for each section, when they do not exist. Returns what it wrote."""
    wrote = []
    first = manifest["formats"][targets[0]]
    if not (video / "style.css").exists():
        shutil.copy2(ROOT / "templates" / "video" / "style.css", video / "style.css")
        wrote.append("style.css")
    (video / "scenes").mkdir(exist_ok=True)
    for s in first["sections"]:
        path = video / "scenes" / f"{s['id']}.html"
        if not path.exists():
            opts = {"bg": s["bg"], "w": s["w"], "parts": [{k: x[k] for k in ("tag", "label", "x", "y", "w", "h")}
                                                         for x in s["parts"]]}
            path.write_text(SCENE.format(id=s["id"], what="the title area" if s["title"] else f"section {s['id'][1:]}",
                                         opts=json.dumps(opts).replace("</", "<\\/")))
            wrote.append(f"scenes/{s['id']}.html")
    if not (video / "script.yaml").exists():
        lines = [f"title: {q(manifest['title'] or video.name)}",
                 "source: html              # made by make from-html: one scene per section of assets/page/index.html",
                 "brief:                    # replace each fill-in line; the facts come from the page only",
                 "  viewer: (fill in) who watches, and what they know already",
                 "  takeaway: (fill in) one sentence the viewer remembers",
                 "  points:",
                 "    - (fill in) 3 to 5 points, in order",
                 "  example: (fill in) one concrete example from the page",
                 "  sources:",
                 f"    - {q('assets/page/index.html, copied from ' + manifest['source'])}",
                 "  guesses: []",
                 f"format: {'both' if len(targets) > 1 else targets[0]}",
                 "moodboard: clean          # captions and accents; each scene shows the page's own look",
                 "three: false",
                 "voice: af_heart",
                 "speed: 1.0",
                 "gap: 0.35",
                 "captions: pop",
                 "engine: playwright",
                 "",
                 "# One scene per page section, in page order. Delete a scene to skip its section; add beats to a long one.",
                 "# The scene's camera scrolls the section from top to bottom over all of its beats.",
                 "scenes:"]
        for s in first["sections"]:
            lines += [f"  - id: {s['id']}",
                      "    treatment: page",
                      "    beats:",
                      f"      - id: {s['id']}-a",
                      f"        say: (fill in) narration for {q(s['heading'] or s['id'])}",
                      f"        show: {q(('The title area' if s['title'] else 'Section ' + s['id'][1:]) + (': ' + s['heading'] if s['heading'] else '') + ', from top to bottom.')}"]
        (video / "script.yaml").write_text("\n".join(lines) + "\n")
        wrote.append("script.yaml")
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
// {what} of the page (make from-html). parts: tables, charts, and code in it, for p.mark (see ev/web/page.js).
EV.page("{id}", {opts}).then(p => {{
  EV.ready();
}});
</script>
</body>
</html>
"""
