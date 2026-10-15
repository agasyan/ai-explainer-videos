---
name: editorial
description: A quiet print page with serif text and thin rules; for history, policy, and essays told in words.
fits: [history, policy, essays]
colors:
  bg: "#fffff8"
  ink: "#111111"
  muted: "#666666"
  panel: "#fffff8"
  line: "#cccccc"
  accent: "#1f4e79"
  accent-2: "#8a5a00"
  good: "#2e6b30"
  bad: "#b00000"
typography:
  display: Noto Serif Display
  body: Noto Serif
  mono: JetBrains Mono
shape:
  radius: 0
  stroke: 2
  style: crisp
motion:
  ease: sine.inOut
  duration: 1.4
  stagger: 0.2
  enter: fade
captions:
  ink: "#111111"
  bg: "rgba(255, 255, 248, 0.92)"
  now: "#8a5a00"
  key: "#1f4e79"
three:
  fit: false
  materials: none, flat print only
  camera: none
treatments: [title, big-number, flow, compare, timeline, quote]
sources: ["Tufte CSS: https://raw.githubusercontent.com/edwardtufte/tufte-css/gh-pages/tufte.css"]
---
## Overview
A quiet print page: warm off-white paper (#fffff8), near-black text (#111111), and thin gray rules (#cccccc). These three values and the dark form of the page (bg #151515, ink #dddddd) come from the source stylesheet. The other colors are chosen for this tool. There are no boxes and no shadows; the panel color is the paper color, and corners are square. Rules are thin (2 px). One deep blue accent marks the main idea, and it shows rarely. Red marks danger only. Noto Serif sets the body text, Noto Serif Display sets titles and large numbers, and JetBrains Mono sets code. Text fades in slowly: 1.4 s with `sine.inOut`, 0.2 s apart. Captions show ink words on a paper strip; the current word turns ochre, and key words turn blue.

## When to use
Use it for history, policy, and essays: topics that rest on text, dates, and quotes. For history told through photos, use archival.

## Treatments
- title: a large serif title, a thin rule below it, and a muted subtitle.
- big-number: one large serif number in ink, with a short muted label; use the accent only when the number is the main point.
- flow: steps as short serif lines, joined by thin rules and small arrows; no boxes.
- compare: two text columns with one thin vertical rule between them; red marks a real danger only.
- timeline: one thin horizontal rule; dates in muted text above it, and events in ink below it.
- quote: a large serif quote with wide margins, and the source in muted text under a short rule.

## Do and don't
- Do separate ideas with thin rules and white space.
- Do let each fade finish before the next one starts.
- Do use the accent at most once on a screen.
- Don't draw boxes, cards, shadows, or round corners.
- Don't use red except for danger.
