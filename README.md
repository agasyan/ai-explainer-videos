# AI Explainer Videos

Turn any topic, PR, repo, or doc into a narrated, animated explainer video: 9:16 for stories, 16:9 for screens. An AI coding agent writes the script, the storyboard, and the animation as web code. Docker makes the voice, renders the frames, and writes the MP4 on your machine. You approve the plan and the preview. Every tool in the pipeline is open source.

> First full run passed on 2026-10-14 (Apple Silicon, Colima): `make build`, `make doctor`, and a test video on both engines.

## Quick start

1. Install Docker (Colima keeps the stack fully open source; Docker Desktop also works) and Claude Code. Install nothing else.
2. Run `make build` once (the image is about 2.1 GB), then `make doctor`.
3. Pick a path. Both make the same video, with the same two checks.

| | Path 1: the dashboard | Path 2: a Claude session |
|---|---|---|
| Start | `make dashboard`, then open http://127.0.0.1:8787. No other terminal step | Run `claude` in this folder |
| Make a video | Type a topic, press Start step 1 | `/explainer-video how DNS works` |
| Look and structure | "Recommend for me", or choose a moodboard and a video format | Claude recommends; or add `--moodboard instrument --video-format compare` |
| Skip the plan stop | Tick "Run until the 720p preview without stopping" | Add `--auto-until-preview`, and say yes when Claude Code asks |
| Approve | Approve buttons under the storyboard and the preview | Claude Code asks; yes means approve |
| 1080p and the file | Render 1080p, then Download | Claude renders it; open `generated_videos/<slug>/out/` |

Details: [docs/dashboard.md](docs/dashboard.md) for path 1. For any other coding agent, see [AGENTS.md](AGENTS.md); to run `make` by hand, see [docs/reference.md](docs/reference.md).

## Three steps, two checks

| Step | The agent | You |
|------|-----------|-----|
| 1 Plan | Researches the facts with sources, picks a video format and a moodboard (2 alternatives each), writes `script.yaml` (per beat: what the voice says and what the screen shows), makes the voice and `storyboard.md`. | Read the storyboard, listen to `build/narration.wav`, approve. |
| 2 Preview | Draws each scene as HTML/SVG, renders 720p, checks one frame per beat, fixes up to 2 passes. | Watch the 720p video, approve. |
| 3 Final | Renders 1080p (in the dashboard, you press the button). | Share. |

Nothing heavy runs before you approve the plan, and 1080p runs only after you approve the preview. Details: [docs/approval-checks.md](docs/approval-checks.md).

## What you get

- **Any topic, any look:** diagrams, UI, maps, charts, code, hand-drawn whiteboard, math. 8 moodboards set the look and 6 video formats set the structure; Claude recommends one of each ([THIRD_PARTY.md](THIRD_PARTY.md) credits their sources).
- **Formats and parts:** `story` (1080 × 1920), `landscape` (1920 × 1080), or `both`, at 30 fps. Long topics split into parts that each make sense alone.
- **Voice and captions:** Kokoro, open source and local, in US and UK English. Captions are designed into the picture: words pop in as they are said, and `*key words*` take the key color. The MP4 also carries a subtitle track, plus `.srt` and `.vtt` files.
- **3D where it helps:** three.js for spatial ideas only, 2 scenes per part at most. Untick one box for 2D only ([docs/scenes.md](docs/scenes.md#3d)).
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
- Rendering takes a while. Leave it running in the background.

## Docs

| Page | Read it to |
|------|------------|
| [how-it-works.md](docs/how-it-works.md) | understand the pipeline, the timing, and the automatic checks |
| [approval-checks.md](docs/approval-checks.md) | approve a step, and see what an approval covers |
| [writing.md](docs/writing.md) | write narration and storyboards, and split long topics |
| [scenes.md](docs/scenes.md) | draw scenes: API, formats, looks, libraries, patterns |
| [reference.md](docs/reference.md) | look up commands, `script.yaml` fields, and output files |
| [dashboard.md](docs/dashboard.md) | use the web page |
| [troubleshooting.md](docs/troubleshooting.md) | fix a step that failed |

## Credits

- Andrej Karpathy, [X post, 2026-10-02](https://x.com/karpathy/status/2105819303471976479): bespoke explainer videos and the ASD-STE100 tip.
- [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd) (MIT): the ADHD-friendly rules in [docs/writing.md](docs/writing.md).
- [Kokoro](https://github.com/thewh1teagle/kokoro-onnx), [whisper.cpp](https://github.com/ggml-org/whisper.cpp), [Playwright](https://playwright.dev), [HyperFrames](https://github.com/heygen-com/hyperframes) (Apache-2.0), [rough.js](https://roughjs.com), [KaTeX](https://katex.org), [three.js](https://threejs.org), [ffmpeg](https://ffmpeg.org).

## License

MIT, see [LICENSE](LICENSE). Each tool in the pipeline keeps its own license ([docs/how-it-works.md](docs/how-it-works.md#open-source)).
