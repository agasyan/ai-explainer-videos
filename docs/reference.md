# Reference

## Commands

Every command runs in Docker, except `make dashboard`. `SLUG=` takes a project id (`20261118-dns`), a name (`dns`: its newest project, and the command says which), or the slug of a video made before projects (`generated_videos/<slug>/`). `make approve` and `make video` take only the exact id or older slug, so an approval or a 1080p render names the one video you checked.

| Command | Does |
|---------|------|
| `make build` | Builds the Docker image, once |
| `make doctor` | Checks every tool; sends "testing one two three" through the voice and back |
| `make test` | Runs the unit tests in `tests/` inside the image |
| `make new SLUG=dns TITLE="How DNS works"` | Starts a project, `projects/<YYYYMMDD>-dns/` (`-2` for a second one that day), from `templates/video/`, with an empty `sources/`; add `SAMPLE=<name>` to start from `videos/samples/<name>/`. It prints the project id |
| `make from-html SLUG=q3 FILE=~/reports/q3.html` | Starts a project (`projects/<YYYYMMDD>-q3/`), copies an HTML page and its CDN files, captures one scene per section, and drafts `script.yaml` and `scenes/` ([from-html.md](from-html.md)). With a project id and no `FILE=`, it captures that project's page again |
| `make sample SLUG=dns` | Maintainers, on the host: copy an approved video's sources and frames to `videos/samples/dns/` to commit |
| `make narrate SLUG=dns` | Step 1: makes the voice, writes `storyboard.md` and `build/narration.wav`, prints `CHECK` lines |
| `make storyboard SLUG=dns` | Writes `storyboard.md` again from the current narration and prints it as JSON |
| `make status SLUG=dns` | Shows the steps and the next action |
| `make approve SLUG=dns STEP=preview` | Approves the preview, the final video, after you check it (`STEP=plan` for an optional early plan check) |
| `make stills SLUG=dns SCENE=hook` | The frame before each next beat, linted, with a contact sheet: a check in seconds while you draw. No MP4 |
| `make preview SLUG=dns` | Step 2: the 720p video (the final), review frames, lint, and the 1080p verdict |
| `make video SLUG=dns` | Optional 1080p. Needs an approved preview |
| `make reference FILE=ref.mp4` | Words per minute, cuts per minute, transcript, and a contact sheet of a reference video |
| `make transcribe FILE=talk.m4a` | `talk.txt` and `talk.srt` next to the file. `MODEL=small` for other languages (downloaded once to `generated_videos/.models/`) |
| `make dashboard` | The web page ([dashboard.md](dashboard.md)) |
| `make catalog` | Maintainers: checks every moodboard and video format, renders `swatch.jpg`, writes both `catalog.json` |
| `make shell` | A shell inside the image |

Options for `stills`, `preview`, and `video`: `FORMAT=landscape|story|both` (default: the script's `format`), `PART=2` (one part), `SCENE=hook` (one scene). Only a full render counts for an approval. Files passed with `FILE=` to `reference` and `transcribe` must be inside `projects/` or `generated_videos/`: Docker can write only there, and the outputs go next to the file; `from-html` reads its `FILE=` on the host instead. The environment variable `EV_WORKERS=2` sets how many pages render at the same time (default 3, about 0.3 GB each). With `engine: hyperframes`, `EV_HF_WORKERS=2` sets the number of Chrome workers (default: HyperFrames picks).

## script.yaml

| Field | Meaning | Default |
|-------|---------|---------|
| `title` | Video title | the slug |
| `brief` | `viewer`, `takeaway`, `points`, `example`, `sources`, `guesses` | `(fill in)` |
| `format` | `landscape`, `story`, or `both` | `landscape` |
| `moodboard` | A folder in `moodboards/` ([scenes.md](scenes.md#moodboards)), or `recommend` until the plan picks one | `recommend` |
| `video_format` | A folder in `video-formats/`: the acts and the beat range of each, or `recommend` | `recommend` |
| `three` | `true` allows 3D (three.js) in scenes with a `three_why`; `false` is 2D only ([scenes.md](scenes.md#3d)) | `true` in new videos, `false` when absent |
| `picks` | The recommender's picks: `video_format` and `moodboard`, 3 `{name, why}` each, the pick first; empty when you chose in the form | empty |
| `look` | Old name for `moodboard`: `clean`, `dark` (now `math-dark`), or `whiteboard` | |
| `voice` | A Kokoro English voice (list below) | `af_heart` |
| `speed` | Voice speed | `1.0` |
| `gap` | Seconds of silence after each beat | `0.35` |
| `captions` | `pop` (words appear as said), `line` (whole line, words light up), or `off` | `pop` |
| `engine` | `playwright`, or `hyperframes` for parallel capture and `<video>` clips ([how-it-works.md](how-it-works.md#engines)) | `playwright` |
| `scenes` | List of scenes; or use `parts`, each with a `title` and `scenes` | |
| scene `id` | Lowercase letters, digits, dashes; names `scenes/<id>.html` | |
| scene `treatment` | One of the moodboard's `treatments`, for example `title`, `flow`, `timeline`; or `page` for a captured page section ([from-html.md](from-html.md)) | |
| scene `three_why` | One line: why 3D explains this scene better than 2D. Needed for a scene that loads three.js | |
| beat `id`, `say`, `show` | Beat name (lowercase letters, digits, dashes; names its frame), narration (`*key words*` in asterisks get the caption key color), storyboard | |
| beat `hold` | Extra seconds of picture after the voice | `0` |
| beat `sources` | Claim ids from `research.md` that the beat states, for example `[c1, c3]` | none |

Kokoro voices include `af_heart`, `af_bella`, `am_michael`, `am_fenrir` (US English) and `bf_emma`, `bm_george` (UK English).

## Files in a video folder

A video's folder is `projects/<YYYYMMDD>-<name>/`, or `generated_videos/<slug>/` for a video made before projects. Both are gitignored (only their `.gitkeep` is tracked), so every video stays on your machine: its content can be confidential. Committed samples live in `videos/samples/` and hold sources only. Back up a video's sources (`research.md`, `sources/`, `script.yaml`, `style.css`, `scenes/`, `assets/`, `approved.json`) in a private place.

| Path | What | Back up |
|------|------|-----------|
| `script.yaml` | Brief, narration, storyboard | yes |
| `assets/page/` | From `make from-html`: the page (`index.html`), its local and CDN files, and `shots/<format>/<id>.png` | yes |
| `style.css`, `scenes/`, `assets/` | The animation | yes |
| `approved.json` | Approvals | yes |
| `research.md` | Topics only: each claim with its sources ([writing.md](writing.md#research-every-fact-has-a-source)) | yes |
| `sources/` | What the agent read: a copy or notes of each file, page, or diff, and `index.md` with where each came from (path, repo and commit, or URL) | yes |
| `storyboard.md` | Made by `make narrate` from `script.yaml`: picks, video direction, one row per beat. Never edit it | no |
| `frames/<format>/<scene>/<beat>.jpg` | One frame per beat from the last full 720p render, shown in `storyboard.md` | no |
| `build/narration.wav` | All beats in a row | no |
| `build/sections.json` | From `make from-html`: each section's heading, text, size, and parts (tables, charts, code) | no |
| `build/stills/<format>/<scene>/<beat>.jpg` | From `make stills` | no |
| `build/verdict.json` | Is 1080p worth it? From the last full 720p render | no |
| `build/hf/<scene or all>/` | The HyperFrames project made for each render (`engine: hyperframes`); one per `SCENE=`, so parallel scene renders stay apart | no |
| `build/review/*-contact-N.png` | Review frames, 12 per sheet | no |
| `out/<slug>[-partN]-<format>-720p.mp4` | The final video once you approve it, with captions in the picture and a subtitle track players can switch on | no |
| `out/<slug>[-partN]-<format>-1080p.mp4` | Optional 1080p | no |
| `out/*.srt`, `out/*.vtt` | Caption files for uploads and web players | no |
