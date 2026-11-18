# AI explainer videos

Each new video is a project: `projects/<YYYYMMDD>-<name>/`, made first, and every file of its work stays inside it. An agent writes `research.md` and `sources/` (what it read), `script.yaml` (brief, narration, storyboard), `style.css`, and `scenes/<scene>.html` (HTML, SVG, and CSS, animated with the `EV` runtime in `ev/web/ev.js`). Docker makes the voice, renders the frames in headless Chromium, and writes the MP4. Every tool in the pipeline is open source.

- Run every tool through `make` (`make help` lists them). Install nothing on the host.
- Start with `make new SLUG=<name> TITLE=...` (or `make from-html`). It prints the project id; use it as `SLUG=` in each next command. Videos made before projects stay in `generated_videos/<slug>/` and keep working.
- Save what you read in the project: a copy or notes of each source in `sources/`, and where it came from in `sources/index.md`. The project is then complete on its own.
- Work in 2 steps with 1 human approval check:
  1. **Plan:** fill `script.yaml`, run `make narrate`. Do not stop here, unless the user asks for a plan check.
  2. **Preview:** write the scenes, check each with `make stills`, run one full `make preview` (720p), check the contact sheets and `LINT` lines, fix at most 2 rounds, then stop until the user approves the preview. The approved 720p video is the final video.
  - **Optional 1080p:** `make video`, only when the user says yes. Give them the `VERDICT 1080p:` line first.
- From an HTML page: `make from-html SLUG=<slug> FILE=<page.html>` drafts the script and one scene per page section. Then write the narration and go on from step 1.
- Full workflow: `.claude/skills/explainer-video/SKILL.md`. Any agent can follow it.
- Only the user approves (`make approve`). Never edit `approved.json`.
- Scene API: the comment at the top of `ev/web/ev.js`, and `docs/scenes.md`. Writing rules: `docs/writing.md`. Starter files: `templates/video/`.
- Change `ev/` or `dashboard/` only when the user asks to change the tool.
- Content can be confidential: put zero customer data or secrets in a video.
- Never run `hyperframes publish`, `cloud`, `lambda`, or `auth`: they upload the project. The pipeline calls only `hyperframes render`.
