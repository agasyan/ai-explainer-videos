# From an HTML page

Turn a report, a docs page, or an artifact into a narrated video of its own sections. Like any new video, it is a project: `projects/<YYYYMMDD>-<name>/` holds the copied page, its captures, the script, and the renders. The agent writes only the narration: each scene shows a capture of one section, with a camera that scrolls it and highlights on its tables, charts, and code.

## Start

| | Dashboard | Claude Code | By hand |
|---|---|---|---|
| Start | Paste the page's path as the source, press Start | `/explainer-video ~/reports/q3-review.html` | `make from-html SLUG=q3 FILE=~/reports/q3-review.html` (it prints the project id, for example `20261118-q3`) |
| Then | Approve the 720p video | Approve the 720p video | Write the narration, then `make narrate`, `make preview`, `make approve` |

The path can be absolute or start with `~`. In the dashboard, a relative path is read from the Extra folder field. A page behind a sign-in: save it as HTML first, or use a connector's download. Do not work around the sign-in.

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
assets/page/shots/<format>/<id>.png + build/sections.json + script.yaml + scenes/<id>.html
   │  4 the agent: brief and narration from build/sections.json
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
4. **Draft.** When they do not exist yet, it writes `script.yaml` (one scene per section, `treatment: page`, `say: (fill in)`), `style.css`, and `scenes/<id>.html`. Run `make from-html SLUG=<project id>` again to capture the page again (for a new format, or after you edit `assets/page/index.html`): it keeps your script and scenes.

## Write the narration

- Read `build/sections.json`; open `assets/page/index.html` for detail. State only what the page says.
- One scene per section, in page order. Delete a scene to skip its section. Give a long section 2 or 3 beats: the camera scrolls over all of a scene's beats, so more words mean a slower scroll.
- Highlight a part when a beat names it: `p.mark(p.parts[n], EV.at(beat, "word"))` in the scene ([scenes.md](scenes.md#page-sections)).
- The look comes from the page. `moodboard:` sets only the captions and the highlight color.

## Rules

- **The capture shows the page as it is.** Before you approve, check every frame for customer data, personal names, booking references, and links to private threads. Delete or redraw a section that shows them.
- **1080p.** The verdict for a page video is "worth it for big screens": page text is small. 720p is fine on a laptop or phone.
- **Limits:** 30 sections, 20 MB per copied file, 200 MB in all, 15 MB per CDN file.
