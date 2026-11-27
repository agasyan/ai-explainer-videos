// The dashboard's page logic. Agent-written text reaches the page only through textContent (see el).
const TOKEN = document.querySelector('meta[name="ev-token"]').content;
const $ = id => document.getElementById(id);
const el = (tag, { dataset = {}, ...props } = {}, kids = []) => {
  const e = Object.assign(document.createElement(tag), props);
  Object.assign(e.dataset, dataset);
  e.append(...kids);
  return e;
};
const BOOT = document.querySelector('meta[name="ev-boot"]').content;
// Every POST answers {error} on failure, so a caller can always show it: a refused token means the dashboard
// restarted after this page loaded (a new run has a new token).
const post = (url, body) => fetch(url, { method: "POST", body: JSON.stringify(body),
  headers: { "Content-Type": "application/json", "X-EV-Token": TOKEN } }).then(async r => {
  if (r.status === 403) return { error: "The dashboard restarted after this page loaded. Reload the page (Cmd+R), then try again." };
  try { return await r.json(); } catch { return { error: `The dashboard answered ${r.status}. Reload the page, then try again.` }; }
}).catch(() => ({ error: "Could not reach the dashboard. Is make dashboard still running?" }));
const clock = s => { const t = Math.max(0, Math.round(s)); return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`; };
const since = t => clock(Date.now() / 1000 - t);
const hms = t => new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });
const ago = t => { const s = Math.max(0, Math.round(Date.now() / 1000 - t)); return s < 60 ? `${s} s ago` : `${Math.floor(s / 60)} min ago`; };

// A video with its subtitle track (switch it on in the player) and a transcript: click a line to jump there.
function player(src) {
  const vtt = src.replace(/\.mp4$/, ".vtt");
  const video = el("video", { src, controls: true, preload: "metadata" },
    [el("track", { kind: "captions", srclang: "en", label: "English", src: vtt })]);
  const list = el("div", { className: "transcript" });
  fetch(vtt).then(r => (r.ok ? r.text() : "")).then(text => {
    const cues = [...text.matchAll(/(\d+):(\d+):([\d.]+) --> \S+\n(.+(?:\n.+)?)/g)]  // a caption has 1 or 2 lines
      .map(m => ({ t: +m[1] * 3600 + +m[2] * 60 + +m[3], text: m[4].replace(/\n/g, " ") }));
    list.replaceChildren(...cues.map(c => el("button", { textContent: c.text,
      onclick: () => { video.currentTime = c.t; video.play(); } })));
    video.ontimeupdate = () => {
      const k = cues.findLastIndex(c => c.t <= video.currentTime);
      [...list.children].forEach((b, i) => b.classList.toggle("now", i === k));
    };
  });
  return el("figure", {}, [video, list]);
}

// The videos to check: one large player at a time, a tab per part, and that part's review frames below it.
function videosView(videos, sheets, note) {
  const label = u => { const m = u.match(/-part(\d+)-(landscape|story)-/); return `${m ? `Part ${m[1]}` : "Video"}${u.includes("-story-") ? " · story" : ""}`; };
  const stage = el("div", { className: "stack" });
  const show = i => {
    tabs.forEach((t, k) => t.setAttribute("aria-selected", k === i));
    const stem = videos[i].split("/").pop().replace(/\.mp4$/, "");
    const own = sheets.filter(s => s.split("/").pop().startsWith(`${stem}-contact-`));
    stage.replaceChildren(el("div", { className: "big" }, [player(videos[i])]),
      ...(own.length ? [el("p", { className: "muted", textContent: "Review frames: the last moment of each beat, in order. Compare each with its On screen line in the storyboard. Click to open full size." }),
        ...own.map(s => el("a", { href: s, target: "_blank" }, [el("img", { src: s, className: "sheet", alt: "review frames" })]))] : []));
  };
  const tabs = videos.map((u, i) => el("button", { type: "button", role: "tab", textContent: label(u), onclick: () => show(i) }));
  if (videos.length) show(0);
  return [...(note ? [el("p", { className: "muted", textContent: note })] : []),
    ...(videos.length > 1 ? [el("div", { className: "tabbar", role: "tablist" }, tabs)] : []), stage];
}

// ---- md: start ----
// A small Markdown reader for agent-written files such as intent.md: headings, paragraphs, lists, bold, code, and
// http(s) links. It returns plain data; markdownView() builds elements with text nodes only, never HTML.
const MD = (() => {
  const inline = src => {
    const out = [], re = /\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g;
    let last = 0, m;
    while ((m = re.exec(src))) {
      if (m.index > last) out.push({ tag: "text", text: src.slice(last, m.index) });
      out.push(m[1] !== undefined ? { tag: "strong", text: m[1] } : m[2] !== undefined ? { tag: "code", text: m[2] }
        : { tag: "a", text: m[3], href: m[4] });
      last = re.lastIndex;
    }
    if (last < src.length) out.push({ tag: "text", text: src.slice(last) });
    return out;
  };
  const parse = src => {
    const blocks = [];
    let para = [], list = null, fence = null;
    const flush = () => { if (para.length) blocks.push({ tag: "p", kids: inline(para.join(" ")) }); para = []; };
    const endList = () => {
      if (list) blocks.push({ tag: list.tag, start: list.start, items: list.items.map(it => ({ kids: inline(it.text),
        sub: it.sub && { tag: it.sub.tag, items: it.sub.items.map(inline) } })) });
      list = null;
    };
    for (const line of String(src || "").replace(/\r/g, "").split("\n")) {
      if (fence) {
        if (/^```/.test(line)) { blocks.push({ tag: "pre", text: fence.join("\n") }); fence = null; } else fence.push(line);
        continue;
      }
      const head = line.match(/^(#{1,4})\s+(.*)$/), item = line.match(/^(\s*)(?:[-*]|(\d+)\.)\s+(.*)$/);
      if (/^```/.test(line)) { flush(); endList(); fence = []; }
      else if (head) { flush(); endList(); blocks.push({ tag: `h${Math.min(4, head[1].length + 1)}`, kids: inline(head[2]) }); }
      else if (item) {
        flush();
        const tag = item[2] ? "ol" : "ul", last = list && list.items[list.items.length - 1];
        if (last && item[1].length >= 2) {  // an indented item: one level under the item above
          if (!last.sub) last.sub = { tag, items: [] };
          last.sub.items.push(item[3]);
        } else {
          if (!list || list.tag !== tag) { endList(); list = { tag, start: item[2] ? Number(item[2]) : 1, items: [] }; }
          list.items.push({ text: item[3], sub: null });
        }
      } else if (list && /^\s{2,}\S/.test(line)) {  // a wrapped line: it belongs to the last item
        const last = list.items[list.items.length - 1];
        if (last.sub) last.sub.items[last.sub.items.length - 1] += " " + line.trim(); else last.text += " " + line.trim();
      }
      else if (!line.trim()) { flush(); endList(); }
      else { endList(); para.push(line.trim()); }
    }
    if (fence) blocks.push({ tag: "pre", text: fence.join("\n") });
    flush();
    endList();
    return blocks;
  };
  return { parse };
})();
// ---- md: end ----

// Agent-written data (storyboard, picks, research) becomes text nodes only; a link renders only for http(s).
const text = value => document.createTextNode(String(value ?? ""));
const link = (label, href) => /^https?:\/\//.test(href)
  ? el("a", { href, textContent: label, target: "_blank", rel: "noopener noreferrer" }) : text(label);
const mdNode = n => (n.tag === "text" ? text(n.text) : n.tag === "a" ? link(n.text, n.href) : el(n.tag, { textContent: n.text }));
const markdownView = src => MD.parse(src).map(b => (b.tag === "pre" ? el("pre", { textContent: b.text })
  : b.items ? el(b.tag, { start: b.start }, b.items.map(it => el("li", {}, [...it.kids.map(mdNode),
      ...(it.sub ? [el(it.sub.tag, {}, it.sub.items.map(kids => el("li", {}, kids.map(mdNode))))] : [])])))
  : el(b.tag, {}, b.kids.map(mdNode))));
const table = (head, rows) => el("div", { className: "table-wrap" }, [el("table", { className: "table" }, [
  el("thead", {}, [el("tr", {}, head.map(h => el("th", { textContent: h })))]),
  el("tbody", {}, rows.map(r => el("tr", {}, r.map(c => el("td", {}, [c instanceof Node ? c : text(c)])))))])]);
const ID = /^[a-z0-9][a-z0-9-]*$/;
const chip = hex => { const c = el("span", { className: "chip", title: hex }); if (/^#[0-9a-f]{6}$/i.test(hex)) c.style.background = hex; return c; };
const PICKS = { video_format: "Video format", moodboard: "Moodboard" };

function storyboardView(v) {
  const b = v.storyboard;
  if (!b) return [el("p", { className: "muted", textContent: v.storyboard_stale
    ? "script.yaml changed after the last narrate: step 1 runs it again." : "No storyboard yet: step 1 makes it." })];
  const out = b.reading ? [el("p", { textContent: b.reading })] : [];
  for (const key of Object.keys(PICKS)) {
    const p = b.picks[key];
    if (!p) continue;
    out.push(el("h3", { className: "sub", textContent: `${PICKS[key]}: ${p.chosen}${p.how === "form" ? " (chosen in the form)" : ""}` }));
    if (p.options.length) out.push(el("div", { className: "picks" }, p.options.map((o, i) => el("div", { className: `pick${o.name === p.chosen ? " chosen" : ""}` }, [
      ...(key === "moodboard" && ID.test(o.name) ? [el("img", { src: `/swatch/${o.name}.jpg`, alt: "" })] : []),
      el("strong", { textContent: `${i === 0 ? "Recommended" : "Alternative"}: ${o.name}` }),
      el("div", { className: "muted", textContent: o.why })]))));
  }
  if (b.direction) {
    const d = b.direction;
    out.push(el("div", { className: "direction" }, [...d.colors.map(c => el("span", { className: "role" }, [chip(c.hex), text(`${c.role}: ${c.use}`)])),
      el("div", { className: "muted", textContent: `Type: ${d.type.display}, ${d.type.body}, ${d.type.mono}. Motion: ${d.motion}.` })]));
  }
  if (b.checks.length) out.push(el("div", { className: "alert", dataset: { variant: "destructive" } },
    [el("section", {}, b.checks.map(c => el("div", { textContent: c })))]));
  // Long sections fold: each part (open) and the research table (folded; its counts are in the heading).
  const fold = (title, open, body) => el("details", { className: "fold", open }, [el("summary", { textContent: title }), body]);
  for (const part of b.parts) {
    out.push(fold(`Part ${part.n}: ${part.title} (${Math.round(part.length)} s, ${part.rows.length} beats)`, true,
      table(["#", "Time", "Voice", "On screen", "Treatment", "2D or 3D", "Sources", "Frame"], part.rows.map(r => [
        r.n, r.time, r.voice, r.show, r.treatment, r.dim, r.sources.join(", "),
        r.frame && /^frames\/[a-z]+\/[a-z0-9-]+\/[a-z0-9-]+\.jpg$/.test(r.frame)
          ? el("a", { href: `/files/${v.slug}/${r.frame}`, target: "_blank" }, [el("img", { src: `/files/${v.slug}/${r.frame}`, className: "thumb", alt: r.n })]) : ""]))));
  }
  const rs = b.research;
  if (rs.claims) {
    out.push(fold(`Research: ${rs.claims} claim${rs.claims === 1 ? "" : "s"}, ${rs.one_source} with one source${rs.no_source ? `, ${rs.no_source} with none` : ""}`, false,
      table(["id", "Claim", "Sources", "Status"], rs.rows.map(r => [r.id, r.claim,
        el("span", {}, r.links.flatMap((u, i) => [...(i ? [text(" · ")] : []), link(`source ${i + 1}`, u)])), r.status]))));
  }
  return out;
}

// ---------- the 3 steps of a video ----------

const MARK = { done: "✓", you: "●", working: "…", next: "○", locked: "·" };
const TURN = { working: "Working", you: "Your turn", next: "Next", done: "Done" };

function steps(c) {
  const st = c.status, work = c.running;
  const intent = st.intent === "none" ? ["done", "none: an older video"] : st.intent === "approved" ? ["done", "approved"]
    : ["ready", "changed"].includes(st.intent) ? ["you", st.intent === "changed" ? "changed: check again" : "your check"]
    : work ? ["working", "Claude is reading the sources"] : ["next", "not ready"];
  const intentOk = ["approved", "none"].includes(st.intent);
  const plan = st.plan === "approved" ? ["done", "approved with the preview"]
    : ["ready", "changed"].includes(st.plan) ? ["done", "ready: you check it with the preview"]
    : !intentOk ? ["locked", "after the intent"] : work ? ["working", "Claude is working"] : ["next", "next"];
  const preview = st.preview === "approved" ? ["done", "approved: the final video"]
    : ["ready", "changed"].includes(st.preview) ? ["you", st.preview === "changed" ? "changed: check again" : "your check"]
    : !intentOk ? ["locked", "after the intent"] : work ? ["working", "Claude is working"] : ["next", "next"];
  const [ready, total] = c.parts || [0, 0];
  const hd = c.finals ? ["done", "ready to download"] : st.preview === "approved"
    ? (work ? ["working", `rendering: ${ready} of ${total} parts ready`] : ["next", "optional: see the verdict"])
    : ["locked", "optional, after the preview"];
  return [["1 Intent", "message, viewers, story, look", ...intent], ["2 Plan", "research, script, voice", ...plan],
          ["3 Preview", "scenes, the 720p video, the script and voice", ...preview], ["4 1080p", "optional", ...hd]];
}

const stepper = c => steps(c).map(([name, what, state, note]) => el("li", { className: `step step-${state}` }, [
  el("span", { className: "mark", textContent: MARK[state] }),
  el("div", {}, [el("strong", { textContent: name }), el("div", { className: "muted", textContent: `${what}: ${note}` })])]));
const ministeps = c => steps(c).map(([name, , state]) => el("span", { className: `ministep step-${state}`, textContent: `${MARK[state]} ${name}` }));

// ---------- the board: one card per video ----------

let slug = null, tab = "check", cards = [], shownCheck = "", shownBoard = "";

function renderBoard() {
  const key = JSON.stringify([slug, cards.map(c => [c.slug, c.title, c.status, c.turn, c.now, c.finals, c.running && Math.floor((Date.now() / 1000 - c.since) / 10)])]);
  if (key === shownBoard) return;  // rebuild only on change (the working timer moves in 10 s steps)
  shownBoard = key;
  $("videos").replaceChildren(...(cards.length ? cards.map(c => el("button", { type: "button",
    className: `vcard${c.slug === slug ? " selected" : ""}`, onclick: () => open(c.slug) }, [
      el("div", { className: "vhead" }, [el("strong", { textContent: c.title }),
        el("span", { className: `turn turn-${c.turn}`, textContent: c.running ? `Working${c.since ? ` · ${since(c.since)}` : ""}` : TURN[c.turn] })]),
      el("div", { className: "ministeps" }, ministeps(c)),
      el("div", { className: "now", textContent: c.now })]))
    : [el("div", { className: "empty", textContent: "No videos yet: start one with New video." })]));
}

async function open(s, toTab, scroll = true) {
  if (slug !== s) { slug = s; run = null; lane = null; shownCheck = ""; shownActions = ""; $("text").value = ""; }
  if (toTab) tab = toTab;
  showTab();
  renderBoard();
  await refreshDetail();
  if (scroll) $("detail").scrollIntoView({ behavior: "smooth", block: "start" });
}

// The open video and tab live in the address (#slug or #slug/activity), so a reload comes back to them.
const remember = () => history.replaceState(null, "", slug ? `#${slug}${tab === "activity" ? "/activity" : ""}` : location.pathname);
const recalled = () => { const m = location.hash.match(/^#([a-z0-9][a-z0-9-]{0,59})(\/activity)?$/); return m ? [m[1], m[2] ? "activity" : "check"] : null; };

function showTab() {
  remember();
  $("tab-check").setAttribute("aria-selected", tab === "check");
  $("tab-activity").setAttribute("aria-selected", tab === "activity");
  $("pane-check").hidden = tab !== "check";
  $("pane-activity").hidden = tab !== "activity";
}
$("tab-check").onclick = () => { tab = "check"; showTab(); };
$("tab-activity").onclick = () => { tab = "activity"; showTab(); pollRun(true); };

// ---------- the selected video ----------

async function refreshDetail() {
  if (!slug) return;
  const v = await fetch(`/api/videos/${slug}`).then(r => (r.ok ? r.json() : null)).catch(() => null);
  if (!v) { $("detail").hidden = true; return; }
  const c = v.summary;
  $("detail").hidden = false;
  $("d-title").textContent = c.title;
  $("d-slug").textContent = v.folder || slug;
  $("d-steps").replaceChildren(...stepper(c));
  $("d-now").replaceChildren(el("span", { className: `dot turn-${c.turn}` }), text(c.running && c.since ? `${c.now} · ${since(c.since)}` : c.now));
  actions(v, c);
  checkPane(v, c);
  if (!run || !v.jobs.some(j => j.id === run)) pickRun(v.jobs.length ? v.jobs[0].id : null);
  runsBar(v.jobs);
  if (tab === "activity") pollRun();
}

let shownActions = "";
function actions(v, c) {
  const key = JSON.stringify([slug, v.status, v.has_scenes, v.downloads, v.finals.length, v.estimate, c.turn, c.running, c.finals]);
  if (key === shownActions) return;  // rebuilding every refresh could swallow a click
  shownActions = key;
  const previewOk = v.status.preview === "approved";
  const button = (label, variant, onclick) => el("button", { type: "button", className: "btn", textContent: label,
    disabled: c.running, onclick, ...(variant ? { dataset: { variant } } : {}) });
  const go = kind => async () => {
    const r = await post(`/api/videos/${slug}/${kind}`, {});
    if (r.error) return alert(r.error);
    run = r.id; lane = null; tab = "activity"; showTab(); refresh();
  };
  $("d-actions").replaceChildren(
    ...(c.turn === "next" && !c.running ? [button("Continue", null, go("continue"))] : []),
    ...(v.has_scenes && ["approved", "none"].includes(v.status.intent)  // no voice or picture before the intent check
        && ["waiting", "changed"].includes(v.status.preview) && !c.running
      ? [button(`${v.status.preview === "changed" ? "Render 720p again" : "Render 720p"} (${v.estimate["720p"]})`, "secondary", go("preview"))] : []),
    ...(previewOk ? [button(`${c.finals ? "Render 1080p again" : "Render 1080p (optional)"} (${v.estimate["1080p"]})`, "secondary", go("final"))] : []),
    ...v.downloads.map(u => { const m = u.match(/-part(\d+)-(landscape|story)-(720p|1080p)/); return el("a", { className: "btn", dataset: { variant: "outline" },
      href: u, title: u.split("/").pop().replace("?download=1", ""),
      textContent: `Download ${m && m[1] ? `part ${m[1]}` : "video"}${u.includes("-story-") ? " (story)" : ""}${u.includes("-1080p") ? " 1080p" : " 720p"}` }); }),
    ...(c.running ? [el("span", { className: "muted", textContent: "Claude is working: follow it in Activity." })] : []));
}

function checkPane(v, c) {
  // The preview is the one check. Before it exists, the plan shows here, and approving it early is optional.
  // Two checks: the intent first, then the preview (which covers the script and the voice).
  const st = v.status;
  const step = ["ready", "changed"].includes(st.intent) ? "intent" : ["ready", "changed"].includes(st.preview) ? "preview"
    : st.preview === "approved" ? null : "plan";
  const can = step === "intent" || step === "preview";
  const withPlan = step === "preview" && st.plan !== "approved";
  const key = JSON.stringify([v.status, v.fingerprints, v.storyboard && v.storyboard.source, v.storyboard_stale,
    v.previews, v.contacts, v.finals, v.audio, v.verdict, v.issues, c.running]);
  if (key !== shownCheck) {  // rebuilding would stop a playing video, so only when something changed
    shownCheck = key;
    const script = el("details", {}, [el("summary", { textContent: "script.yaml" }), el("pre", { textContent: v.script })]);
    const wait = msg => el("div", { className: "waiting" }, [el("p", { textContent: msg })]);
    let body;
    if (step === "intent") {
      body = [el("p", { className: "muted", textContent: "What the video will say, to whom, and how. The script, the voice, and the scenes come after you approve it, and you check them with the 720p video." }),
        el("article", { className: "md" }, markdownView(v.intent || "")),
        el("details", {}, [el("summary", { textContent: "intent.md as text" }), el("pre", { textContent: v.intent || "" })])];
    } else if (step === "plan" && st.intent === "waiting") {
      body = [wait(c.running ? "Claude is reading the sources and writing the intent: the key message, the viewers, the story, and the look."
                             : "No intent yet. Press Continue.")];
    } else if (step === "plan") {
      body = v.storyboard ? [...(v.audio ? [el("audio", { src: v.audio, controls: true })] : []), ...storyboardView(v), script]
        : [wait(c.running ? "Claude is making the plan: research, picks, script, and voice. The storyboard shows here when the voice is ready."
                          : "No plan yet. Press Continue."),
           el("p", { className: "muted", textContent: "The 720p MP4 comes in step 2. You check the plan with it; an early check here is optional." })];
    } else if (step === "preview") {
      body = [...(v.previews.length ? videosView(v.previews, v.contacts, `${v.previews.length} video${v.previews.length > 1 ? "s" : ""} to watch: pick a part, play it, and look at its review frames.`)
        : [wait(c.running ? "Claude is drawing the scenes and rendering the 720p preview. The MP4 shows here when it is done."
                          : "No preview yet. Press Continue.")]),
        ...(withPlan ? [el("h3", { className: "sub", textContent: "The plan: you approve it with this preview" }), ...storyboardView(v), script] : [])];
    } else {
      body = [...videosView(v.finals.length ? v.finals : v.previews, v.finals.length ? [] : v.contacts, ""),
        el("p", { className: "muted", textContent: v.finals.length ? "1080p video ready. Share it with the audience you approved."
          : "Approved: this 720p video is the final. Share it with the audience you approved." }),
        ...(v.verdict && !v.finals.length ? [el("p", {}, [el("strong", { textContent: `1080p: ${v.verdict["1080p"]}. ` }), text(v.verdict.why)])] : [])];
    }
    // issues.md: what slowed Claude down in each step, and an idea to fix it. It is about the tool, not the video.
    const issues = (v.issues || "").replace(/^# .*\n+/, "");
    if (issues.trim()) body.push(el("details", { className: "fold issues" }, [
      el("summary", { textContent: `Issues Claude met, and ideas to fix them (${(issues.match(/^## /gm) || []).length || 1} step${(issues.match(/^## /gm) || []).length === 1 ? "" : "s"})` }),
      el("article", { className: "md" }, markdownView(issues))]));
    $("check-body").replaceChildren(...body);
    $("decide").hidden = !can && c.running;
    $("check-question").hidden = !can;
    $("check-text").textContent = can ? `Check the ${step}${step === "preview" && withPlan ? " and the plan" : ""}: ${v.checklist[step]}` : "";
    // The preview check ends the work, so its buttons say what comes next: keep the 720p, or render 1080p too.
    const preview = step === "preview" && v.previews.length > 0;
    $("approve").hidden = !can;
    $("approve").textContent = preview ? "Approve and download 720p" : `Approve the ${step}${step === "preview" && withPlan ? " and the plan" : ""}`;
    $("approve-hd").hidden = !preview;
    $("approve-hd").textContent = `Approve and render 1080p (${v.estimate["1080p"]})`;
    $("approve-note").hidden = !can;
    $("approve-note").textContent = step === "intent" ? "Claude then writes the script, makes the voice, draws the scenes, and renders 720p."
      : `Approving covers the video${withPlan ? ", the script, and the voice" : ""}. ${v.verdict ? `1080p: ${v.verdict["1080p"]}. ${v.verdict.why}` : "1080p is optional."}`;
    $("check-question").hidden = !can;
    const approve = then => async () => {  // sends the fingerprint shown, so a change after this view is refused
      const r = await post(`/api/videos/${slug}/approve`, { step, expected: v.fingerprints[step] });
      if (r.error) return alert(r.error);
      shownCheck = "";
      if (r.id) { run = r.id; lane = null; }
      if (then === "download") v.previews.forEach(u => { const a = el("a", { href: `${u}?download=1`, download: "" }); document.body.append(a); a.click(); a.remove(); });
      if (then === "1080p") {
        const job = await post(`/api/videos/${slug}/final`, {});
        if (job.error) return alert(job.error);
        run = job.id; lane = null; tab = "activity"; showTab();
      }
      refresh();
    };
    $("approve").onclick = approve(preview ? "download" : null);
    $("approve-hd").onclick = approve("1080p");
  }
  $("reply").hidden = c.running || !can;  // changes go with a check: the intent or the preview
}

$("reply").onsubmit = async e => {
  e.preventDefault();
  const t = $("text").value.trim();
  if (!t) return;
  const r = await post(`/api/videos/${slug}/reply`, { text: t });
  if (r.error) return alert(r.error);
  $("text").value = ""; run = r.id; lane = null; tab = "activity"; showTab(); refresh();
};

// ---------- Activity: each run, each agent, and its log ----------

let run = null, runSince = 0, runEvents = [], lane = null, polling = false;

function pickRun(id) { run = id; runSince = 0; runEvents = []; lane = null; logSeen = 0; openSteps.clear(); $("log").replaceChildren(); }

function runsBar(jobs) {
  $("runs").replaceChildren(...(jobs.length ? jobs.map((j, i) => el("button", { type: "button",
    className: `runchip${j.id === run ? " selected" : ""}`, onclick: () => { pickRun(j.id); runsBar(jobs); pollRun(true); },
    textContent: `${j.label ? `[${j.label}] ` : ""}${j.system ? "Render" : "Claude"} · ${new Date(j.started * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hourCycle: "h23" })} · ${
      !j.done ? `running ${since(j.started)}` : j.code ? `stopped (exit ${j.code})` : `done in ${clock(j.ended - j.started)}`}${i === 0 ? " · latest" : ""}` }))
    : [el("div", { className: "empty", textContent: "No runs for this video yet in this dashboard session." })]));
}

const agentName = (r, id) => id === "main" ? "Main" : (r.agents[id] ? r.agents[id].name : "Sub-agent");

function agentCard(r, id, a) {
  const main = id === "main";
  const steps = main ? runEvents.filter(e => e.agent === "main" && e.kind === "tool").length : a.steps;
  const state = main ? (!r.done ? "running" : r.code ? "stopped" : "done") : (!a.done ? "running" : a.error ? "error" : "done");
  const took = main ? (r.ended || Date.now() / 1000) - r.started : (a.ended || Date.now() / 1000) - a.started;
  const last = lastTime(id), quiet = state === "running" && last && Date.now() / 1000 - last > 120;
  return el("div", { className: `agent agent-${state}${lane === id ? " selected" : ""}` }, [
    el("div", { className: "vhead" }, [el("strong", { textContent: main ? (r.system ? "Render job (make)" : "Main Claude") : a.name }),
      el("span", { className: `turn turn-${state === "running" ? "working" : state === "done" ? "done" : "you"}`,
        textContent: `${state}${!main && a.background ? " in background" : ""} · ${clock(took)}` })]),
    el("div", { className: "muted", textContent: main && r.system ? `${runEvents.length} output lines · ${r.prompt}`
      : `${steps} tool call${steps === 1 ? "" : "s"} · now: ${main ? r.now : a.last}` }),
    ...(last ? [el("div", { className: `muted when${quiet ? " quiet" : ""}`,
      textContent: `last step ${hms(last)}, ${ago(last)}${quiet ? ": no new step for a while (it can be thinking or rendering)" : ""}` })] : []),
    el("div", { className: "buttons" }, [
      el("button", { type: "button", className: "btn", dataset: { variant: "ghost" },
        textContent: lane === id ? "Showing its steps" : "Show its steps", onclick: () => { lane = id; renderLog(r); renderAgents(r); } }),
      ...(!main && (a.task || a.report) ? [el("button", { type: "button", className: "btn", dataset: { variant: "ghost" },
        textContent: a.report ? "Task and report" : "Task", onclick: () => openAgent(id) })] : [])])]);
}

// One modal for a sub-agent's task and report. It updates while it is open, and the arrow keys move to the
// next agent, so you can read each one without opening and closing panels in the cards.
let shownAgent = null, shownAgentKey = "";
const lastTime = id => { for (let i = runEvents.length - 1; i >= 0; i--) if ((runEvents[i].agent || "main") === id && runEvents[i].t) return runEvents[i].t; return 0; };
function openAgent(id) { shownAgent = id; shownAgentKey = ""; fillAgent(lastRun); if (!$("agent-dialog").open) $("agent-dialog").showModal(); }
function fillAgent(r) {
  if (!r || !shownAgent || !r.agents[shownAgent]) return;
  const a = r.agents[shownAgent], key = JSON.stringify([shownAgent, a.done, a.error, a.steps, a.last, (a.report || "").length]);
  if (key === shownAgentKey) return;  // rebuilding would jump the scroll while you read
  shownAgentKey = key;
  const state = !a.done ? "running" : a.error ? "error" : "done";
  $("agent-title").textContent = a.name;
  $("agent-state").className = `turn turn-${state === "running" ? "working" : state === "done" ? "done" : "you"}`;
  $("agent-state").textContent = `${state} · ${clock((a.ended || Date.now() / 1000) - a.started)}`;
  const last = lastTime(shownAgent);
  $("agent-meta").textContent = `Started ${hms(a.started)}${a.ended ? `, ended ${hms(a.ended)}` : ""} · ${a.steps} tool call${a.steps === 1 ? "" : "s"}`
    + (last ? ` · last step ${hms(last)}` : "") + (a.last ? ` · now: ${a.last}` : "");
  $("agent-body").replaceChildren(
    ...(a.report ? [el("h3", { textContent: "Its report" }), el("article", { className: "md" }, markdownView(a.report))] : []),
    ...(a.task ? [el("details", { open: !a.report }, [el("summary", { textContent: "Task it was given" }),
      el("article", { className: "md" }, markdownView(a.task))])] : []));
}
function stepAgent(dir) {
  const ids = Object.keys((lastRun && lastRun.agents) || {}).filter(k => lastRun.agents[k].task || lastRun.agents[k].report);
  const i = ids.indexOf(shownAgent);
  if (ids.length) openAgent(ids[(i + dir + ids.length) % ids.length]);
}
$("agent-close").onclick = () => $("agent-dialog").close();
$("agent-prev").onclick = () => stepAgent(-1);
$("agent-next").onclick = () => stepAgent(1);
$("agent-steps").onclick = () => { lane = shownAgent; $("agent-dialog").close(); pollRun(true); };
$("agent-dialog").onclick = e => { if (e.target === $("agent-dialog")) $("agent-dialog").close(); };  // a click outside
$("agent-dialog").onkeydown = e => {
  if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); stepAgent(e.key === "ArrowLeft" ? -1 : 1); }
};

function renderAgents(r) {
  lastRun = r;
  if ($("agent-dialog").open) fillAgent(r);
  const subs = Object.entries(r.agents || {});
  $("agents").replaceChildren(agentCard(r, "main", null), ...subs.map(([id, a]) => agentCard(r, id, a)));
  $("log-filter-label").textContent = lane ? `Steps of: ${agentName(r, lane)}` : `All agents (${subs.length} sub-agent${subs.length === 1 ? "" : "s"})`;
  $("log-all").hidden = !lane;
}
$("log-all").onclick = () => { lane = null; pollRun(true); };

// The log as steps: each thing Claude says opens a step, and the actions after it fold under one summary line
// ("4 actions"). Problems (a refused tool, a failed helper, an error) stay open and red. Filters: everything, what
// Claude says, or problems. While you read higher up, the log stays still, and a button counts the new lines.
const PROBLEM = /^(Not allowed|Denied|Failed|Sub-agent failed|Sub-agent stopped|The dashboard could not read)/;
const isProblem = e => PROBLEM.test(e.text) || (e.kind === "result" && /^(error|Failed)/i.test(e.text));
// The same tidy step as the server's, for lines it saved before: short paths, "Run" for a command, and a long
// command cut to its first line.
const escapeRe = t => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
function tidy(e) {
  if (e.kind !== "tool") return e.text;
  let t = ROOT_DIR ? e.text.replace(new RegExp(escapeRe(ROOT_DIR + "/"), "g"), "") : e.text;
  t = t.replace(/(?:projects|generated_videos)\/[a-z0-9][a-z0-9-]*\//g, "").replace(/^\$ /, "Run ").replace(/^cd \S+ && /, "");
  t = t.replace(/^Run cd \S+ && /, "Run ");
  const lines = t.split("\n");
  return lines.length > 1 ? `${lines[0].trim()} (+${lines.length - 1} lines)` : t;
}
const openSteps = new Set();
let logMode = "all", logSeen = 0;
document.querySelectorAll('input[name="log-mode"]').forEach(x => { x.onchange = () => { logMode = x.value; renderLog(lastRun); }; });
$("log-new").onclick = () => { $("log").scrollTop = $("log").scrollHeight; $("log-new").hidden = true; logSeen = runEvents.length; };
$("log").onscroll = () => { if (atBottom()) { $("log-new").hidden = true; logSeen = runEvents.length; } };
const atBottom = () => $("log").scrollTop + $("log").clientHeight >= $("log").scrollHeight - 30;
let lastRun = null;

function renderLog(r) {
  lastRun = r;
  if (!r) return;
  const box = $("log"), follow = atBottom();
  const shown = runEvents.map((e, i) => ({ ...e, i })).filter(e => !lane || e.agent === lane)
    .filter(e => logMode === "all" || (logMode === "said" ? e.kind !== "tool" : isProblem(e))).slice(-600);
  const steps = [];
  for (const e of shown) {
    const last = steps[steps.length - 1];
    if (e.kind === "tool" && !isProblem(e) && last && last.head.agent === e.agent && !isProblem(last.head)) last.actions.push(e);
    else steps.push({ head: e, actions: [] });
  }
  const line = (e, cls) => el("div", { className: `${cls} log-${e.kind}${isProblem(e) ? " problem" : ""}` }, [
    el("span", { className: "time", textContent: e.t ? hms(e.t) : "" }),
    el("span", { className: "who", textContent: agentName(r, e.agent || "main") }),
    ...(isProblem(e) ? [el("span", { className: "mark", textContent: "✕ " })] : []),
    el("span", { textContent: tidy(e), title: e.kind === "tool" && tidy(e) !== e.text ? e.text : "" })]);
  box.replaceChildren(...(steps.length ? steps.map(s => {
    if (!s.actions.length) return line(s.head, "step");
    const fold = el("details", { className: "actions", open: openSteps.has(s.head.i) }, [
      el("summary", { textContent: `${s.actions.length} action${s.actions.length === 1 ? "" : "s"}${
        s.actions[s.actions.length - 1].t ? `, last at ${hms(s.actions[s.actions.length - 1].t)}` : ""}: ${tidy(s.actions[s.actions.length - 1])}` }),
      ...s.actions.map(a => line(a, "action"))]);
    fold.ontoggle = () => (fold.open ? openSteps.add(s.head.i) : openSteps.delete(s.head.i));
    return el("div", { className: "stepgroup" }, [line(s.head, "step"), fold]);
  }) : [el("div", { className: "empty", textContent: logMode === "problems" ? "No problems." : "Nothing yet." })]));
  if (follow) { box.scrollTop = box.scrollHeight; logSeen = runEvents.length; $("log-new").hidden = true; }
  else if (runEvents.length > logSeen) {
    $("log-new").hidden = false;
    $("log-new").textContent = `${runEvents.length - logSeen} new line${runEvents.length - logSeen === 1 ? "" : "s"}: jump to the end`;
  }
}

async function pollRun(force) {
  if (!run) { $("agents").replaceChildren(); $("log").replaceChildren(el("div", { className: "empty", textContent: "No runs yet." })); return; }
  if (polling && !force) return;
  polling = true;
  try {
    const id = run, r = await fetch(`/api/jobs/${id}?since=${runSince}`).then(x => x.json());
    if (id !== run) return;
    runEvents.push(...r.events);
    runSince += r.events.length;
    renderAgents(r);
    renderLog(r);
    const sid = typeof r.session === "string" && /^[0-9a-f-]{20,64}$/.test(r.session) ? r.session : null;
    $("session").hidden = !sid || r.system;
    if (sid) $("session").replaceChildren(text(r.done ? "Open this run in Claude Code: " : "When this run ends, open it in Claude Code: "),
      el("code", { textContent: `claude --resume ${sid}` }),
      el("button", { type: "button", className: "btn", dataset: { variant: "ghost" }, textContent: "Copy",
        onclick: () => navigator.clipboard.writeText(`claude --resume ${sid}`) }));
  } catch { /* the next refresh tries again */ } finally { polling = false; }
}

// ---------- System panel: Docker, the image, doctor, and the Claude Code login ----------

const ACTIONS = { start: "Start Docker", stop: "Stop Docker", build: "Build image", doctor: "Run doctor" };
const badge = (t, variant) => el("span", { className: "badge", textContent: t, ...(variant ? { dataset: { variant } } : {}) });

let ROOT_DIR = "";
async function refreshSystem() {
  let s;
  try {
    s = await fetch("/api/system").then(r => r.json());
    ROOT_DIR = typeof s.root === "string" ? s.root : "";
    // Model aliases and effort levels, as this Claude Code lists them (an alias always means the latest version).
    for (const [id, list] of [["model", s.claude_models], ["effort", s.claude_efforts]])
      if (Array.isArray(list) && $(id).options.length === 1)
        $(id).append(...list.filter(x => /^[a-z0-9][a-z0-9.\[\]-]*$/.test(x)).map(x => el("option", { value: x, textContent: x })));
  } catch {
    $("system-status").textContent = "Could not reach the dashboard server: is make dashboard still running?";
    $("system-line").textContent = "Dashboard server not reachable";
    return;
  }
  const doctor = s.doctor ? (s.doctor.fail.length ? `${s.doctor.fail.length} FAIL: ${s.doctor.fail.join(", ")}` : `${s.doctor.ok} ok at ${s.doctor.at}`) : "not run yet";
  const dockerText = { running: "running", stopped: "stopped", missing: "not installed", "not responding": "not responding" }[s.docker];
  const ready = s.docker === "running" && s.image === "built" && s.claude === "logged in";
  $("system-status").textContent = ready ? "Ready." : "Set up below.";
  $("system-line").textContent = ready ? "Docker running · image built · Claude Code logged in" : "Set up the System card first";
  $("system-rows").replaceChildren(
    el("dt", { textContent: "Docker" }), el("dd", {}, [badge(dockerText, s.docker === "running" ? null : "destructive"),
      ...(s.docker === "missing" ? [el("span", { className: "muted", textContent: "  Install Colima or Docker Desktop (README, Quick start)." })] : [])]),
    el("dt", { textContent: "Image" }), el("dd", {}, [badge(s.image === "built" ? "built" : s.image === "missing" ? "not built" : "unknown", s.image === "built" ? null : "secondary")]),
    el("dt", { textContent: "Doctor" }), el("dd", {}, [badge(doctor, s.doctor && s.doctor.fail.length ? "destructive" : "secondary")]),
    el("dt", { textContent: "Claude Code" }), el("dd", {}, [badge(s.claude === "logged in" && s.claude_plan ? `logged in (${s.claude_plan} plan)` : s.claude,
      s.claude === "logged in" ? null : "destructive"),
      ...(s.claude !== "logged in" ? [el("span", { className: "muted", textContent: {
        expired: "  Your login expired: run claude in a terminal, then /login.",
        "no plan": "  This login has no Claude plan: jobs need Pro, Max, Team, or Enterprise, or an API key.",
        missing: "  Install Claude Code: jobs run on it." }[s.claude] || "  Log in once: run claude in a terminal." })] : [])]));
  const show = { start: s.docker !== "running" && s.docker !== "missing", stop: s.docker === "running" && s.runtime === "colima",
                 build: s.docker === "running", doctor: s.docker === "running" && s.image === "built" };
  $("system-buttons").replaceChildren(...Object.keys(ACTIONS).filter(a => show[a]).map(a => el("button", {
    type: "button", className: "btn", textContent: a === "build" && s.image === "built" ? "Rebuild image" : ACTIONS[a],
    disabled: s.busy, dataset: a === "stop" ? { variant: "outline" } : a === "start" || (a === "build" && s.image !== "built") ? {} : { variant: "secondary" },
    onclick: async () => { const r = await post(`/api/system/${a}`, {}); if (r.error) return alert(r.error); refresh(); } })));
  $("three").disabled = s.three === false;  // make doctor found no working WebGL
  if (s.three === false) $("three").checked = false;
  const reason = s.docker !== "running" ? "Start Docker first." : s.image !== "built" ? "Build the image first."
    : s.claude !== "logged in" ? `Claude Code is ${s.claude}: Start runs a Claude job, so fix it in the System card first.` : "";
  $("start").disabled = Boolean(reason);
  $("start-reason").hidden = !reason;
  $("start-reason").textContent = reason;
}

async function refresh() {
  let s;
  try {
    s = await fetch("/api/state").then(r => r.json());
  } catch {
    return;
  }
  const restarted = s.boot && s.boot !== BOOT;
  $("stale").hidden = !s.stale && !restarted;
  $("stale-text").textContent = restarted ? "The dashboard restarted after this page loaded. Reload the page (Cmd+R)."
    : s.videos.some(v => v.running)
    ? "The dashboard's code changed after it started. When the running jobs finish, stop it (Ctrl+C in its terminal) and run make dashboard again: a restart stops running jobs."
    : "The dashboard's code changed after it started. Stop it (Ctrl+C in its terminal), run make dashboard again, then reload this page.";
  cards = s.videos;
  renderBoard();
  const sys = s.system[0];
  $("system-job").hidden = !sys;
  if (sys) $("system-job").textContent = `${sys.done ? (sys.code ? "Failed" : "Done") : "Running"}: ${sys.prompt}. ${sys.last}`;
  await refreshDetail();
}

// ---------- New video: a dialog with sources, what you want, and look and sound ----------

const KINDS = { topic: "Topic", html: "HTML page", pr: "PR", folder: "Repo or folder", file: "File", recording: "Recording", link: "Web link" };
const ROLES = { main: "Main story", context: "Context", facts: "Facts and numbers", look: "Look reference" };
const HINTS = { topic: "how DNS works", html: "~/reports/q3-review.html", pr: "https://github.com/org/repo/pull/482",
  folder: "~/code/checkout-service", file: "~/notes/design.md", recording: "~/Movies/sync-1118.mp4", link: "https://example.com/article" };
const MEDIA = /\.(mp3|m4a|wav|aac|ogg|flac|mp4|mov|mkv|webm)$/i;
// What a value looks like: a PR link or #123, a web link, an .html page, a recording, another file, a folder, else a topic.
function detectKind(v) {
  const t = v.trim().replace(/^file:\/\//i, "");  // a browser's file:// link is a path
  if (/^https:\/\/github\.com\/[^/\s]+\/[^/\s]+\/pull\/\d+/.test(t) || /^([\w.-]+\/[\w.-]+)?#\d+$/.test(t)) return "pr";
  if (/^https?:\/\//i.test(t)) return "link";
  if (/^(~|\/|\.{1,2}\/)/.test(t) || /^[^\s/]+\/\S/.test(t)) {
    if (/\.html?$/i.test(t)) return "html";
    if (MEDIA.test(t)) return "recording";
    return /\.[a-z0-9]{1,5}$/i.test(t) ? "file" : "folder";
  }
  return "topic";
}
const htmlPage = t => (detectKind(t) === "html" ? t.trim() : null);
const slugify = t => t.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim().split(" ").slice(0, 5).join("-").slice(0, 60);
const options = (map, value) => Object.entries(map).map(([k, label]) => el("option", { value: k, textContent: label, selected: k === value }));
let webEdited = false;

function sourceRow(kind = "topic", role = "main") {
  const row = el("div", { className: "srcrow", role: "group" });
  const kindSel = el("select", { className: "select" }, options(KINDS, kind));
  const value = el("input", { className: "input value", placeholder: HINTS[kind], maxLength: 500 });
  const roleSel = el("select", { className: "select" }, options(ROLES, role));
  const remove = el("button", { type: "button", className: "btn", dataset: { variant: "ghost" }, textContent: "Remove" });
  kindSel.onchange = () => { row.dataset.kindSet = "1"; value.placeholder = HINTS[kindSel.value]; sourcesChanged(); };
  value.oninput = () => { if (!row.dataset.kindSet) { kindSel.value = detectKind(value.value); value.placeholder = HINTS[kindSel.value]; } sourcesChanged(); };
  remove.onclick = () => {
    const rows = [...$("sources").children];
    if (rows.length === 1) { value.value = ""; delete row.dataset.kindSet; kindSel.value = "topic"; sourcesChanged(); return; }
    const i = rows.indexOf(row);
    row.remove();
    const before = $("sources").children[Math.max(0, i - 1)];  // focus goes to the row above
    if (before) before.querySelector("input").focus();
    sourcesChanged(`Removed source ${i + 1}.`);
  };
  row.append(kindSel, value, roleSel, remove);
  return row;
}
function sourcesChanged(note = "") {
  [...$("sources").children].forEach((row, i) => {
    const [kind, value, role, remove] = row.children;
    row.setAttribute("aria-label", `Source ${i + 1}`);
    kind.setAttribute("aria-label", `Source ${i + 1}: kind`);
    value.setAttribute("aria-label", `Source ${i + 1}: ${KINDS[kind.value]}`);
    role.setAttribute("aria-label", `Source ${i + 1}: role`);
    remove.setAttribute("aria-label", `Remove source ${i + 1}`);
  });
  const list = sources();
  if (!webEdited) $("web").checked = !list.some(x => x.kind === "html");  // a page is its own source; a topic needs research
  $("sources-note").textContent = note || (list.filter(x => x.kind === "html").length > 1 ? "One HTML page per video: keep one." : "");
}
const sources = () => [...$("sources").children].map(row => {
  const [kind, value, role] = row.children;
  return { kind: kind.value, value: value.value.trim(), role: role.value };
}).filter(x => x.value);
$("add-source").onclick = () => {
  const row = sourceRow("topic", "context");
  $("sources").append(row);
  sourcesChanged(`Added source ${$("sources").children.length}.`);
  row.children[1].focus();
};
$("web").onchange = () => { webEdited = true; };
$("name-mode").onchange = () => {
  const manual = $("name-mode").value === "manual";
  $("slug").hidden = !manual;
  $("slug").required = manual;
  if (manual && !$("slug").value) { const first = sources()[0]; $("slug").value = first ? slugify(first.value.split("/").pop().replace(/\.html?$/i, "")) : ""; }
};

$("brief").oninput = () => { $("brief-count").textContent = $("brief").value.length; };
const radio = name => (document.querySelector(`input[name="${name}"]:checked`) || {}).value;
const card = (name, value, title, text, img, checked) => el("label", {}, [
  el("input", { type: "radio", name, value, checked }),
  el("span", { className: "cardbody" }, [...(img ? [el("img", { src: img, alt: "" })] : []), el("strong", { textContent: title }),
    el("span", { className: "muted", textContent: text })])]);

// Structure and look as cards, "Let Claude pick" first; each structure shows its acts, each look its swatch.
async function loadCatalogs() {
  const c = await fetch("/api/catalog").then(r => r.json()).catch(() => ({ moodboards: [], video_formats: [] }));
  $("vformat").replaceChildren(card("vformat", "recommend", "Let Claude pick", "from the sources and the intent", null, true),
    ...c.video_formats.filter(x => ID.test(x.name)).map(x => card("vformat", x.name, x.name, (x.acts || []).join(" > "))));
  $("mood").replaceChildren(card("mood", "recommend", "Let Claude pick", "a look that fits the topic", null, true),
    ...c.moodboards.filter(x => ID.test(x.name)).map(x => card("mood", x.name, x.name, (x.fits || []).slice(0, 2).join(", "), `/swatch/${x.name}.jpg`)));
}

// Voices: a radio per voice and a play button with its sample (voices/<voice>.m4a); nothing plays on its own.
const VOICES = { af_heart: "US, female", am_michael: "US, male", bf_emma: "UK, female", bm_george: "UK, male" };
const sample = new Audio();
$("voice").replaceChildren(...Object.entries(VOICES).map(([v, label], i) => el("div", { className: "voicerow" }, [
  el("label", {}, [el("input", { type: "radio", name: "voice", value: v, checked: i === 0 }), text(label)]),
  el("button", { type: "button", className: "btn", dataset: { variant: "ghost" }, textContent: "Play",
    ariaLabel: `Play voice: ${label}`, onclick: () => { sample.src = `/voice/${v}.m4a`; sample.play().catch(() => {}); } })])));

function resetNew() {
  $("sources").replaceChildren(sourceRow("topic", "main"));
  $("brief").value = ""; $("brief-count").textContent = "0"; $("slug").value = ""; $("name-mode").value = "auto"; $("slug").hidden = true;
  $("web").checked = true; webEdited = false; $("claude-cmd").hidden = true;
  sourcesChanged();
}
$("new-open").onclick = () => { if (!$("sources").children.length) resetNew(); $("new-dialog").showModal(); $("sources").querySelector("select").focus(); };
const closeNew = () => { $("new-dialog").close(); $("new-open").focus(); };
$("new-close").onclick = closeNew;
$("new-cancel").onclick = closeNew;

// The request, from the dialog. A dashboard job gets the sources from the server, which copies pages, files, and
// recordings into the project first; Claude Code (forTerminal) gets each source as typed, and the skill copies it.
function request(forTerminal) {
  const vf = radio("vformat"), mood = radio("mood"), list = sources();
  const brief = $("brief").value.trim();
  const listed = forTerminal ? " Sources (kind, role): " + list.map((x, i) => `${i + 1}. ${KINDS[x.kind]}, ${ROLES[x.role]}: ${x.value}`).join("; ") + "." : "";
  return `Use the explainer-video skill.${listed} Format: ${radio("format")}. ` +
    (vf !== "recommend" ? `Video format: ${vf}. ` : "") + (mood !== "recommend" ? `Moodboard: ${mood}. ` : "") +
    `3D: ${$("three").checked ? "allowed (three: true)" : "off (three: false)"}. ` +
    `Voice: ${radio("voice")}. Length: ${radio("length")}, one video, no parts. ` +
    (forTerminal && brief ? `The requester's brief (who watches, why, what to cover), in their words: <<<${brief}>>> ` : "") +
    (forTerminal ? ($("name-mode").value === "manual" && $("slug").value.trim() ? `Name: ${$("slug").value.trim()}. ` : "") +
      ($("web").checked ? "Web research: on. " : "Web research: off: use only the sources, and write no research.md. ") : "") +
    "Use defaults for anything else.";
}

// One word for the shell: single quotes, with each ' inside written as '\''.
const shq = t => `'${String(t).replace(/'/g, "'\\''")}'`;

$("to-claude").onclick = async () => {
  const list = sources();
  if (!list.length) return alert("Add a source first.");
  const dirs = list.filter(x => x.kind === "folder").map(x => x.value);
  const picks = ["model", "effort"].filter(id => $(id).value).map(id => `--${id} ${shq($(id).value)} `).join("");
  const cmd = `cd ${shq(ROOT_DIR || ".")} && claude ${picks}${dirs.map(d => `--add-dir ${shq(d)} `).join("")}` +
    `${$("web").checked ? "" : "--disallowedTools WebSearch WebFetch "}${shq(request(true))}`;
  $("claude-cmd-text").textContent = cmd;
  $("claude-cmd").hidden = false;
  try { await navigator.clipboard.writeText(cmd); } catch { $("claude-cmd").querySelector("p").textContent = "Copy this and paste it in a terminal:"; }
};

$("new").onsubmit = async e => {
  e.preventDefault();
  const list = sources();
  if (!list.length) { $("sources-note").textContent = "Add a source first."; return $("sources").querySelector("input").focus(); }
  const auto = $("name-mode").value === "auto";
  $("start").disabled = true;
  $("start").textContent = auto ? "Naming the project" : "Starting";
  const r = await post("/api/jobs", { prompt: request(false), sources: list, slug: auto ? "" : $("slug").value.trim(),
    auto_name: auto, web: $("web").checked, brief: $("brief").value.trim(), model: $("model").value, effort: $("effort").value })
    .finally(() => { $("start").textContent = "Start video"; refreshSystem(); });
  if (r.error) { $("sources-note").textContent = r.error; return alert(r.error); }  // the dialog stays open
  closeNew();
  resetNew();
  await refresh();
  open(r.slug, "activity");
};

// Samples: a finished video to copy. Start runs make new and make narrate; no Claude job is needed.
async function loadSamples() {
  const r = await fetch("/api/samples").then(x => x.json()).catch(() => ({ samples: [] }));
  $("samples").replaceChildren(...(r.samples.length ? r.samples.map(s => {
    const slugBox = el("input", { className: "input", value: `${s.name}-copy`, maxLength: 60 });
    return el("div", { className: "sample" }, [
      ...(s.frame ? [el("img", { src: s.frame, alt: "", className: "thumb" })] : []),
      el("div", { className: "stack" }, [
        el("strong", { textContent: s.title }),
        el("div", { className: "muted", textContent: `${s.video_format || "any format"} · ${s.moodboard} · ${s.format}${s.three ? " · 3D" : ""}` }),
        slugBox,
        el("button", { type: "button", className: "btn", dataset: { variant: "secondary" }, textContent: "Start from this sample",
          onclick: async () => { const x = await post(`/api/samples/${s.name}/use`, { slug: slugBox.value.trim() });
            if (x.error) return alert(x.error); await refresh(); open(x.slug || slugBox.value.trim(), "activity"); } })])]);
  }) : [el("div", { className: "empty", textContent: "No samples in videos/samples/ yet." })]));
}

loadCatalogs();
loadSamples();
refreshSystem();
refresh().then(() => { const r = recalled(); if (r && cards.some(c => c.slug === r[0])) open(r[0], r[1], false); });
setInterval(refresh, 3000);
setInterval(refreshSystem, 15000);

// Follow the system light or dark setting: Basecoat switches its tokens on the .dark class.
const dark = matchMedia("(prefers-color-scheme: dark)");
const setTheme = () => document.documentElement.classList.toggle("dark", dark.matches);
setTheme(); dark.addEventListener("change", setTheme);
