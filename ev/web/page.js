/* EV.page: show one captured section of a page (make from-html) inside .safe, and move a camera over it.
 * Load it after ev.js. A scene that `make from-html` writes:
 *
 *   EV.page("s03", { bg: "rgb(255, 255, 255)", w: 832, parts: [...] }).then(p => { EV.ready(); });
 *
 * The camera: a section shorter than the frame sits in the middle and zooms in slowly (zoom); a taller one scrolls
 * from its top to its bottom while the voice talks. The image is assets/page/shots/<format>/<id>.png, made by
 * `ev sections` at the page's own layout for that format, at 2x (`w` is the section's width in page px).
 * The section grows to fill the frame's width, up to `max` times its page size.
 *
 * Highlights: p.mark(box, start, end) draws a box around a region of the section from `start` to `end` (seconds,
 * usually from EV.at; end is optional). `box` is [x, y, w, h] in page px, or one of p.parts (a table, chart, code
 * block, or sub-heading, from build/sections.json), before EV.ready():
 *
 *   EV.page("s03", {...}).then(p => { p.mark(p.parts[0], EV.at("s03-a", "cheapest")); EV.ready(); });
 *
 * Keep a mark inside the part of the section the camera shows at that time.
 */
(() => {
  EV.page = async (id, { bg, w: pageWidth, zoom = 1.04, max = 2, parts = [] } = {}) => {
    const format = EV.portrait ? "story" : "landscape";
    const safe = document.querySelector(".safe");
    if (!safe) throw new Error('EV.page needs a <div class="safe"> in the scene');
    const frame = safe.appendChild(Object.assign(document.createElement("div"), { className: "ev-page" }));
    const sheet = frame.appendChild(Object.assign(document.createElement("div"), { className: "ev-page-sheet" }));
    const img = sheet.appendChild(Object.assign(document.createElement("img"), { className: "ev-page-shot", alt: "" }));
    img.src = `../assets/page/shots/${format}/${id}.png`;
    try {
      await img.decode();
    } catch {
      throw new Error(`No capture for section ${id} in ${format}: run make from-html SLUG=<slug> FORMAT=${format}`);
    }
    if (bg) document.querySelector(".stage").style.background = bg;
    const fw = frame.clientWidth, fh = frame.clientHeight;
    const density = pageWidth ? img.naturalWidth / pageWidth : 2;  // image px per page px
    const scale = Math.min(fw / (img.naturalWidth / density), max);  // frame px per page px
    const w = img.naturalWidth / density * scale, h = img.naturalHeight / density * scale;
    Object.assign(sheet.style, { width: `${w}px`, height: `${h}px`, left: `${(fw - w) / 2}px`,
      top: `${h < fh ? (fh - h) / 2 : 0}px` });
    const duration = EV.data.duration;
    if (h <= fh) {
      EV.fromTo(sheet, { scale: 1 }, { scale: zoom, duration, ease: "none" }, 0);
    } else {  // scroll down while the voice talks: start after a short look at the top, end a little before the cut
      const start = Math.min(1, duration * 0.1), end = Math.max(start + 0.5, duration - 0.8);
      EV.fromTo(sheet, { y: 0 }, { y: fh - h, duration: end - start, ease: "sine.inOut" }, start);
    }
    const mark = (box, start, end) => {
      const [x, y, bw, bh] = Array.isArray(box) ? box : [box.x, box.y, box.w, box.h];
      const m = sheet.appendChild(Object.assign(document.createElement("div"), { className: "ev-page-mark" }));
      Object.assign(m.style, { left: `${x * scale - 10}px`, top: `${y * scale - 10}px`,
        width: `${bw * scale + 20}px`, height: `${bh * scale + 20}px` });
      EV.fromTo(m, { opacity: 0, scale: 1.04 }, { opacity: 1, scale: 1, duration: 0.35 }, start);
      if (end != null) EV.to(m, { opacity: 0, duration: 0.3 }, end);
      return m;
    };
    return { frame, sheet, img, scale, width: w, height: h, parts, mark };
  };
})();
