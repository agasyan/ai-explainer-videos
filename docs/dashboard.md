# Dashboard

Run `make dashboard` and open http://127.0.0.1:8787. The page starts Claude Code jobs and shows each check with Approve buttons.

## What the page shows

- **System:** Docker (running, stopped, not installed, or not responding), the image (built or not), the last doctor result, and the Claude Code login. Start Docker, Stop Docker (Colima), Build image, and Run doctor are buttons; each runs a fixed command and ends with "Done:" or "Failed:" and the last log line. Start stays off until Docker runs, the image is built, and you are logged in.
- **New video:** source; slug; video format and moodboard, each "Recommend for me" or one catalog entry (a moodboard shows its swatch); aspect, length per part, and voice. Two boxes: "Allow 3D where it explains better" (ticked; off when `make doctor` finds no WebGL), and "Run until the 720p preview without stopping" (unticked: your Start click is then the consent, and you check the plan together with the preview). An optional extra folder Claude may read is for a repo outside this folder.
- **Samples:** finished videos from `videos/samples/`, each with a frame and its picks. "Start from this sample" copies its sources to a new slug and makes the voice, with no Claude job; then check the plan as usual.
- **Videos:** every video with its two checks: ✓ approved, ● waiting for you, ↺ changed after approval, » plan checked with the preview (auto).
- **Review:** for the plan, the storyboard: the picks (a recommended video format and moodboard with 2 alternatives each, moodboard swatches), the video direction, one row per beat (time, voice, picture, treatment, 2D or 3D, sources, frame), the research table, and a voice player. For the preview, the 720p videos and contact sheets. Then the check question, Approve and continue, and Request changes.
- **Render buttons:** "Render 720p preview" once scenes exist and the plan is approved, and "Render 1080p" once the preview is approved, each with an estimate such as "About 4 min" from earlier renders on this machine. While it runs, the job line reads "Rendering scene 3 of 12". Each final MP4 has a Download link.
- **Players:** each video has its subtitle track (switch it on in the player menu) and a transcript below it. Click a line to jump there; the current line is highlighted.
- **Jobs and log:** each Claude run, what Claude says, and each command it runs.

## How it works

- Each job runs `claude -p "<request>" --permission-mode dontAsk` in this folder, with an allowlist: the commands in `.claude/settings.json`, edits to a video's sources in `generated_videos/`, and reads in the extra folder. Claude Code refuses anything else without a prompt.
- When Claude reaches a check, it ends with `WAITING FOR APPROVAL: <slug> <step>`, and the page opens that video's review.
- Approve sends the fingerprint of what the page showed. `ev/gates.py` refuses it if a file changed since ("Changed since you looked: check again"), else records the approval and resumes the same Claude session (`--resume <session id>`) to do the next step.
- Request changes sends your text to the same session; Claude applies it and stops for the check again.
- After the preview approval, Claude stops: 1080p is your button. The page runs a fixed `make video` with the formats you approved, refuses while a job for that video runs, and the render re-checks the preview approval after capture, so a file changed meanwhile removes the 1080p files.
- The page runs on the host, not in Docker, because it uses your Claude Code login. Claude's `make` commands then use Docker. It needs Python 3.9 or later and the `claude` command.

## Safety

- The server listens on 127.0.0.1 only and checks the Host header.
- Every POST needs a token that the server puts in the page at start, so other websites cannot start jobs or approve steps.
- Agent-written text (storyboard, picks, research) reaches the page as text only, never as HTML; a link shows only for an `http` or `https` address. The server never serves `storyboard.md` or `script.yaml` as files.
- Claude may write only a video's sources (`script.yaml`, `research.md`, `style.css`, `scenes/*.html`, `assets/`), read the extra folder, and run only the commands in `.claude/settings.json`. The list names files exactly, so a disk that ignores letter case cannot widen it: `APPROVED.JSON` or `MAKEFILE` matches nothing. Text hidden in a source (a PR, a web page) cannot make Claude change the tool or run its own code.
- Inside Docker, Python runs in isolated mode with the repo last on its path, so a file at the repo root (for example `json.py`) never replaces a library.
- Each job works on one video. The page fixes its slug when the job starts (the Slug box) and passes it as `EV_JOB_SLUG`, which `make` enforces: the job may run `make` only with that slug, edit only that video's sources, and its own output cannot switch it to another video.
- Treat fetched web pages and samples as untrusted input: a job cannot read or edit another video's folder (the rules also match any letter case), so hidden instructions in a source cannot copy one out.
- The pipeline's container has no network (`network_mode: none`), so a scene page cannot send a video's content anywhere, whatever the engine. Each render also blocks any URL outside its own local server and prints it as a `LINT` line. Only `make transcribe` uses a container with network, to download a whisper model once.
- Inside Docker the repo is read-only except `generated_videos/`, and `make` accepts only its documented options (`SLUG`, `TITLE`, `STEP`, `FORMAT`, `PART`, `SCENE`, `FILE`, `MODEL`, `SAMPLE`).
- Keep the bind address at 127.0.0.1. On 0.0.0.0, anyone on your network could run Claude on your machine.

## Design rules

The page is a calm, dense internal tool:

1. Components come from Basecoat 1.0.2, vendored and minified in `dashboard/vendor/`; the page loads nothing from the internet.
2. Colors come from Basecoat's tokens, so light and dark follow the system setting. No gradients and no shadows of our own.
3. Loading, empty, and error states look different, and each button that cannot run says why ("Start Docker first").
4. Agent-written text is shown as text, never as HTML.
5. One main button per card; the rest are secondary or outline.
