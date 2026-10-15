# AI explainer videos

An agent writes `generated_videos/<slug>/script.yaml` (brief, narration, storyboard), `style.css`, and `scenes/<scene>.html` (HTML, SVG, and CSS, animated with the `EV` runtime in `ev/web/ev.js`). Docker makes the voice, renders the frames in headless Chromium, and writes the MP4. Every tool in the pipeline is open source.

- Run every tool through `make` (`make help` lists them). Install nothing on the host.
- Work in 3 steps with 2 human approval checks:
  1. **Plan:** fill `script.yaml`, run `make narrate`, then stop until the user approves the plan.
  2. **Preview:** write the scenes, run `make preview` (720p), check the contact sheets and `LINT` lines, fix at most 2 rounds, then stop until the user approves the preview.
  3. **Final:** `make video` (1080p).
- Full workflow: `.claude/skills/explainer-video/SKILL.md`. Any agent can follow it.
- Only the user approves (`make approve`). Never edit `approved.json`.
- Scene API: the comment at the top of `ev/web/ev.js`, and `docs/scenes.md`. Writing rules: `docs/writing.md`. Starter files: `templates/video/`.
- Change `ev/` or `dashboard/` only when the user asks to change the tool.
- Content can be confidential: put zero customer data or secrets in a video.
- Never run `hyperframes publish`, `cloud`, `lambda`, or `auth`: they upload the project. The pipeline calls only `hyperframes render`.
