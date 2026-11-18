# Approval checks

Two stops. The **intent** comes first: what the video says, to whom, and how, before any script. The **720p preview** comes last: it is the final video, and approving it also approves the script and the voice it was made from. Between them, Claude researches, writes the script, makes the voice, and draws the scenes with no stop.

| Step | The agent makes | You check | Approve with |
|------|-----------------|-----------|--------------|
| 1 Intent | `intent.md`: the key message, the viewers, the sources and their roles, the story, the look, what to keep and cut, the evidence, research questions | Right message for the right viewers? Right story and look? Anything to cut or add? | `make approve SLUG=<id> STEP=intent` |
| 2 Plan | `research.md`, `script.yaml` (per beat: `say` and `show`), the voice, `storyboard.md` | Nothing now: you check it with the preview | (with the preview) |
| 3 Preview | `scenes/*.html`, a 720p MP4, contact sheets, and the 1080p verdict | The script and the voice in the video? Each frame matches its `show`? Nothing broken? Zero customer data or secrets? Right audience? | `make approve SLUG=<id> STEP=preview` |
| 4 1080p (optional) | The 1080p MP4 and SRT, only when you say yes | Watch it once | (no check) |

The tool enforces the order: `make narrate`, `make stills`, and `make preview` refuse to run until the intent is approved, and stop again if `intent.md` changes after its approval. A video made before the intent step (no `intent.md`) skips it.

## How to approve

Pick one:

- **Claude Code:** the agent runs `make approve ...`, and Claude Code asks you to allow it. Allow means approve. Decline and type a change to request changes.
- **Dashboard:** press Approve, or type a change and press Request changes ([dashboard.md](dashboard.md)). The button sends the fingerprint of what the page showed; if a file changed since, the approval is refused with "Changed since you looked: check again".
- **Terminal:** run `make approve SLUG=<slug> STEP=preview`. `make status SLUG=<slug>` shows where a video is.

## The intent check

- You read one short page. Claude guesses the viewers from the sources, so correct them if the guess is wrong.
- Request changes (dashboard) or decline the prompt and say what to change (Claude Code): Claude edits `intent.md` and asks again.
- In the dashboard, the job stops at "Your turn: check the intent". Approve, and Claude goes on to the preview with no other stop.

## 1080p: the verdict

Each full 720p render ends with a `VERDICT 1080p:` line, also in `make status`, `build/verdict.json`, and the dashboard.

| Verdict | When | What to do |
|---------|------|------------|
| not needed | Every scene is drawn: EV's lint keeps text at 28 px or more, which 720p shows sharply | Share the 720p video |
| worth it for big screens | The video shows page captures ([from-html.md](from-html.md)), or `assets/` holds screenshots or clips: their own small text loses detail at 720p | 720p is fine on a laptop or phone. Render 1080p for a projector, a TV, or a public upload |

1080p needs the approved preview, and only for the formats you approved: `make video FORMAT=story` needs an approved story preview, and `FORMAT=both` needs both.

## What an approval covers

- The intent check covers `intent.md`. The preview approval also approves the plan (`script.yaml` and, for a topic, `research.md`), so it approves the facts.
- `approved.json` in the video's folder (`projects/<id>/`, or `generated_videos/<slug>/` for an older video) stores a hash of what you approved, the time (UTC), and your user name. It stays on your machine with the video.
- **Plan** covers `script.yaml`, except each beat's `hold` and the top-level `format`, `look`, `moodboard`, `three`, `captions`, and `engine` lines. Those are timing, look, and rendering, which the preview check covers. The `video_format` line is in the plan: it sets the structure.
- **Preview** covers `script.yaml`, `style.css`, `scenes/`, and `assets/`, plus the formats you previewed. For a video with a `moodboard:` line, it also covers that moodboard's file, so a change to the moodboard asks for a new preview check.
- The checks read `script.yaml` line by line, and the pipeline reads it as YAML. `make narrate` and the renders refuse a script where the two could differ: write those keys as plain `key: value` lines, and `moodboard:` once, at the top level, unquoted.
- If you edit a covered file, the approval stops counting. `make status` shows `CHANGED`, and `make video` refuses to run. Check the change, then approve again.
- Approving the preview refuses a plan that changed after the render: run `make narrate` and a full `make preview` first.

## Why the agent cannot approve

- `.claude/settings.json` puts `make approve` under `ask`, so Claude Code always asks you. It also denies the agent edits to any `approved.json`.
- Approvals count only from a file named exactly `approved.json`. On a disk that ignores letter case (the macOS default), an agent could otherwise write `Approved.json` past the deny rule; a case variant counts as not approved, and the next approval deletes it.
- Work in Claude Code's default permission mode (the project setting). macOS ignores letter case, and path rules such as "ask before editing the Makefile" may not match `MAKEFILE`; in default mode, every edit asks anyway.
- In headless runs (the dashboard), `ask` means denied. The agent stops and ends with `WAITING FOR APPROVAL: <slug> <step>`.
- ⚠️ Unverified: check that your permission mode still prompts for `ask` rules.
- The check stops mistakes, not people: anyone with the repo can edit `approved.json` by hand.
