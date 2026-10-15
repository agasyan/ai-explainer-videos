---
name: clean
description: Light paper, dark ink, and one blue accent in Inter; a calm, neutral look that suits most topics.
fits: [general, product, onboarding, data, process]
colors:
  bg: "#f7f5f0"
  ink: "#1d1d1f"
  muted: "#6e6e73"
  panel: "#ffffff"
  line: "#d9d6cf"
  accent: "#2563eb"
  accent-2: "#f59e0b"
  good: "#16a34a"
  bad: "#dc2626"
typography:
  display: Inter
  body: Inter
  mono: JetBrains Mono
shape:
  radius: 24
  stroke: 3
  style: crisp
motion:
  ease: power1.out
  duration: 0.5
  stagger: 0.1
  enter: fade-up
captions:
  ink: "#ffffff"
  bg: "rgba(20, 20, 24, 0.82)"
  now: "#ffd84d"
  key: "#7cc4ff"
three:
  fit: false
  materials: none
  camera: none
treatments: [title, big-number, flow, compare, timeline, quote]
sources: ["ev/web/base.css (this repo)", "ev/web/ev.js (this repo)"]
---
## Overview
Clean is the default look. It uses warm off-white paper, near-black ink, and one blue accent. Inter sets the titles and the body text, and JetBrains Mono sets code. Cards are white panels with a 3 px gray border and 24 px corners. Motion uses the EV tween defaults: 0.5 s with power1.out. Captions show white words on a dark pill. The current word turns yellow, and key words turn light blue.

## When to use
Use clean when the topic does not need a special look. It suits product walkthroughs, onboarding, and short data stories. Use it when a scene has many labels and the viewer must read them fast.

## Treatments
- title: Inter at 88 px, weight 800, centered. A muted subtitle at 48 px sits below it.
- big-number: Inter at 160 px, weight 800, in accent blue. Put a short muted label below it.
- flow: White cards in a row, with blue SVG arrows between them. Each card fades up when the voice names it.
- compare: Two cards side by side. Mark the old side in red (bad) and the new side in green (good).
- timeline: A thin line in the line color. Accent dots mark the events, and muted text gives the dates.
- quote: Ink text on a white card. Give the role of the speaker in muted text, not a name.

## Do and don't
- Do use one accent per point. Keep accent-2 (amber) for one second point only.
- Do keep content inside `.safe`. The captions sit below it.
- Do use green and red only for right and wrong, or for gain and loss.
- Don't set amber text on the paper. Its contrast is 1.97, so use amber for fills and strokes.
- Don't add shadows or gradients. The look is flat.
