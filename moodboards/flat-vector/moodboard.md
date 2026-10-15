---
name: flat-vector
description: Bright solid shapes on a deep navy field; friendly and clear, for science and big-picture why questions.
fits: [science, space, biology, technology, why-questions]
colors:
  bg: "#1b2a4a"
  ink: "#f7f9ff"
  muted: "#a3b3d6"
  panel: "#25385f"
  line: "#3a5084"
  accent: "#ffc93c"
  accent-2: "#3ec7e0"
  good: "#5ad17a"
  bad: "#ff5d73"
typography:
  display: Inter
  body: Inter
  mono: JetBrains Mono
shape:
  radius: 32
  stroke: 1
  style: crisp
motion:
  ease: back.out
  duration: 0.5
  stagger: 0.08
  enter: pop
captions:
  ink: "#ffffff"
  bg: "rgba(14, 21, 40, 0.82)"
  now: "#ffc93c"
  key: "#3ec7e0"
three:
  fit: true
  materials: flat unlit toon fills, no outlines
  camera: orthographic front view, slow turn
treatments: [title, big-number, flow, compare, timeline, stage-3d]
sources: ["University of Michigan: https://artsatmichigan.umich.edu/ink/2019/09/27/simple-bright-beautiful-the-work-of-kurzgesagt", "Flat illustration guide: https://www.linearity.io/blog/flat-illustration-guide"]
---
## Overview
Flat vector art: a small set of bright colors on a deep navy field, and each shape is one solid fill. Shapes come from circles, rectangles, and triangles, with round corners and no stroke. The style "avoids textures, gradients, and perspective-based rendering". The palette is chosen for this tool; the sources give no hex values. Text uses Inter, because no rounded sans font is installed. Elements pop in with a slight overshoot (`back.out`, 0.5 s, 0.08 s apart). `stroke: 1` is the schema minimum: use it only for thin arrows and guide lines.

## When to use
Friendly science (space, biology, technology) and big-picture "why" questions, where one simple shape stands for a large idea. For history told through photos, use archival.

## Treatments
- title: one bold Inter line over a large flat shape, such as a planet or a cell, that pops in first.
- big-number: the number in `accent` inside a solid circle; the circle pops in, then the number.
- flow: rounded boxes in solid fills, linked by short arrows in `muted`; each box pops in when the voice names it.
- compare: two panels side by side, each with one icon made of basic shapes; `good` and `bad` mark the result.
- timeline: a straight bar with solid circles for events; each circle pops in on its date.
- stage-3d: three.js shapes with flat unlit toon fills, no outlines, and an orthographic camera, so they match the 2D shapes. Use it only when depth explains the idea.

## Do and don't
- Do use a small set of colors from this palette, and fill each shape with one solid color.
- Do build each icon from circles, rectangles, and triangles with round corners.
- Don't add textures, gradients, outlines, or drop shadows.
- Don't draw 2D scenes in perspective; keep them flat and front-on.
- Don't use `elastic` or `bounce` eases; the small `back.out` overshoot is enough.
