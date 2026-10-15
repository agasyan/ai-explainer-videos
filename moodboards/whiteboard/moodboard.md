---
name: whiteboard
description: Off-white board, marker ink, Caveat hand font, and rough.js shapes; an informal look for ideas and processes.
fits: [concepts, teaching, process, brainstorm]
colors:
  bg: "#fbfaf6"
  ink: "#22223b"
  muted: "#6b705c"
  panel: "#ffffff"
  line: "#22223b"
  accent: "#1d4ed8"
  accent-2: "#e85d04"
  good: "#16a34a"
  bad: "#dc2626"
typography:
  display: Caveat
  body: Caveat
  mono: JetBrains Mono
shape:
  radius: 24
  stroke: 3
  style: rough
motion:
  ease: power1.inOut
  duration: 1.0
  stagger: 0.1
  enter: draw
captions:
  ink: "#22223b"
  bg: "rgba(255, 255, 255, 0.92)"
  now: "#e85d04"
  key: "#1d4ed8"
three:
  fit: false
  materials: none
  camera: none
treatments: [title, big-number, flow, compare, timeline]
sources: ["ev/web/base.css (this repo)", "ev/web/ev.js (this repo)", "docs/scenes.md (this repo)"]
---
## Overview
Whiteboard looks like marker on a white board. The board is off-white, and the ink is a dark blue-gray. Blue and orange are the two marker colors. Caveat sets all text, so every word looks handwritten. JetBrains Mono still sets code. rough.js draws boxes, arrows, and circles with a hand-drawn line, and `EV.draw` reveals each stroke. Captions show ink words on a white card in Caveat. The current word turns orange, and key words turn blue. Captions run at 64 px, larger than in clean, because Caveat runs small.

## When to use
Use whiteboard to explain an idea step by step, as a teacher does at a board. It suits concepts, processes, and early plans. Do not use it for dense tables or long code. Caveat is hard to read at small sizes.

## Treatments
- title: Caveat at 88 px, centered. A short rough line draws on below it.
- big-number: Caveat at 160 px in blue, with a rough circle drawn around it.
- flow: Rough boxes joined by rough arrows. Each box draws on in turn, 0.1 s apart.
- compare: Two rough boxes side by side. Cross out the old side in red, and tick the new side in green.
- timeline: A rough line with hand-drawn dots. Write each date in muted ink next to its dot.

## Do and don't
- Do draw shapes with rough.js, and reveal them with `EV.draw`.
- Do draw boxes in the ink color. Use blue or orange only for the point that matters.
- Do keep code in JetBrains Mono. Caveat does not suit code.
- Don't write long sentences on the board. Use a few words per label.
- Don't mix crisp CSS borders and rough shapes in one scene.
