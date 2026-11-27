# AI Explainer Videos

Turn any topic, PR, repo, doc, recording, or HTML page into a narrated, animated explainer video: 9:16 for stories, 16:9 for screens. An AI coding agent reads your sources, writes the script, and draws the animation as web code: diagrams, infographics, and 3D where it helps. Docker makes the voice, renders the frames, and writes the MP4 on your machine. You check two things: the intent (what the video says, to whom) and the 720p video. Every tool in the pipeline is open source.

> First full run passed on 2026-10-14 (Apple Silicon, Colima): `make build`, `make doctor`, and a test video on both engines.

## Quick start

1. Install Docker (Colima keeps the stack fully open source; Docker Desktop also works) and Claude Code. Install nothing else.
2. Run `make build` once (the image is about 2.1 GB), then `make doctor`.
3. Pick a path. Both make the same video, with the same checks.

| | Path 1: the dashboard | Path 2: a Claude session |
|---|---|---|
| Start | `make dashboard`, then open http://127.0.0.1:8787. No other terminal step | Run `claude` in this folder |
| Make a video | **+ New video**, add your sources, press Start video | `/explainer-video how DNS works` |
| From an HTML page | A source row of kind HTML page | `/explainer-video ~/reports/q3-review.html` |
| Look and structure | "Recommend for me", or choose a moodboard and a video format | Claude recommends; or add `--moodboard instrument --video-format compare` |
| Approve | Approve the intent, then the 720p video | Claude Code asks; yes means approve |
| The file | Download | Open `projects/<YYYYMMDD>-<name>/out/` |
| 1080p (optional) | Render 1080p, next to its verdict | Claude asks, with the verdict |

Details: [docs/dashboard.md](docs/dashboard.md) for path 1. For any other coding agent, see [AGENTS.md](AGENTS.md); to run `make` by hand, see [docs/reference.md](docs/reference.md).

## Four steps, two checks

Each video is a project folder, `projects/<YYYYMMDD>-<name>/`, made when the work starts. Its sources, notes, research, intent, script, scenes, and renders all stay inside it, and git ignores it. Videos made before projects stay in `generated_videos/`.

| Step | The agent | You |
|------|-----------|-----|
| 1 Intent | Reads every source into the project, guesses the viewers, picks a video format and a look, and writes `intent.md`: the key message, the story, what to keep and cut. | Read one page, approve or ask for changes. |
| 2 Plan | Researches the facts with sources (when web research is on), writes the script, and makes the voice. | Nothing: no stop. |
| 3 Preview | Draws each scene with the [visual patterns](docs/visual-patterns.md), checks one frame per beat, renders 720p, fixes up to 2 passes. | Watch the 720p video, with its script and voice, and approve. That video is the final. |
| 4 1080p (optional) | Says if 1080p is worth it: "not needed" for drawn scenes, "worth it for big screens" for page captures and screenshots. | Say yes only for a projector, a TV, or a public upload. |

An HTML page is a source, not the video: Claude retells its point in its own story, and zooms into the page only for evidence. Details: [docs/approval-checks.md](docs/approval-checks.md), [docs/from-html.md](docs/from-html.md).

## What you get

- **Any topic, any look:** diagrams, UI, maps, charts, code, hand-drawn whiteboard, math. 8 moodboards set the look and 6 video formats set the structure; Claude recommends one of each ([THIRD_PARTY.md](THIRD_PARTY.md) credits their sources).
- **Formats and parts:** `story` (1080 × 1920), `landscape` (1920 × 1080), or `both`, at 30 fps. Long topics split into parts that each make sense alone.
- **Voice and captions:** Kokoro, open source and local, in US and UK English. Captions are designed into the picture: the whole sentence shows like a film subtitle, the said word lights up, and `*key words*` take the key color. Each scene is a chapter mark in the MP4. The MP4 also carries a subtitle track, plus `.srt` and `.vtt` files.
- **3D where it helps:** three.js for spatial ideas only, 2 scenes per part at most. Untick one box for 2D only ([docs/scenes.md](docs/scenes.md#3d)).
- **From an HTML page:** a report, a docs page, or an artifact becomes a short story of its point, with zoom-ins on the evidence ([docs/from-html.md](docs/from-html.md)).
- **Open source and offline:** every tool has an open-source license, and renders run with no network. Two engines: Playwright (default), or [HyperFrames](https://github.com/heygen-com/hyperframes) for screen recordings inside a scene ([docs/how-it-works.md](docs/how-it-works.md#engines)).

## Rules for work content

1. **Render locally.** The voice, the frames, and the video stay on your machine; only your coding agent sees the source.
2. **Zero customer data** in narration or on screen: no names, emails, phone numbers, passport numbers, booking references, or card data. Use fake values.
3. **Zero secrets.** If a diff shows a key or token, leave it out and tell the owner to rotate it.
4. **Internal stays internal.** An explainer of an internal PR or repo is Confidential: share it in internal channels, not on public social accounts.
5. **Facts only.** The agent states what it read and lists guesses in the brief.

## Tips

- Use the strongest model at high effort, and expect one or two rounds of changes.
- Give a reference video: `make reference FILE=ref.mp4` measures its words and cuts per minute, and the agent matches them.
- A 2-minute video renders at 720p in about 1.5 min on 4 CPUs. Set `EV_WORKERS=2` if Docker has little memory.

## Docs

| Page | Read it to |
|------|------------|
| [how-it-works.md](docs/how-it-works.md) | understand the pipeline, the timing, and the automatic checks |
| [approval-checks.md](docs/approval-checks.md) | approve a step, and see what an approval covers |
| [writing.md](docs/writing.md) | write narration and storyboards, and split long topics |
| [scenes.md](docs/scenes.md) | draw scenes: API, formats, looks, libraries, patterns |
| [visual-patterns.md](docs/visual-patterns.md) | pick the picture for each kind of content |
| [from-html.md](docs/from-html.md) | make a video from an HTML page |
| [reference.md](docs/reference.md) | look up commands, `script.yaml` fields, and output files |
| [dashboard.md](docs/dashboard.md) | use the web page |
| [troubleshooting.md](docs/troubleshooting.md) | fix a step that failed |

## Credits

- Andrej Karpathy, [X post, 2026-10-02](https://x.com/karpathy/status/2105819303471976479): bespoke explainer videos and the ASD-STE100 tip.
- [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd) (MIT): the ADHD-friendly rules in [docs/writing.md](docs/writing.md).
- [Kokoro](https://github.com/thewh1teagle/kokoro-onnx), [whisper.cpp](https://github.com/ggml-org/whisper.cpp), [Playwright](https://playwright.dev), [HyperFrames](https://github.com/heygen-com/hyperframes) (Apache-2.0), [rough.js](https://roughjs.com), [KaTeX](https://katex.org), [three.js](https://threejs.org), [ffmpeg](https://ffmpeg.org).

## License

MIT, see [LICENSE](LICENSE). Each tool in the pipeline keeps its own license ([docs/how-it-works.md](docs/how-it-works.md#open-source)).
