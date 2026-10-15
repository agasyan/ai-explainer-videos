---
name: math-dark
description: Bright lines that draw on a near-black stage; calm and exact, for math, algorithms, and proofs.
fits: [math, algorithms, geometry, physics]
colors:
  bg: "#0f1115"
  ink: "#ffffff"
  muted: "#9aa0a6"
  panel: "#1b1e24"
  line: "#2c313a"
  accent: "#58c4dd"
  accent-2: "#f7d96f"
  good: "#83c167"
  bad: "#fc6255"
typography:
  display: Inter
  body: Inter
  mono: JetBrains Mono
shape:
  radius: 12
  stroke: 3
  style: crisp
motion:
  ease: sine.inOut
  duration: 1.0
  stagger: 0.1
  enter: draw
captions:
  ink: "#ffffff"
  bg: transparent
  now: "#f7d96f"
  key: "#58c4dd"
three:
  fit: true
  materials: unlit lines and surfaces in the accent colors
  camera: slow orbit around the object
treatments: [title, big-number, flow, compare, timeline, quote, stage-3d]
sources: ["Manim color docs: https://docs.manim.community/en/stable/reference/manim.utils.color.manim_colors.html", "Manim Animation docs: https://docs.manim.community/en/stable/reference/manim.animation.animation.Animation.html"]
---
## Overview
Bright lines and shapes draw on a near-black stage, close to the 3Blue1Brown style. The accents come from the palette of an open-source math animation library: blue (#58c4dd) and yellow (#f7d96f) lead, green (#83c167) means good, and red (#fc6255) means bad. That library uses a pure black background; this look keeps the near-black #0f1115 of the old `dark` look, which it replaces. Muted text, panels, and lines also keep the old `dark` values. Text is white, as in the library. Each move takes 1.0 s and eases in and out smoothly (`sine.inOut`), close to the library default. Inter sets all text. JetBrains Mono sets code and equations, because the library's mono font is not open. Captions show white words with no background; the current word turns yellow, and key words turn blue.

## When to use
Use it for math, algorithms, geometry, and physics: ideas that a graph, a diagram, or an equation explains. Videos that ask for the old `dark` look get this look.

## Treatments
- title: a white Inter title on the dark stage, with one key word in blue.
- big-number: one large number in yellow, with a muted label below it.
- flow: boxes with thin outlines on `panel`, joined by blue arrows that draw from start to end.
- compare: two panels side by side; green marks the good side, and red marks the bad side.
- timeline: one horizontal line draws in; each event dot draws, then its label fades in.
- quote: the quote in white, one key phrase in yellow, and the source in muted text.
- stage-3d: unlit lines and surfaces in blue, yellow, and teal (#5cd0b3); the camera orbits slowly.

## Do and don't
- Do draw each line or shape first, then fade in its label.
- Do keep one meaning for each color for the whole video.
- Do set equations and code in JetBrains Mono.
- Don't add glows, shadows, or gradients.
- Don't animate two ideas at the same time; finish one move, then start the next.
