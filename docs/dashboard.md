# Dashboard

Run `make dashboard` and open http://127.0.0.1:8787. The page starts Claude Code jobs, shows the 720p video with an Approve button, and offers the optional 1080p. Jobs run on your Claude Code login, so they need a Claude plan (Pro, Max, Team, or Enterprise) or an API key.

## What the page shows

- **System:** Docker (running, stopped, not installed, or not responding), the image (built or not), the last doctor result, and the Claude Code login (`claude auth status`: logged in with its plan, logged out, expired, or no plan; never your email). Start Docker, Stop Docker (Colima), Build image, and Run doctor are buttons; each runs a fixed command and ends with "Done:" or "Failed:" and the last log line. Start stays off until Docker runs, the image is built, and Claude Code is logged in with a plan or an API key. The page checks the login once a minute.
- **New video:** source; name (the job's project is `projects/<today>-<name>`, made when you press Start, and the card shows it); video format and moodboard, each "Recommend for me" or one catalog entry (a moodboard shows its swatch); aspect and voice. The job makes one video, with no parts. Two boxes: "Allow 3D where it explains better" (ticked; off when `make doctor` finds no WebGL), and "Stop after the plan" (unticked: Claude runs to the 720p video, and you check the plan there). An optional extra folder Claude may read is for a repo outside this folder.
- **From an HTML page:** a source that is one path to an `.html` or `.htm` file, for example `~/reports/q3-review.html`. The slug follows the file name. When you press Start, the page copies the file and the local files it links into the video folder ([from-html.md](from-html.md)), then starts the job; a relative path is read from the extra folder. The job never gets your path, and it may not copy files itself (`FILE=` is denied in jobs).
- **Samples:** finished videos from `videos/samples/`, each with a frame and its picks. "Start from this sample" copies its sources to a new slug and makes the voice, with no Claude job; then check the plan as usual.
- **Videos:** every video with its steps: 1 Plan, 2 Preview (your check, the final video), 3 1080p (optional). ✓ done, ● waiting for you, … working, ○ next.
- **Review:** the 720p videos and contact sheets, with the storyboard below them: the picks (a recommended video format and moodboard with 2 alternatives each, moodboard swatches), the video direction, one row per beat (time, voice, picture, treatment, 2D or 3D, sources, frame), and the research table. Then the check question, Approve, and Request changes. Before the preview exists, the storyboard and a voice player show here, with an optional early plan approval.
- **Render buttons:** "Render 720p" once scenes exist, and "Render 1080p (optional)" once the preview is approved, each with an estimate such as "About 4 min" from earlier renders on this machine. Next to it, the verdict: "1080p: not needed" or "worth it for big screens", with the reason. While a render runs, the job line reads "3 of 12 scenes done". The approved 720p MP4 and any 1080p MP4 have Download links.
- **Players:** each video has its subtitle track (switch it on in the player menu) and a transcript below it. Click a line to jump there; the current line is highlighted.
- **Jobs and log:** each Claude run, what Claude says, and each command it runs.

## How it works

- Each job runs `claude -p "<request>" --permission-mode dontAsk` in this folder, with an allowlist: the commands in `.claude/settings.json`, edits to its own video's sources (in `projects/<id>/`, or `generated_videos/<slug>/` for an older video), and reads in the extra folder. Claude Code refuses anything else without a prompt.
- When Claude reaches the check, it ends with `WAITING FOR APPROVAL: <slug> preview` (or `plan`, when you ticked "Stop after the plan"), and the page opens that video's review.
- Approve sends the fingerprint of what the page showed. `ev/gates.py` refuses it if a file changed since ("Changed since you looked: check again"), else records the approval. After a plan approval, it resumes the same Claude session (`--resume <session id>`) to do step 2.
- Request changes sends your text to the same session; Claude applies it and stops for the check again.
- After the preview approval, Claude stops: the video is done, and 1080p is your button. The page runs a fixed `make video` with the formats you approved, refuses while a job for that video runs, and the render re-checks the preview approval after capture, so a file changed meanwhile removes the 1080p files.
- The page runs on the host, not in Docker, because it uses your Claude Code login. Claude's `make` commands then use Docker. It needs Python 3.9 or later and the `claude` command.

## Safety

- The server listens on 127.0.0.1 only and checks the Host header.
- Every POST needs a token that the server puts in the page at start, so other websites cannot start jobs or approve steps.
- Agent-written text (storyboard, picks, research) reaches the page as text only, never as HTML; a link shows only for an `http` or `https` address. The server never serves `storyboard.md` or `script.yaml` as files.
- Claude may write only a video's sources (`script.yaml`, `research.md`, `style.css`, `scenes/*.html`, `assets/`), read the extra folder, and run only the commands in `.claude/settings.json`. The list names files exactly, so a disk that ignores letter case cannot widen it: `APPROVED.JSON` or `MAKEFILE` matches nothing. Text hidden in a source (a PR, a web page) cannot make Claude change the tool or run its own code.
- Inside Docker, Python runs in isolated mode with the repo last on its path, so a file at the repo root (for example `json.py`) never replaces a library.
- Each job works on one video. The page fixes its slug when the job starts (the Slug box) and passes it as `EV_JOB_SLUG`, which `make` enforces: the job may run `make` only with that slug, edit only that video's sources, and its own output cannot switch it to another video.
- Treat fetched web pages and samples as untrusted input: a job cannot read or edit another video's folder (the rules also match any letter case), so hidden instructions in a source cannot copy one out.
- The pipeline's container has no network (`network_mode: none`), so a scene page cannot send a video's content anywhere, whatever the engine. Each render also blocks any URL outside its own local server and prints it as a `LINT` line. Only `make transcribe` uses a container with network, to download a whisper model once. The vendor step of `make from-html` runs on the host: it downloads a page's scripts, styles, and fonts from a short list of CDNs and runs no page code.
- Inside Docker the repo is read-only except `projects/` and `generated_videos/`, and `make` accepts only its documented options (`SLUG`, `TITLE`, `STEP`, `FORMAT`, `PART`, `SCENE`, `FILE`, `MODEL`, `SAMPLE`).
- Keep the bind address at 127.0.0.1. On 0.0.0.0, anyone on your network could run Claude on your machine.

## Design rules

The page is a calm, dense internal tool:

1. Components come from Basecoat 1.0.2, vendored and minified in `dashboard/vendor/`; the page loads nothing from the internet.
2. Colors come from Basecoat's tokens, so light and dark follow the system setting. No gradients and no shadows of our own.
3. Loading, empty, and error states look different, and each button that cannot run says why ("Start Docker first").
4. Agent-written text is shown as text, never as HTML.
5. One main button per card; the rest are secondary or outline.
