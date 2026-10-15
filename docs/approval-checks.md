# Approval checks

Two checks keep heavy work behind a person's OK: the plan before any rendering, and the 720p preview before 1080p.

| Step | The agent makes | You check | Approve with |
|------|-----------------|-----------|--------------|
| 1 Plan | `script.yaml` (brief, picks, plus `say` and `show` per beat), `storyboard.md`, the voice, `build/narration.wav` | Right story for the viewer? Facts right? Words and pictures make sense? | `make approve SLUG=<slug> STEP=plan` |
| 2 Preview | `scenes/*.html`, a 720p MP4, contact sheets | Each frame matches its `show`? Nothing broken? Zero customer data or secrets? Right audience? | `make approve SLUG=<slug> STEP=preview` |
| 3 Final | The 1080p MP4 and SRT | Watch it once | (no check) |

## How to approve

Pick one:

- **Claude Code:** the agent runs `make approve ...`, and Claude Code asks you to allow it. Allow means approve. Decline and type a change to request changes.
- **Dashboard:** press Approve and continue, or type a change and press Request changes ([dashboard.md](dashboard.md)). The button sends the fingerprint of what the page showed; if a file changed since, the approval is refused with "Changed since you looked: check again".
- **Terminal:** run `make approve SLUG=<slug> STEP=plan` (or `preview`). `make status SLUG=<slug>` shows where a video is.

## What an approval covers

- The plan check covers `script.yaml` and, for a topic, `research.md`: approving the plan approves the facts.
- `generated_videos/<slug>/approved.json` stores a hash of what you approved, the time (UTC), and your user name. It stays on your machine with the video.
- **Plan** covers `script.yaml`, except each beat's `hold` and the top-level `format`, `look`, `moodboard`, `three`, `captions`, and `engine` lines. Those are timing, look, and rendering, which the preview check covers. The `video_format` line is in the plan: it sets the structure.
- **Preview** covers `script.yaml`, `style.css`, `scenes/`, and `assets/`, plus the formats you previewed. For a video with a `moodboard:` line, it also covers that moodboard's file, so a change to the moodboard asks for a new preview check.
- The checks read `script.yaml` line by line, and the pipeline reads it as YAML. `make narrate` and the renders refuse a script where the two could differ: write those keys as plain `key: value` lines, and `moodboard:` once, at the top level, unquoted.
- If you edit a covered file, the approval stops counting. `make status` shows `CHANGED`, and the next render refuses to run. Check the change, then approve again.
- `make video FORMAT=story` needs an approved story preview. `FORMAT=both` needs both.

## Auto until preview

To skip the plan stop, give your consent once: tick the box in the dashboard's New video form, or answer yes when Claude runs `make auto SLUG=<slug>` (an `ask` rule, like `make approve`).

- The consent is stored as `auto` in `approved.json`. `make status` shows the plan as `AUTO`.
- 720p then runs without a plan approval. 1080p still needs the preview approval.
- Approving the preview also approves the plan it was made from, marked "approved with the preview". Check the storyboard as part of that preview check.
- Any approval uses the consent up, so a later plan edit needs a plan check again.

## Why the agent cannot approve

- `.claude/settings.json` puts `make approve` and `make auto` under `ask`, so Claude Code always asks you. It also denies the agent edits to `approved.json`.
- Approvals count only from a file named exactly `approved.json`. On a disk that ignores letter case (the macOS default), an agent could otherwise write `Approved.json` past the deny rule; a case variant counts as not approved, and the next approval deletes it.
- Work in Claude Code's default permission mode (the project setting). macOS ignores letter case, and path rules such as "ask before editing the Makefile" may not match `MAKEFILE`; in default mode, every edit asks anyway.
- In headless runs (the dashboard), `ask` means denied. The agent stops and ends with `WAITING FOR APPROVAL: <slug> <step>`.
- ⚠️ Unverified: check that your permission mode still prompts for `ask` rules.
- The check stops mistakes, not people: anyone with the repo can edit `approved.json` by hand.
