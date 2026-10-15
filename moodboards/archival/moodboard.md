---
name: archival
description: Paper tones and serif captions over stills that pan and zoom slowly; for history and biography told through photos and documents.
fits: [history, biography, archives, documents]
colors:
  bg: "#f1e9da"
  ink: "#2b2620"
  muted: "#6b6152"
  panel: "#e6dcc8"
  line: "#c9bba1"
  accent: "#7b4a2a"
  accent-2: "#4d6070"
  good: "#56683a"
  bad: "#9a3a2a"
typography:
  display: Noto Serif Display
  body: Noto Serif
  mono: JetBrains Mono
shape:
  radius: 2
  stroke: 2
  style: crisp
motion:
  ease: sine.inOut
  duration: 1.2
  stagger: 0.2
  enter: fade
captions:
  ink: "#f6efe2"
  bg: "rgba(34, 29, 24, 0.82)"
  now: "#e3c98f"
  key: "#dba882"
three:
  fit: false
  materials: none, depth comes from flat image layers
  camera: slow pan-and-zoom over stills, done in 2D
treatments: [title, quote, timeline, compare, big-number]
sources: ["Wikipedia: https://en.wikipedia.org/wiki/Ken_Burns_effect"]
---
## Overview
Archival: history told through photos and documents. Each still moves with a slow pan-and-zoom, and fading transitions link the stills. The camera comes to rest on the person or object that the narrator names. The colors are desaturated paper tones; the palette is chosen for this tool, because the source gives no hex values. Titles use Noto Serif Display, and body text and captions use Noto Serif. Graphics are few, because the stills carry the story. For depth, cut a still into 2 or 3 layers and move them at different speeds (simulated parallax). This is CSS layer work, so `three.fit` is false. Text fades in over 1.2 s (`sine.inOut`), 0.2 s apart.

## When to use
History and biography, when you have photos, letters, maps, or newspaper pages to show. For a process or a system with many parts, use a diagram look such as flat-vector.

## Treatments
- title: the title in Noto Serif Display on a paper panel, over a still that zooms in slowly.
- quote: a short quote in Noto Serif, with the speaker and year below in `muted`; the lines fade in one by one.
- timeline: a thin ink rule with serif dates; the camera pans along it and stops on each date that the voice names.
- compare: two stills side by side in square-cornered frames, each with one serif label below.
- big-number: one year or count in Noto Serif Display, on a paper panel next to its still.

## Do and don't
- Do keep every still in motion with a slow zoom or pan for the full beat.
- Do end each move on the subject that the voice names, then fade to the next still.
- Do desaturate color stills toward paper tones, for example with a CSS `sepia()` or `grayscale()` filter.
- Don't add icons, charts, or bouncy eases; use one graphic per scene at most.
- Don't make up documents: show only real records that have a source and that you have the right to use.
