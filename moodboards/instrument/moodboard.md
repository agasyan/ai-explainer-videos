---
name: instrument
description: A dark glass-cockpit screen with boxed readouts and strict alert colors, for aviation, operations, and incident timelines.
fits: [aviation, monitoring, operations, incidents]
colors:
  bg: "#0b1016"
  ink: "#e6edf3"
  muted: "#8a99a8"
  panel: "#111a24"
  line: "#2b3a4a"
  accent: "#2ec7f0"
  accent-2: "#ffb020"
  good: "#33d17a"
  bad: "#ff3b30"
typography:
  display: Liberation Sans Narrow
  body: Inter
  mono: JetBrains Mono
shape:
  radius: 4
  stroke: 2
  style: crisp
motion:
  ease: power2.out
  duration: 0.4
  stagger: 0.08
  enter: fade
captions:
  ink: "#b8c4cf"
  bg: "rgba(0, 0, 0, 0.6)"
  now: "#ffffff"
  key: "#2ec7f0"
three:
  fit: true
  materials: glowing cyan lines on black, no solid faces
  camera: orthographic, or a slow orbit
treatments: [title, big-number, flow, compare, timeline, stage-3d]
sources:
  - "14 CFR 25.1322: https://www.law.cornell.edu/cfr/text/14/25.1322"
---
## Overview
This board looks like a glass cockpit or a monitoring screen: light text and thin lines on a near-black background, with values in boxed readouts, tape scales, and dials. The alert colors follow 14 CFR 25.1322(e): red for warnings, amber or yellow for cautions, and any color except red or green for advisories. Rule (f) limits other uses of red, amber, and yellow. So `bad` is a red for warnings only, `accent-2` is an amber for cautions only, `accent` is a cyan for normal readouts and advisories, and `good` is a green for a normal state. The hex values are a palette chosen for this tool, because the source gives color names, not hex values.

## When to use
Use it for flight topics, system monitoring, on-call operations, and incident timelines, where a state moves from normal to caution to warning and back. Do not use it for a calm or historical topic, or when the story has no states to show.

## Treatments
- `title`: Narrow display caps in a thin box, with a mono status line below.
- `big-number`: One boxed mono readout with its unit, beside a tape scale that slides to the value.
- `flow`: Boxes joined by thin lines; a cyan marker moves along the path, one step at a time.
- `compare`: Two dials or two tapes side by side, on the same scale, with one label each.
- `timeline`: A horizontal time tape in 24-hour time; each event is a tick with a boxed label in its alert color.
- `stage-3d`: An attitude sphere or a flight path as glowing cyan lines on black, with an orthographic camera or a slow orbit.

## Do and don't
- Do use red only for a warning and amber only for a caution. Use cyan for all other highlights.
- Do let an alert appear and then stay steady. Never loop, blink, or pulse it.
- Do put each value in a box with its unit, in the mono font.
- Don't use green or red for an advisory.
- Don't copy a real panel layout, and don't show a maker's name or logo.
