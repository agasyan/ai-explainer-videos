# Third-party material

This repo is MIT licensed ([LICENSE](LICENSE)). This file lists material from other projects that the repo itself holds or adapts. Tools that the Docker image installs keep their own licenses ([docs/how-it-works.md](docs/how-it-works.md#open-source)).

## Held in this repo

| Material | Where | Source | License |
|----------|-------|--------|---------|
| Basecoat 1.0.2 CSS, minified | `dashboard/vendor/basecoat-1.0.2/` | [basecoat-css on npm](https://www.npmjs.com/package/basecoat-css) | MIT, copy in that folder |
| Swatch images | `moodboards/*/swatch.jpg` | rendered by `make catalog` with the fonts below | the fonts' licenses allow rendered images |

## Adapted

| What we took | Where | Source | License |
|--------------|-------|--------|---------|
| File shape: YAML design tokens on top, prose rules below. No text copied | `moodboards/*/moodboard.md` | [google-labs-code/design.md](https://github.com/google-labs-code/design.md) | Apache-2.0 |
| Idea: a storyboard names color roles, not raw colors. No text copied | `ev/catalog.py`, the storyboard | [HyperFrames frame presets](https://github.com/heygen-com/hyperframes/tree/main/skills/hyperframes-creative/frame-presets) | Apache-2.0 |
| 5 color values and the 1.0 s run time | `moodboards/math-dark/` | [Manim Community colors](https://docs.manim.community/en/stable/reference/manim.utils.color.manim_colors.html) | MIT |
| 5 color values: paper, ink, rules, and the dark form | `moodboards/editorial/` | [Tufte CSS](https://github.com/edwardtufte/tufte-css) | MIT |

Each moodboard lists its sources in its `sources:` field. A source that only gives facts or rules, such as 14 CFR 25.1322 for the alert colors in `instrument`, is cited there and not listed here.

## Fonts the moodboards name

The Docker image installs these fonts. The repo holds no font files. Each license was read from the font file's license field on 2026-10-15.

| Font | Debian package or source | License |
|------|--------------------------|---------|
| Inter | `fonts-inter` | SIL Open Font License 1.1 |
| Noto Sans, Noto Serif, Noto Serif Display | `fonts-noto-core` | SIL Open Font License 1.1 |
| JetBrains Mono | `fonts-jetbrains-mono` | SIL Open Font License 1.1 |
| Caveat | [google/fonts](https://github.com/google/fonts/tree/main/ofl/caveat) | SIL Open Font License 1.1 |
| Liberation Sans Narrow | `fonts-liberation` 1.07 | GPL-2.0 with a font exception: a document or video that uses the font does not become GPL |

To add a font to a moodboard, install it in the `Dockerfile`, add it to `FONTS` in `ev/catalog.py`, and add a row here after you read its license file upstream.
