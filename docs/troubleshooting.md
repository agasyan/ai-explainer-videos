# Troubleshooting

| Symptom | Fix |
|---------|-----|
| `make build` is killed or very slow | Give Docker 4 CPUs and 6 GB RAM, for example `colima start --cpu 4 --memory 6` |
| `Approval check: the 720p preview is not approved` | `make video` needs it: run `make status SLUG=<slug>`, check the changed file, then approve the preview again |
| `The plan changed after the preview` | Run `make narrate` and a full `make preview`, then approve |
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
| `EV= is not an option here` | `make` takes only `SLUG`, `TITLE`, `STEP`, `FORMAT`, `PART`, `SCENE`, `FILE`, `MODEL`, `SAMPLE`; this keeps a value from replacing a command. Environment variables such as `EV_WORKERS=2 make preview SLUG=dns` still work |
| `Read-only file system` | Put the file inside `projects/` or `generated_videos/`; Docker can write only there |
| `No video named dns in projects/ or generated_videos/` | Start it with `make new SLUG=dns`, or give the full project id that `make new` printed |
| `NOTE not copied: ... (Name or service not known)` | Colima's DNS stopped answering. Run `colima restart` (it stops running containers), or `colima start --dns 1.1.1.1`, then `make from-html SLUG=<project id>` again |
| `Move videos/<slug> to generated_videos/<slug>` | Local videos moved: run `mv videos/<slug> generated_videos/` once per video |
| `Run one target at a time` | Give `make` one command per run, for example `make status SLUG=dns`; two targets could approve a step without the prompt |
| Claude Code refuses a `make` command with a `-` option | Options such as `-f` are denied so they cannot load another makefile. Leave them out, and keep ` -` out of `TITLE` |
| `hyperframes render failed` | Read the last lines it prints. If Chrome was killed, set `EV_HF_WORKERS=1` or give Docker more memory |
| `hyperframes wrote 224 frames, and the voice needs 223` | Report it with the HyperFrames version from `make doctor`; use `engine: playwright` until it is fixed |
| A `<video>` clip is frozen or blank | Set `engine: hyperframes`, add `class="clip"` and `muted`, and check the `src` path is `../assets/<file>` |
| `make doctor` says `FAIL HyperFrames engine` | Run `make build` again; the image did not get the CLI or its Chrome |
| `make build` fails with `Could not resolve host` | A short DNS failure inside Colima: run `make build` again; finished layers come from the cache |
| `SyntaxError` or `No such file` just after you edit a file | Colima's file sharing can show the container an old copy for a few seconds. Wait 5 s and run the command again |
| `FILE must be an .html or .htm page` | `make from-html` takes one HTML file. Save the page as HTML first |
| `NOTE not copied (host not on the list): <host>` | `make from-html` copies scripts and styles only from the CDNs in `ev/fromhtml.py` (`HOSTS`). Save the file next to the page and link it with a relative path, then run `make from-html` again |
| `NOTE blocked a request to ...` after `sections` | The page loads a file that is not in `assets/page/`. The capture shows the page without it |
| `The page has 9 sections at the story width and 7 at the landscape width` | The page hides sections on a narrow screen. Make one format at a time: `FORMAT=landscape` |
| A page capture is cut off at the top, or a menu covers it | `sections` hides fixed bars and unsticks sticky ones; for anything else, edit `assets/page/index.html` and run `make from-html SLUG=<slug>` again |
