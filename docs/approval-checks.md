# Approval checks

One check: the 720p preview. It is the final video, and approving it approves the plan it was made from. Nothing waits for an approval before it: narrate and the 720p render run as soon as their files are ready.

| Step | The agent makes | You check | Approve with |
|------|-----------------|-----------|--------------|
| 1 Plan | `script.yaml` (brief, picks, plus `say` and `show` per beat), `storyboard.md`, the voice, `build/narration.wav` | Nothing, unless you asked for a plan check | (optional) `make approve SLUG=<slug> STEP=plan` |
| 2 Preview | `scenes/*.html`, a 720p MP4, contact sheets, and the 1080p verdict | Right story? Facts right? Each frame matches its `show`? Nothing broken? Zero customer data or secrets? Right audience? | `make approve SLUG=<slug> STEP=preview` |
| 1080p (optional) | The 1080p MP4 and SRT, only when you say yes | Watch it once | (no check) |

## How to approve

Pick one:

- **Claude Code:** the agent runs `make approve ...`, and Claude Code asks you to allow it. Allow means approve. Decline and type a change to request changes.
- **Dashboard:** press Approve, or type a change and press Request changes ([dashboard.md](dashboard.md)). The button sends the fingerprint of what the page showed; if a file changed since, the approval is refused with "Changed since you looked: check again".
- **Terminal:** run `make approve SLUG=<slug> STEP=preview`. `make status SLUG=<slug>` shows where a video is.

## A plan check, when you want one

A long video or a new topic can be worth a look before the scenes: the script is cheap to change, and the scenes are not.

- Dashboard: tick "Stop after the plan" in the New video form. Claude Code: add `--plan-check`.
- The agent stops after step 1 and asks with `make approve SLUG=<slug> STEP=plan`. Then it goes on to the preview.
- A plan you approve on its own stays approved on its own. Else the preview approval approves it, marked "approved with the preview".

## 1080p: the verdict

Each full 720p render ends with a `VERDICT 1080p:` line, also in `make status`, `build/verdict.json`, and the dashboard.

| Verdict | When | What to do |
|---------|------|------------|
| not needed | Every scene is drawn: EV's lint keeps text at 28 px or more, which 720p shows sharply | Share the 720p video |
| worth it for big screens | The video shows page captures ([from-html.md](from-html.md)), or `assets/` holds screenshots or clips: their own small text loses detail at 720p | 720p is fine on a laptop or phone. Render 1080p for a projector, a TV, or a public upload |

1080p needs the approved preview, and only for the formats you approved: `make video FORMAT=story` needs an approved story preview, and `FORMAT=both` needs both.

## What an approval covers

- The plan check covers `script.yaml` and, for a topic, `research.md`: approving the plan approves the facts.
- `approved.json` in the video's folder (`projects/<id>/`, or `generated_videos/<slug>/` for an older video) stores a hash of what you approved, the time (UTC), and your user name. It stays on your machine with the video.
- **Plan** covers `script.yaml`, except each beat's `hold` and the top-level `format`, `look`, `moodboard`, `three`, `captions`, and `engine` lines. Those are timing, look, and rendering, which the preview check covers. The `video_format` line is in the plan: it sets the structure.
- **Preview** covers `script.yaml`, `style.css`, `scenes/`, and `assets/`, plus the formats you previewed. For a video with a `moodboard:` line, it also covers that moodboard's file, so a change to the moodboard asks for a new preview check.
- The checks read `script.yaml` line by line, and the pipeline reads it as YAML. `make narrate` and the renders refuse a script where the two could differ: write those keys as plain `key: value` lines, and `moodboard:` once, at the top level, unquoted.
- If you edit a covered file, the approval stops counting. `make status` shows `CHANGED`, and `make video` refuses to run. Check the change, then approve again.
- Approving the preview refuses a plan that changed after the render: run `make narrate` and a full `make preview` first.

## Why the agent cannot approve

- `.claude/settings.json` puts `make approve` under `ask`, so Claude Code always asks you. It also denies the agent edits to `approved.json`.
- Approvals count only from a file named exactly `approved.json`. On a disk that ignores letter case (the macOS default), an agent could otherwise write `Approved.json` past the deny rule; a case variant counts as not approved, and the next approval deletes it.
- Work in Claude Code's default permission mode (the project setting). macOS ignores letter case, and path rules such as "ask before editing the Makefile" may not match `MAKEFILE`; in default mode, every edit asks anyway.
- In headless runs (the dashboard), `ask` means denied. The agent stops and ends with `WAITING FOR APPROVAL: <slug> <step>`.
- ⚠️ Unverified: check that your permission mode still prompts for `ask` rules.
- The check stops mistakes, not people: anyone with the repo can edit `approved.json` by hand.
