# Troubleshooting

| Symptom | Fix |
|---------|-----|
| `make build` is killed or very slow | Give Docker 4 CPUs and 6 GB RAM, for example `colima start --cpu 4 --memory 6` |
| `Approval check: the plan is not approved` | Run `make status SLUG=<slug>`, check the changed file, then approve again |
| The agent approved without asking you | Your permission mode skips `ask` rules. Use the default mode for video work |
| `CHECK: the voice may say these wrong` | Respell the word as it sounds ("Kubernetes" as "koo-ber-net-eez"), then `make narrate` again |
| `LINT ...: text leaves the safe area` | Use fewer words, a smaller font, or `.row` (it stacks in story) |
| `LINT ...: text overlaps` | Fade out the old text before the new text, or move one of them |
| `LINT ...: animation runs 1.4s past the scene's voice` | Add `hold: 1.5` to the last beat, or shorten the tweens |
| `the page never called EV.ready()` | Read the JS error above it and fix the scene's script |
| `No element matches ".x"` | Fix the selector, or add the element to the page |
| `Tween time must be seconds` | Pass a time as the last argument, for example `EV.at("hook")` |
| `Unknown ease` | Use `power1.out`, `back.out(2)`, `sine.inOut`, `none`, and so on (list in `ev/web/ev.js`) |
| `"word" is not in beat` | `EV.at` phrases must match the beat's `say` text, including any respelling |
| Chromium crashes or says "Target closed" | Give Docker more memory; `compose.yaml` already sets `shm_size: 1gb` |
| A dashboard job stops at a command | Add that command to `permissions.allow` in `.claude/settings.json` |
| `EV= is not an option here` | `make` takes only `SLUG`, `TITLE`, `STEP`, `FORMAT`, `PART`, `SCENE`, `FILE`, `MODEL`; this keeps a value from replacing a command |
| `Read-only file system` | Put the file inside `generated_videos/`; Docker can write only there |
| `Move videos/<slug> to generated_videos/<slug>` | Local videos moved: run `mv videos/<slug> generated_videos/` once per video |
| `Run one target at a time` | Give `make` one command per run, for example `make status SLUG=dns`; two targets could approve a step without the prompt |
| Claude Code refuses a `make` command with a `-` option | Options such as `-f` are denied so they cannot load another makefile. Leave them out, and keep ` -` out of `TITLE` |
| `hyperframes render failed` | Read the last lines it prints. If Chrome was killed, set `EV_HF_WORKERS=1` or give Docker more memory |
| `hyperframes wrote 224 frames, and the voice needs 223` | Report it with the HyperFrames version from `make doctor`; use `engine: playwright` until it is fixed |
| A `<video>` clip is frozen or blank | Set `engine: hyperframes`, add `class="clip"` and `muted`, and check the `src` path is `../assets/<file>` |
| `make doctor` says `FAIL HyperFrames engine` | Run `make build` again; the image did not get the CLI or its Chrome |
