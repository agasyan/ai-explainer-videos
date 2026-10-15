# Drawing scenes

A scene is one HTML page: `generated_videos/<slug>/scenes/<scene id>.html`. Draw with HTML, SVG, CSS, rough.js, or KaTeX, and animate with the `EV` runtime. Its full API is the comment at the top of [ev/web/ev.js](../ev/web/ev.js). Starter scenes are in [templates/video/scenes/](../templates/video/scenes/).

## Page skeleton

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="/ev/base.css">
<link rel="stylesheet" href="../style.css">
<script src="/ev/ev.js"></script>
</head>
<body>
<div class="stage">
  <div class="safe">
    <h1 class="title">How DNS works</h1>
  </div>
</div>
<script>
const { at, end } = EV;
EV.from(".title", { opacity: 0, y: 40, duration: 0.8 }, at("hook"));
EV.ready();
</script>
</body>
</html>
```

## Animation API

The calls look like GSAP, but the last argument is always an absolute time in seconds, usually from `EV.at`.

| Call | Does |
|------|------|
| `EV.at("beat")` | Returns the second the beat starts |
| `EV.at("beat", "word")` | Returns the second the voice starts that word or phrase; a third argument picks the nth match |
| `EV.end("beat")` | Returns the second the beat's voice ends |
| `EV.from(target, vars, t)` | Animates from `vars` to the current state; hidden in the `from` state until `t` |
| `EV.to(target, vars, t)` | Animates from the state before it to `vars` |
| `EV.fromTo(target, fromVars, toVars, t)` | Animates between two given states |
| `EV.set(target, vars, t)` | Changes instantly at `t` |
| `EV.draw(target, t, duration)` | Draws SVG strokes on |
| `EV.path(target, "#route", t, duration)` | Moves a marker along an SVG path; add `{ rotate: true }` to turn it with the path |
| `EV.type(target, t, duration)` | Types text on, letter by letter |
| `EV.count(target, from, to, t, duration)` | Counts a number up or down |
| `EV.onFrame(t => ...)` | Calls your function on every frame, for canvas or other drawing computed from time |
| `EV.ready()` | Must be the last line of every scene |

**Vars:** `duration` (default 0.5), `ease` (default `power1.out`; also `power0` to `power4`, `sine`, `expo`, `circ`, `back`, `elastic`, `bounce`, each with `.in`, `.out`, or `.inOut`, and `none`), `stagger` (seconds between targets), and the properties `x`, `y` (px), `scale`, `scaleX`, `scaleY`, `rotate` (deg), `opacity`, any numeric CSS property, colors (`color`, `backgroundColor`, `fill`, `stroke`, `borderColor`, including `var(--accent)`), and SVG attributes as `attr: { r: 40 }`.

## Rules

1. Animate only through `EV`. Use no CSS transitions, `setTimeout`, `setInterval`, or `requestAnimationFrame`. CSS `@keyframes` are fine. Use the class `clip` only for [video clips](#video-clips).
2. Do not set a CSS `transform` on an animated element; use `x`, `y`, `scale`, and `rotate`.
3. Put content inside `.safe`. Captions sit below it.
4. Text: 28 px or more, 8 words or fewer per block, 2 blocks or fewer on screen.
5. Same color, same concept, for the whole video.

## Formats

| Format | Page size (CSS px) | `.safe` box | Captions |
|--------|--------------------|-------------|----------|
| `landscape` | 1920 × 1080 | 96 px from the sides, 72 px from the top, 200 px from the bottom | 60 px from the bottom |
| `story` | 1080 × 1920 | 60 px from the sides, 250 px from the top, 600 px from the bottom | 380 px from the bottom |

The story box keeps clear of Instagram's UI (⚠️ check current Instagram guidance). For `both`, use `.row`, which stacks in story, or branch on `EV.portrait`.

## Moodboards

A moodboard is the look of a video: colors, fonts, shapes, motion, and captions. `script.yaml` names one with `moodboard:`. Each one is a file in `moodboards/<name>/moodboard.md`: YAML values on top, then prose with its treatments and its do and don't rules. Read the file before you write scenes. `make catalog` checks every moodboard and renders its `swatch.jpg`.

| `moodboard` | Fits | 3D |
|-------------|------|----|
| `clean` | the default: product walkthroughs, onboarding, short data stories | no |
| `whiteboard` | ideas explained step by step, with rough.js and the Caveat hand font | no |
| `math-dark` | math, algorithms, physics; close to the 3Blue1Brown style | yes |
| `editorial` | history, policy, essays: text, dates, and quotes | no |
| `instrument` | aviation, monitoring, incidents: red for warnings, amber for cautions | yes |
| `blueprint` | machines and system internals: white line art on blue | yes |
| `flat-vector` | friendly science: solid flat shapes, no outlines | yes |
| `archival` | history told through photos, with slow pan and zoom | no |

The renderer turns the YAML into CSS variables in `/ev/theme.css` (link it after `base.css`, as the templates do), and into EV's default `ease` and `duration`. Each scene uses one of the moodboard's `treatments` (`title`, `big-number`, `flow`, `compare`, `timeline`, `quote`, `stage-3d`), drawn as its prose says. The old `look:` field still works: `look: dark` is `math-dark`, and `clean` and `whiteboard` keep their names.

| Variable | From the moodboard |
|----------|--------------------|
| `--bg`, `--ink`, `--muted`, `--panel`, `--line`, `--accent`, `--accent-2`, `--good`, `--bad` | `colors` |
| `--font`, `--display`, `--mono` | `typography` (body, display, mono) |
| `--radius`, `--stroke` | `shape` |
| `--cap-ink`, `--cap-bg`, `--cap-now`, `--cap-key` | `captions` |

Override any variable in the video's `style.css`, but keep the moodboard's contrast: ink on bg 4.5:1 or more, muted and accent 3:1 or more. Base classes: `.title`, `.subtitle`, `.label`, `.small`, `.big-number`, `.card`, `.row`, `.mono`, `.hand`, `.accent`, `.accent-2`, `.good`, `.bad`, `.muted`. Put images in `generated_videos/<slug>/assets/` and use `<img src="../assets/name.png">`.

## Libraries and fonts

| Library | Add to the page | Use for |
|---------|-----------------|---------|
| EV runtime | in the template | tweens, timing, captions, lint |
| rough.js 4.6 | `<script src="/vendor/roughjs/bundled/rough.js"></script>` | hand-drawn boxes, arrows, and circles |
| KaTeX 0.19 | `/vendor/katex/dist/katex.min.js` and `katex.min.css` | formulas |
| three.js 0.186 | an importmap to `/vendor/three/build/three.module.js` ([3D](#3d)) | 3D, only with `three: true` and a `three_why` |
| Fonts | installed | Inter, Noto Sans, Noto Serif, Noto Serif Display, Noto Color Emoji (icons), JetBrains Mono (code), Caveat (handwriting), Liberation Sans Narrow |

## 3D

Use 3D only for a spatial idea: orientation, rotation, depth, or a mechanism. Text, numbers, timelines, and comparisons stay 2D. The dashboard's "Allow 3D where it explains better" box (ticked by default) sets `three: true` in `script.yaml`.

1. The scene gets `treatment: stage-3d` (only moodboards with `three.fit: true` have it) and a one-line `three_why`.
2. 2 scenes with 3D per part, at most. `make narrate` prints `CHECK` for a third.
3. With `three: false`, the renderer serves no three.js, and a scene that loads it stops the render: "three.js is off for this video".
4. 3D renders with `engine: playwright` only. Chromium draws it in software WebGL; `make doctor` checks that the same frame gives the same pixels twice.

```html
<canvas id="c" width="1920" height="1080"></canvas>
<script type="importmap">{"imports": {"three": "/vendor/three/build/three.module.js", "three/addons/": "/vendor/three/examples/jsm/"}}</script>
<script type="module">
import * as THREE from "three";
const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById("c"), alpha: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(40, 16 / 9, 0.1, 100);
camera.position.set(0, 0, 6);
const accent = getComputedStyle(document.body).getPropertyValue("--accent").trim();
const box = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(2, 2, 2)),
                                   new THREE.LineBasicMaterial({ color: accent }));
scene.add(box);
const state = { turn: 0 };  // EV tweens plain objects too, before each frame's painters run
EV.to(state, { turn: Math.PI / 3, duration: 2 }, EV.at("rotate"));
EV.onFrame(() => { box.rotation.set(0.4, state.turn, 0); renderer.render(scene, camera); });
EV.ready();  // last, inside the module script: module scripts run after the others
</script>
```

`alpha: true` lets the moodboard background show through. WebGL lines are 1 px wide; for thicker lines, use `Line2` from `three/addons/lines/`. Draw in `EV.onFrame` from `t` alone. For random numbers use `EV.random(seed)`, never `Math.random`, so every render is the same. Labels stay in HTML over the canvas, so captions, fonts, and lint work as in 2D.

## Video clips

A scene can play a screen recording or other footage, if `script.yaml` sets `engine: hyperframes`. The `playwright` engine does not seek video.

```html
<video class="clip" muted data-start="at:demo:click save" data-duration="4" data-track-index="1"
       src="../assets/demo.mp4" style="width: 1200px"></video>
```

| Attribute | Meaning |
|-----------|---------|
| `class="clip"`, `muted` | Required. The voice is the only sound. |
| `data-start` | Seconds from the scene start (`"2.5"`), or `"at:beat"` or `"at:beat:phrase"`: the same times as `EV.at` |
| `data-duration` | Seconds on screen |
| `data-track-index` | Any whole number; give overlapping clips different numbers |

Put the file in `generated_videos/<slug>/assets/`. Show only what the viewer may see: no customer data and no secrets in a recording. To move or fade a clip, wrap it in a `<div>` and animate the div with `EV`. Do not animate, play, pause, or seek the `<video>` itself: HyperFrames does that.

## Patterns

- **Flow:** boxes (`.card`) in a `.row`, with SVG arrows between them drawn by `EV.draw` as each box is named.
- **Before and after:** two `.card` columns; the "after" column fades in at the word "now".
- **Chart:** SVG bars that tween `scaleY` from 0, with `EV.count` on their labels.
- **Code:** `<pre class="mono">` revealed with `EV.type`; highlight one line by tweening its `backgroundColor`.
- **Whiteboard:** shapes from `rough.svg(svg).rectangle(...)`, appended to an `<svg>`, then `EV.draw(svg.querySelectorAll("path"), t, 1, { stagger: 0.1 })`.
- **Route or map:** draw the route with `EV.draw`, then move a plane along it with `EV.path(".plane", "#route", t, 3, { rotate: true })`.
