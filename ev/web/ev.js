/* EV page runtime. Animation is a pure function of time, so every frame renders the same way every time.
 *
 *   const { at, end } = EV;
 *   EV.from(".title", { opacity: 0, y: 40, duration: 0.8 }, at("hook"));                  // when beat "hook" starts
 *   EV.to(".car", { x: 600, duration: 1.5, ease: "power2.inOut" }, at("hook", "drives"));  // when the voice says "drives"
 *   EV.fromTo(".dot", { scale: 0 }, { scale: 1, ease: "back.out(2)" }, end("hook"));       // when the beat's voice ends
 *   EV.set(".old", { opacity: 0 }, at("next"));    // instant change
 *   EV.draw("#route", at("route"), 1.5);           // draw SVG strokes on
 *   EV.path(".plane", "#route", at("route"), 3);   // move along an SVG path (marker drawn around 0,0 in the same <svg>)
 *   EV.type(".cmd", at("run"), 1.2);               // typewriter text
 *   EV.count(".price", 0, 120, at("cost"), 1);     // number counter
 *   EV.onFrame(t => paintCanvas(t));               // canvas or other drawing computed from t
 *   EV.ready();                                    // last line of every scene
 *
 * Times are seconds from the scene start; the last argument is always an absolute time, usually from EV.at.
 * Tween vars: duration (default 0.5), ease (default "power1.out"; also power0-4, sine, expo, circ, back(s),
 * elastic, bounce, each with .in, .out, or .inOut, and "none"), stagger (seconds between targets), and these
 * properties: x, y (px), scale, scaleX, scaleY, rotate (deg), opacity, any numeric CSS property (width, fontSize,
 * strokeDashoffset), colors (color, backgroundColor, fill, stroke, borderColor; var(--accent) works), and SVG
 * attributes as attr: { r: 40 }. Do not set a CSS transform on an animated element; use x, y, scale, and rotate.
 *
 * Rules: animate only through EV. Use no CSS transitions, setTimeout, setInterval, or requestAnimationFrame:
 * the renderer calls EV.seek(t) for each frame. CSS @keyframes are fine; the renderer seeks them too.
 * Put content inside .safe; captions sit below it. EV.portrait is true for story (1080 x 1920 CSS px).
 * Optional libraries: /vendor/roughjs/bundled/rough.js (hand-drawn shapes),
 * /vendor/katex/dist/katex.min.js and katex.min.css (math), and three.js for 3D, only when script.yaml says
 * `three: true` and the scene has a `three_why` (docs/scenes.md, "3D"): an importmap maps "three" to
 * /vendor/three/build/three.module.js; one <script type="module"> builds the scene, draws in
 * EV.onFrame(t => { ...; renderer.render(scene, camera); }), and calls EV.ready() last. Use
 * EV.random(seed) for random numbers, never Math.random: every frame must render the same way every time.
 * The renderer calls EV.lint() on the frame before each next beat and prints every issue as a LINT line.
 * Both engines (script.yaml `engine:`) run this file unchanged. With engine: hyperframes, a scene can also play
 * <video class="clip" muted data-start="at:beat:phrase" data-duration="4" data-track-index="1" src="../assets/x.mp4">
 * (data-start: seconds, or at: like EV.at); HyperFrames seeks it frame by frame. See docs/scenes.md, "Video clips".
 */
(() => {
  const D = window.EV_DATA || { scene: "demo", format: "landscape", look: "clean", captions: "off",
    width: 1920, height: 1080, frames: 300, duration: 10, beats: [], cues: [] };
  const root = document.documentElement;
  const MOTION = D.motion || {};  // the moodboard's default ease and duration (moodboards/<name>/moodboard.md)
  root.dataset.format = D.format;
  root.dataset.look = D.look;
  const tracks = new Map();  // one per target and property: { target, kind, prop, base, list: [tween] }
  const painters = [];
  const warnings = [];
  let built = false;
  const norm = w => w.toLowerCase().replace(/[^a-z0-9']/g, "");

  // ---------- beats ----------

  function beat(id) {
    const b = D.beats.find(x => x.id === id);
    if (!b) throw new Error(`No beat "${id}" in scene "${D.scene}". Beats: ${D.beats.map(x => x.id).join(", ")}`);
    return b;
  }

  // Seconds from the scene start when beat `id` starts, or when its voice starts the nth match of `phrase`.
  function at(id, phrase, nth = 1) {
    const b = beat(id);
    if (!phrase) return b.start;
    const want = phrase.split(/\s+/).map(norm);
    const said = b.words.map(w => norm(w.w));
    const hits = said.map((_, i) => i).filter(i => want.every((w, k) => said[i + k] === w));
    if (hits.length < nth) throw new Error(`"${phrase}" is not in beat "${id}": ${b.text}`);
    return b.words[hits[nth - 1]].start;
  }

  const end = id => beat(id).end;

  // ---------- easing (GSAP names) ----------

  const C4 = (2 * Math.PI) / 3;
  const bounceOut = p => {
    const n = 7.5625, d = 2.75;
    if (p < 1 / d) return n * p * p;
    if (p < 2 / d) return n * (p -= 1.5 / d) * p + 0.75;
    if (p < 2.5 / d) return n * (p -= 2.25 / d) * p + 0.9375;
    return n * (p -= 2.625 / d) * p + 0.984375;
  };
  const EASE_IN = {
    power0: () => p => p,
    power1: () => p => p ** 2,
    power2: () => p => p ** 3,
    power3: () => p => p ** 4,
    power4: () => p => p ** 5,
    sine: () => p => 1 - Math.cos((p * Math.PI) / 2),
    expo: () => p => (p === 0 ? 0 : 2 ** (10 * p - 10)),
    circ: () => p => 1 - Math.sqrt(1 - p * p),
    back: (s = 1.70158) => p => p * p * ((s + 1) * p - s),
    elastic: () => p => (p === 0 || p === 1 ? p : -(2 ** (10 * p - 10)) * Math.sin((p * 10 - 10.75) * C4)),
    bounce: () => p => 1 - bounceOut(1 - p),
  };

  function ease(name = "power1.out") {
    if (typeof name === "function") return name;
    if (name === "none" || name === "linear") return p => p;
    const m = /^([a-z]+\d?)(?:\.(in|out|inOut))?(?:\(([^)]*)\))?$/.exec(name);
    if (!m || !EASE_IN[m[1]]) throw new Error(`Unknown ease "${name}". Use power0-4, sine, expo, circ, back, elastic, bounce, or none.`);
    const f = EASE_IN[m[1]](m[3] ? parseFloat(m[3]) : undefined);
    if (m[2] === "in") return f;
    if (m[2] === "inOut") return p => (p < 0.5 ? f(2 * p) / 2 : 1 - f(2 - 2 * p) / 2);
    return p => 1 - f(1 - p);
  }

  // ---------- values ----------

  const TRANSFORM = { x: 0, y: 0, rotate: 0, scale: 1, scaleX: 1, scaleY: 1 };
  const UNITLESS = new Set(["opacity", "zIndex", "fontWeight", "lineHeight", "flexGrow"]);
  const COLORS = new Set(["color", "backgroundColor", "fill", "stroke", "borderColor", "outlineColor"]);
  const RESERVED = new Set(["duration", "ease", "stagger"]);
  const canvas = document.createElement("canvas").getContext("2d");

  function cssVar(v) {
    const m = /^var\((--[\w-]+)\)$/.exec(String(v).trim());
    return m ? getComputedStyle(root).getPropertyValue(m[1]).trim() : v;
  }

  function rgba(css) {  // any CSS color -> [r, g, b, a]; the canvas normalizes the syntax
    canvas.fillStyle = "#000";
    canvas.fillStyle = cssVar(css);
    const s = canvas.fillStyle;
    if (s[0] === "#") return [1, 3, 5].map(i => parseInt(s.slice(i, i + 2), 16)).concat(1);
    return s.match(/[\d.]+/g).map(Number).concat(1).slice(0, 4);
  }

  function unitOf(kind, prop) {
    if (kind === "a" || kind === "o" || UNITLESS.has(prop) || prop.startsWith("scale")) return "";
    return prop === "rotate" ? "deg" : "px";
  }

  function parse(kind, prop, v) {
    if (kind === "c" && COLORS.has(prop)) return { c: rgba(v) };
    if (typeof v === "number") return { n: v, u: unitOf(kind, prop) };
    const m = /^(-?[\d.]+)([a-z%]*)$/i.exec(String(cssVar(v)).trim());
    if (!m) throw new Error(`Cannot animate ${prop} to "${v}": use a number, a number with a unit, or a color`);
    return { n: parseFloat(m[1]), u: m[2] || unitOf(kind, prop) };
  }

  function current(target, kind, prop) {  // the value before any tween runs
    if (kind === "t") return { n: TRANSFORM[prop], u: unitOf(kind, prop) };
    if (kind === "a") return { n: parseFloat(target.getAttribute(prop)) || 0, u: "" };
    if (kind === "o") return { n: Number(target[prop]) || 0, u: "" };
    const v = getComputedStyle(target)[prop];
    return COLORS.has(prop) ? { c: rgba(v) } : parse(kind, prop, parseFloat(v) || 0);
  }

  const mix = (a, b, p) => (a.c ? { c: a.c.map((x, i) => x + (b.c[i] - x) * p) } : { n: a.n + (b.n - a.n) * p, u: b.u });

  // ---------- tweens ----------

  function targets(t) {
    if (typeof t === "string") {
      const found = [...document.querySelectorAll(t)];
      if (!found.length) throw new Error(`No element matches "${t}" in scene "${D.scene}"`);
      return found;
    }
    if (t instanceof Element) return [t];
    if (t && typeof t.length === "number") return [...t];  // NodeList or array
    return [t];  // a plain object, for numbers you read in EV.onFrame
  }

  const ids = new WeakMap();
  let nextId = 0;
  function track(target, kind, prop) {
    if (!ids.has(target)) ids.set(target, ++nextId);
    const key = `${ids.get(target)}|${kind}|${prop}`;
    if (!tracks.has(key)) tracks.set(key, { target, kind, prop, base: kind === "f" ? null : current(target, kind, prop), list: [] });
    return tracks.get(key);
  }

  function add(target, fromVars, toVars, time, mode) {
    if (built) throw new Error("Add every tween before EV.ready()");
    if (typeof time !== "number" || !isFinite(time)) throw new Error(`Tween time must be seconds, got ${time}. Use EV.at(...)`);
    const vars = (mode === "from" ? fromVars : toVars) || {};
    const duration = mode === "set" ? 0 : vars.duration ?? MOTION.duration ?? 0.5;
    const easing = ease(vars.ease ?? MOTION.ease);
    targets(target).forEach((el, i) => {
      const plain = !(el instanceof Element);
      const props = new Map();
      const put = (kind, prop, side, v) => {
        const p = props.get(kind + prop) || { kind, prop };
        p[side] = parse(kind, prop, v);
        props.set(kind + prop, p);
      };
      const take = (obj, side) => {
        for (const [k, v] of Object.entries(obj || {})) {
          if (k === "attr") Object.entries(v).forEach(([a, av]) => put("a", a, side, av));
          else if (k === "onUpdate") throw new Error("onUpdate is not supported: use EV.onFrame(t => ...)");
          else if (!RESERVED.has(k)) put(plain ? "o" : k in TRANSFORM ? "t" : "c", k, side, v);
        }
      };
      take(mode === "fromTo" || mode === "from" ? fromVars : null, "from");
      take(mode === "from" ? null : toVars, "to");
      for (const p of props.values()) {
        track(el, p.kind, p.prop).list.push({ start: time + i * (vars.stagger || 0), duration, ease: easing,
          from: p.from, to: p.to, hideBefore: p.from !== undefined });
      }
    });
  }

  function custom(el, name, start, duration, easeName, render) {
    if (built) throw new Error("Add every tween before EV.ready()");
    track(el, "f", name).list.push({ start, duration, ease: ease(easeName), render });
  }

  const from = (target, vars, time) => add(target, vars, null, time, "from");
  const to = (target, vars, time) => add(target, null, vars, time, "to");
  const fromTo = (target, fromVars, toVars, time) => add(target, fromVars, toVars, time, "fromTo");
  const set = (target, vars, time) => add(target, null, vars, time, "set");

  function draw(target, time, duration = 1, { stagger = 0, ease: e = "power1.inOut" } = {}) {
    targets(target).forEach((el, i) => {
      const length = el.getTotalLength();
      el.style.strokeDasharray = length;
      fromTo(el, { strokeDashoffset: length }, { strokeDashoffset: 0, duration, ease: e }, time + i * stagger);
    });
  }

  function path(target, route, time, duration = 1, { ease: e = "power1.inOut", rotate = false } = {}) {
    const line = typeof route === "string" ? document.querySelector(route) : route;
    if (!line) throw new Error(`No path matches "${route}" in scene "${D.scene}"`);
    const length = line.getTotalLength();
    targets(target).forEach(el => custom(el, "path", time, duration, e, p => {
      const d = p * length;
      const here = line.getPointAtLength(d);
      const s = Math.max(0, Math.min(d, length - 1));  // heading: from a point to the point 1 unit further on
      const a = line.getPointAtLength(s);
      const b = line.getPointAtLength(s + 1);
      el.style.translate = `${here.x}px ${here.y}px`;
      if (rotate) el.style.rotate = `${(Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI}deg`;
    }));
  }

  function type(target, time, duration = 1, easeName = "none") {
    targets(target).forEach(el => {
      const full = el.textContent;
      custom(el, "text", time, duration, easeName, p => { el.textContent = full.slice(0, Math.round(p * full.length)); });
    });
  }

  function count(target, fromValue, toValue, time, duration = 1, format = v => Math.round(v).toLocaleString("en-US"), easeName = "power1.out") {
    targets(target).forEach(el => custom(el, "text", time, duration, easeName,
      p => { el.textContent = format(fromValue + (toValue - fromValue) * p); }));
  }

  // ---------- frames ----------

  const progress = (tween, t) => (tween.duration > 0 ? tween.ease(Math.min(1, (t - tween.start) / tween.duration)) : 1);

  function render(t) {
    const transforms = new Map();
    for (const tr of tracks.values()) {
      let k = -1;
      for (let i = 0; i < tr.list.length; i++) if (tr.list[i].start <= t) k = i;
      if (tr.kind === "f") {
        const tw = tr.list[Math.max(k, 0)];
        tw.render(k < 0 ? 0 : progress(tw, t));
        continue;
      }
      const first = tr.list[0];
      const v = k < 0 ? (first.hideBefore ? first.from : tr.base) : mix(tr.list[k].from, tr.list[k].to, progress(tr.list[k], t));
      if (tr.kind === "t") {
        const m = transforms.get(tr.target) || { ...TRANSFORM };
        m[tr.prop] = v.n;
        transforms.set(tr.target, m);
      } else if (tr.kind === "a") {
        tr.target.setAttribute(tr.prop, v.n);
      } else if (tr.kind === "o") {
        tr.target[tr.prop] = v.n;
      } else {
        tr.target.style[tr.prop] = v.c ? `rgba(${v.c.slice(0, 3).map(Math.round).join(", ")}, ${v.c[3]})` : v.n + v.u;
      }
    }
    for (const [el, m] of transforms) {
      el.style.transform = `translate(${m.x}px, ${m.y}px) rotate(${m.rotate}deg) scale(${m.scale * m.scaleX}, ${m.scale * m.scaleY})`;
    }
  }

  // ---------- captions ----------
  // "pop": words appear as the voice says them, and the current word pops. "line": the whole line shows, and
  // words light up. Words in *asterisks* in `say` get the key color. Colors and font follow the look (base.css).

  let captions = null;
  let line = null;
  let spans = [];
  let shownCue = null;
  function paintCaptions(t) {
    if (!captions) return;
    const cue = D.cues.find(c => t >= c.start && t < c.end) || null;
    if (cue !== shownCue) {
      shownCue = cue;
      captions.replaceChildren();
      spans = [];
      if (cue) {
        line = captions.appendChild(Object.assign(document.createElement("span"), { className: "line" }));
        spans = cue.words.map(w => line.appendChild(
          Object.assign(document.createElement("span"), { className: w.key ? "w key" : "w", textContent: w.w })));
      }
    }
    if (!cue) return;
    const enter = Math.min(1, (t - cue.start) / 0.15);  // the line rises and fades in over 0.15 s
    line.style.opacity = enter;
    line.style.transform = `translateY(${(1 - enter) * 16}px)`;
    spans.forEach((s, i) => {
      const since = t - cue.words[i].start;
      const next = i + 1 < cue.words.length ? cue.words[i + 1].start : cue.end;
      s.classList.toggle("on", since >= 0);
      s.classList.toggle("now", since >= 0 && t < next);
      s.style.transform = `scale(${1 + 0.15 * (since >= 0 ? Math.max(0, 1 - since / 0.18) : 0)})`;  // pop, then settle
    });
  }

  function seek(t) {
    render(t);
    document.getAnimations().forEach(a => { a.pause(); a.currentTime = t * 1000; });
    painters.forEach(paint => paint(t));
    paintCaptions(t);
  }

  // ---------- checks ----------

  // Layout check for the current frame: text outside .safe, text under 28 px, overlapping text.
  function lint() {
    const safe = document.querySelector(".safe");
    if (!safe) return ['no .safe element: put the content inside <div class="safe">'];
    const box = safe.getBoundingClientRect();
    const shown = el => {
      for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
        const s = getComputedStyle(e);
        if (s.display === "none" || s.visibility === "hidden" || parseFloat(s.opacity) < 0.05) return false;
      }
      return true;
    };
    const texts = [...safe.querySelectorAll("*")].filter(e => !e.closest(".katex, .no-lint") && shown(e)
      && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()));
    const rects = texts.map(e => e.getBoundingClientRect());
    const name = e => `"${e.textContent.trim().slice(0, 30)}"`;
    const issues = [];
    texts.forEach((e, i) => {
      const r = rects[i];
      if (r.left < box.left - 2 || r.right > box.right + 2 || r.top < box.top - 2 || r.bottom > box.bottom + 2)
        issues.push(`text leaves the safe area: ${name(e)}`);
      const px = e instanceof SVGElement ? r.height / 1.2
        : parseFloat(getComputedStyle(e).fontSize) * (e.offsetHeight ? r.height / e.offsetHeight : 1);
      if (px < 28) issues.push(`text under 28 px: ${name(e)}`);
    });
    for (let i = 0; i < texts.length; i++) {
      for (let j = i + 1; j < texts.length; j++) {
        if (texts[i].contains(texts[j]) || texts[j].contains(texts[i])) continue;
        const x = Math.min(rects[i].right, rects[j].right) - Math.max(rects[i].left, rects[j].left);
        const y = Math.min(rects[i].bottom, rects[j].bottom) - Math.max(rects[i].top, rects[j].top);
        if (x > 4 && y > 4) issues.push(`text overlaps: ${name(texts[i])} and ${name(texts[j])}`);
      }
    }
    return issues;
  }

  function ready() {
    let last = 0;
    for (const tr of tracks.values()) {
      tr.list.sort((a, b) => a.start - b.start);
      let prev = tr.base;
      for (const tw of tr.list) {
        if (tr.kind !== "f") {  // a "to" tween starts from the value before it; a "from" tween ends there
          tw.from = tw.from ?? prev;
          tw.to = tw.to ?? prev;
          prev = tw.to;
        }
        last = Math.max(last, tw.start + tw.duration);
      }
    }
    if (last > D.duration + 0.05)
      warnings.push(`animation runs ${(last - D.duration).toFixed(1)}s past the scene's voice: add hold to a beat in script.yaml, or shorten tweens`);
    built = true;
    const host = document.querySelector("#ev-root") || document.body;  // #ev-root: the HyperFrames engine's root
    if (D.captions !== "off") {
      captions = host.appendChild(Object.assign(document.createElement("div"), { className: "ev-captions" }));
      captions.dataset.style = D.captions;
    }
    seek(0);
    // HyperFrames engine: its runtime owns the clock and calls seek(t) once per frame.
    const hf = window.__hyperframes;
    if (hf && hf.registerFrameSource && host !== document.body)
      hf.registerFrameSource({ element: host, ready: document.fonts.ready, render: t => seek(t) });
    window.EV_READY = true;
  }

  // Seeded random numbers (mulberry32): the same seed gives the same numbers in every frame and every render.
  function random(seed = 1) {
    let a = seed >>> 0;
    return () => {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  window.EV = { at, end, beat, from, to, fromTo, set, draw, path, type, count, ease, random,
    onFrame: fn => painters.push(fn), seek, lint, ready, warnings,
    data: D, portrait: D.format === "story", width: D.width, height: D.height };
})();
