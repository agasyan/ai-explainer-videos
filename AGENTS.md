# AI explainer videos

Each new video is a project: `projects/<YYYYMMDD>-<name>/`, made first, and every file of its work stays inside it. An agent writes `research.md` and `sources/` (what it read), `script.yaml` (brief, narration, storyboard), `style.css`, and `scenes/<scene>.html` (HTML, SVG, and CSS, animated with the `EV` runtime in `ev/web/ev.js`). Docker makes the voice, renders the frames in headless Chromium, and writes the MP4. Every tool in the pipeline is open source.

- Run every tool through `make` (`make help` lists them). Install nothing on the host.
- Start with `make new SLUG=<name> TITLE=...` (or `make from-html`). It prints the project id; use it as `SLUG=` in each next command. Videos made before projects stay in `generated_videos/<slug>/` and keep working.
- Save what you read in the project: a copy or notes of each source in `sources/`, and where it came from in `sources/index.md`. The project is then complete on its own.
- Work in 4 steps with 2 human approval checks:
  1. **Intent:** read the sources, fill in `intent.md` (key message, viewers, story, look, keep and cut), then stop until the user approves it (`make approve SLUG=<id> STEP=intent`). The tool makes no voice and no picture before that.
  2. **Plan:** research, fill `script.yaml`, run `make narrate`. Do not stop: the preview check covers the script and the voice.
  3. **Preview:** write the scenes with `docs/visual-patterns.md`, check each with `make stills`, run one full `make preview` (720p), check the contact sheets and `LINT` lines, fix at most 2 rounds, then stop until the user approves the preview. The approved 720p video is the final video.
  4. **Optional 1080p:** `make video`, only when the user says yes. Give them the `VERDICT 1080p:` line first.
- A source is never the video: retell its point in the video format's acts. From an HTML page: `make from-html SLUG=<name> FILE=<page.html>` copies it, writes its text to `sources/page.md`, and makes evidence scenes `scenes/page-<id>.html` to zoom into where a beat needs one.
- Full workflow: `.claude/skills/explainer-video/SKILL.md`. Any agent can follow it.
- Only the user approves (`make approve`). Never edit `approved.json`.
- Scene API: the comment at the top of `ev/web/ev.js`, and `docs/scenes.md`. Pictures: `docs/visual-patterns.md`, with starters in `templates/patterns/`. Writing rules: `docs/writing.md`. Starter files: `templates/video/`.
- Change `ev/` or `dashboard/` only when the user asks to change the tool.
- Content can be confidential: put zero customer data or secrets in a video.
- Never run `hyperframes publish`, `cloud`, `lambda`, or `auth`: they upload the project. The pipeline calls only `hyperframes render`.
