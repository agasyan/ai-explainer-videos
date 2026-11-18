# From an HTML page

An HTML page (a report, a docs page, a claude.ai artifact) is a **source**, not the video. Claude reads it, writes an intent card for your check, and then retells its point in its own story: shorter and simpler, with diagrams, stat cards, comparisons, and 3D where it helps ([visual-patterns.md](visual-patterns.md)). It does not scroll the page. Where a beat needs the evidence, a scene shows one part of the real page and zooms into it.

Like any new video, it is a project: `projects/<YYYYMMDD>-<name>/` holds the copied page, its text, its captures, the intent, the script, and the renders.

## Start

| | Dashboard | Claude Code | By hand |
|---|---|---|---|
| Start | **+ New video**, a source row of kind HTML page, press Start video | `/explainer-video ~/reports/q3-review.html` | `make from-html SLUG=q3 FILE=~/reports/q3-review.html` (it prints the project id, for example `20261118-q3`) |
| Then | Approve the intent, then the 720p video | Approve the intent, then the 720p video | Fill in `intent.md`, approve it, write the script and scenes, then `make narrate`, `make preview`, `make approve` |

Give the full path: it starts with `/` or `~`. A page behind a sign-in: save it as HTML first, or use a connector's download. Do not work around the sign-in. One HTML page per video; add other pages as files.

## What happens

```
page.html (your disk)
   │  1 intake (host): start projects/<YYYYMMDD>-<name>/, copy the page and the files it links from its own folder
   ▼
projects/<id>/assets/page/index.html
   │  2 vendor (host): copy scripts, styles, and fonts from the CDN list
   ▼
assets/page/vendor/...
   │  3 sections (container with no network): freeze the page, find sections, capture each at 2x
   ▼
assets/page/shots/<format>/<id>.png + sources/page.md + scenes/page-<id>.html + the template
   │  4 the agent: intent.md (your check), then its own story, script, and drawn scenes
   ▼
make narrate -> make preview -> your check
```

1. **Intake** (`ev/intake.py`, on the host). Copies the page as `assets/page/index.html`, plus each file it links with a relative path, when that file is in the page's own folder and is a type a page loads (images, CSS, JS, fonts, video). It never follows a symlink out of the folder. `assets/page/source.json` lists what it copied and skipped.
2. **Vendor** (`ev/vendor.py`, on the host, with your Mac's network and DNS; standard library only). Copies `<script src>`, stylesheets, and fonts from these HTTPS hosts: `cdnjs.cloudflare.com`, `cdn.jsdelivr.net`, `unpkg.com`, `cdn.tailwindcss.com`, `code.jquery.com`, `fonts.googleapis.com`, `fonts.gstatic.com`. It points the page at the copies. It sends GET requests for those files only: the page's text never leaves your machine. Other hosts are listed as `NOTE` lines, and a link (`<a href>`) is never fetched. A second run fetches nothing.
3. **Sections** (`ev sections`, no network). Opens the page at the format's width (1920 px for landscape, 1080 px for story), so it uses its own responsive layout. It freezes the page: animations jump to their end, transitions stop, `<details>` open, lazy images load, fixed bars hide, and sticky ones stop sticking. Then it finds the sections, in this order:
   - top-level `<section>` elements, when there are 2 or more;
   - else the blocks between `<h2>` headings, in `<main>`, `<article>`, or the body;
   - else the whole page, as one tall scene.

   A title area above the first section becomes scene `s00`. Each section is captured at 2x (a section over 8000 px tall at 1x), so zoomed text stays sharp. `build/sections.json` lists each section's heading, text (2000 characters at most), size, and parts: tables, charts, code blocks, images, and sub-headings, with their boxes.
4. **Project files.** Where a file is missing, it starts the project from `templates/video/` (`intent.md`, `script.yaml`, `style.css`, `scenes/`). It writes the page's text, section by section, to `sources/page.md`, adds the page to `sources/index.md`, and writes `scenes/page-<id>.html` for each section: a ready scene that shows that part of the page. Run `make from-html SLUG=<project id>` again to capture the page again (for a new format, or after you edit `assets/page/index.html`): it keeps your intent, script, and scenes.

## Retell it

- Read `sources/page.md`; open `assets/page/index.html` for detail. State only what the page says, unless web research is on.
- Fill in `intent.md`: the key message, the viewers, the story in a video format's acts, the look, what to keep and cut, and the evidence to show. Then ask for the intent check.
- Tell it in the acts, not in the page's order. A decision: the verdict, the options side by side, the evidence for each criterion, the verdict again and the ask ([visual-patterns.md](visual-patterns.md)).
- Evidence: use a `scenes/page-<id>.html` scene (scene id `page-<id>`, `treatment: page`) only where a beat names a table, chart, or code block. Zoom into it with `p.zoom`, and mark it with `p.mark` ([scenes.md](scenes.md#page-sections)).
- A page tour, every page scene in page order, is only for a request that asks for one.

## Rules

- **The capture shows the page as it is.** Before you approve, check every frame for customer data, personal names, booking references, and links to private threads. Delete or redraw a section that shows them.
- **1080p.** A video with page scenes gets the verdict "worth it for big screens": page text is small. 720p is fine on a laptop or phone.
- **Limits:** 30 sections, 20 MB per copied file, 200 MB in all, 15 MB per CDN file.
