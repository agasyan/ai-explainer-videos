---
name: blueprint
description: White line art on blueprint blue, with a grid and dimension lines, for machines, engineering drawings, and system internals.
fits: [machines, engineering, hardware, internals]
colors:
  bg: "#1a4f8b"
  ink: "#ffffff"
  muted: "#b4cbe6"
  panel: "#1a4f8b"
  line: "#6a93c4"
  accent: "#d4ecff"
  accent-2: "#ffd166"
  good: "#ffffff"
  bad: "#ffd166"
typography:
  display: JetBrains Mono
  body: Inter
  mono: JetBrains Mono
shape:
  radius: 0
  stroke: 2
  style: crisp
motion:
  ease: power1.inOut
  duration: 0.8
  stagger: 0.12
  enter: draw
captions:
  ink: "#d4ecff"
  bg: "rgba(10, 40, 78, 0.8)"
  now: "#ffffff"
  key: "#ffd166"
three:
  fit: true
  materials: white wireframe edges on blue, no faces
  camera: orthographic, fixed or a slow turn
treatments: [title, big-number, flow, compare, timeline, stage-3d]
sources:
  - "Blueprint (Wikipedia): https://en.wikipedia.org/wiki/Blueprint"
---
## Overview
This board looks like an engineering drawing. A blueprint has "white lines on a blue background", and in that print process "color or shades of grey cannot be reproduced". So the board is two-tone, blue and white, with one yellow highlight. `panel` equals `bg`, so a box shows only its outline. `muted`, `line`, and `accent` are blue-whites that read as fainter or thinner white lines, not as new colors. `good` is white; `bad` and `accent-2` are the same yellow highlight. Display and mono text use JetBrains Mono as technical lettering. The hex values are a palette chosen for this tool, because the source gives no hex values.

## When to use
Use it for machines, mechanisms, hardware, and the inside of a system: its parts, connections, and sizes. Use it when the viewer must see how parts fit together. Do not use it when the story needs many colors, photos, or alert states.

## Treatments
- `title`: Mono caps inside a title block with a thin double border, on the grid.
- `big-number`: One mono value between two dimension arrows, with extension lines to the part it measures.
- `flow`: Outlined parts joined by lines that draw on in order, with open arrowheads.
- `compare`: Two drawings of the same part at the same scale; the highlight marks each difference.
- `timeline`: A long dimension line with ticks; each step is a mono label above its tick.
- `stage-3d`: White wireframe edges on blue, with an orthographic camera that holds still or turns slowly; no faces, no shading.

## Do and don't
- Do draw every shape as an outline on the grid. Never fill it.
- Do draw hidden parts as dashed lines, and sizes as dimension lines with arrows.
- Do let each line draw on, one part at a time, and then hold still.
- Do use the yellow highlight for one thing per scene, at most.
- Don't add a third color, a gradient, a shadow, or a grey fill.
