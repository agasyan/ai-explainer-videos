// The dashboard's page logic. Agent-written text reaches the page only through textContent (see el).
const TOKEN = document.querySelector('meta[name="ev-token"]').content;
const $ = id => document.getElementById(id);
const el = (tag, { dataset = {}, ...props } = {}, kids = []) => {
  const e = Object.assign(document.createElement(tag), props);
  Object.assign(e.dataset, dataset);
  e.append(...kids);
  return e;
};
const post = (url, body) => fetch(url, { method: "POST", body: JSON.stringify(body),
  headers: { "Content-Type": "application/json", "X-EV-Token": TOKEN } }).then(r => r.json());
const clock = s => { const t = Math.max(0, Math.round(s)); return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`; };
const since = t => clock(Date.now() / 1000 - t);

// A video with its subtitle track (switch it on in the player) and a transcript: click a line to jump there.
function player(src) {
  const vtt = src.replace(/\.mp4$/, ".vtt");
  const video = el("video", { src, controls: true, preload: "metadata" },
    [el("track", { kind: "captions", srclang: "en", label: "English", src: vtt })]);
  const list = el("div", { className: "transcript" });
  fetch(vtt).then(r => (r.ok ? r.text() : "")).then(text => {
    const cues = [...text.matchAll(/(\d+):(\d+):([\d.]+) --> \S+\n(.+)/g)]
      .map(m => ({ t: +m[1] * 3600 + +m[2] * 60 + +m[3], text: m[4] }));
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

// Agent-written data (storyboard, picks, research) becomes text nodes only; a link renders only for http(s).
const text = value => document.createTextNode(String(value ?? ""));
const link = (label, href) => /^https?:\/\//.test(href)
  ? el("a", { href, textContent: label, target: "_blank", rel: "noopener noreferrer" }) : text(label);
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
  const plan = st.plan === "approved" ? ["done", "approved"]
    : ["ready", "changed"].includes(st.plan) ? ["done", "ready: you check it with the preview"]
    : work ? ["working", "Claude is working"] : ["next", "not ready"];
  const preview = st.preview === "approved" ? ["done", "approved: the final video"]
    : ["ready", "changed"].includes(st.preview) ? ["you", st.preview === "changed" ? "changed: check again" : "your check"]
    : work ? ["working", "Claude is working"] : ["next", "next"];
  const [ready, total] = c.parts || [0, 0];
  const hd = c.finals ? ["done", "ready to download"] : st.preview === "approved"
    ? (work ? ["working", `rendering: ${ready} of ${total} parts ready`] : ["next", "optional: see the verdict"])
    : ["locked", "optional, after the preview"];
  return [["1 Plan", "research, script, voice", ...plan], ["2 Preview", "scenes, the 720p video", ...preview],
          ["3 1080p", "optional", ...hd]];
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
    ...(v.has_scenes && ["waiting", "changed"].includes(v.status.preview) && !c.running
      ? [button(`${v.status.preview === "changed" ? "Render 720p again" : "Render 720p"} (${v.estimate["720p"]})`, "secondary", go("preview"))] : []),
    ...(previewOk ? [button(`${c.finals ? "Render 1080p again" : "Render 1080p (optional)"} (${v.estimate["1080p"]})`, "secondary", go("final"))] : []),
    ...v.downloads.map(u => { const m = u.match(/-part(\d+)-(landscape|story)-(720p|1080p)/); return el("a", { className: "btn", dataset: { variant: "outline" },
      href: u, title: u.split("/").pop().replace("?download=1", ""),
      textContent: `Download ${m && m[1] ? `part ${m[1]}` : "video"}${u.includes("-story-") ? " (story)" : ""}${u.includes("-1080p") ? " 1080p" : " 720p"}` }); }),
    ...(c.running ? [el("span", { className: "muted", textContent: "Claude is working: follow it in Activity." })] : []));
}

function checkPane(v, c) {
  // The preview is the one check. Before it exists, the plan shows here, and approving it early is optional.
  const st = v.status, waitingPreview = !["ready", "changed", "approved"].includes(st.preview);
  const step = ["ready", "changed"].includes(st.preview) ? "preview" : st.preview === "approved" ? null : "plan";
  const can = Boolean(step) && ["ready", "changed"].includes(st[step]) && (step === "preview" || waitingPreview);
  const withPlan = step === "preview" && st.plan !== "approved";
  const key = JSON.stringify([v.status, v.fingerprints, v.storyboard && v.storyboard.source, v.storyboard_stale,
    v.previews, v.contacts, v.finals, v.audio, v.verdict, c.running]);
  if (key !== shownCheck) {  // rebuilding would stop a playing video, so only when something changed
    shownCheck = key;
    const script = el("details", {}, [el("summary", { textContent: "script.yaml" }), el("pre", { textContent: v.script })]);
    const wait = msg => el("div", { className: "waiting" }, [el("p", { textContent: msg })]);
    let body;
    if (step === "plan") {
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
    $("check-body").replaceChildren(...body);
    $("decide").hidden = !can && c.running;
    $("check-question").hidden = !can;
    $("check-text").textContent = can ? `Check the ${step}${step === "preview" && withPlan ? " and the plan" : ""}: ${v.checklist[step]}` : "";
    $("approve").hidden = !can;
    $("approve").textContent = `Approve the ${step}${step === "preview" && withPlan ? " and the plan" : ""}`;
    $("approve-note").hidden = !can;
    $("approve-note").textContent = step === "plan" ? "Optional: Claude writes the scenes and renders the 720p preview either way."
      : "This 720p video is the final. 1080p is optional after it.";
    $("check-question").hidden = !can;
    $("approve").onclick = async () => {  // sends the fingerprint shown, so a change after this view is refused
      const r = await post(`/api/videos/${slug}/approve`, { step, expected: v.fingerprints[step] });
      if (r.error) return alert(r.error);
      shownCheck = "";
      if (r.id) { run = r.id; lane = null; }
      refresh();
    };
  }
  $("reply").hidden = c.running || !v.script;
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
const opened = new Set();  // task and report panels you opened stay open across refreshes

function pickRun(id) { run = id; runSince = 0; runEvents = []; lane = null; $("log").replaceChildren(); }

function runsBar(jobs) {
  $("runs").replaceChildren(...(jobs.length ? jobs.map((j, i) => el("button", { type: "button",
    className: `runchip${j.id === run ? " selected" : ""}`, onclick: () => { pickRun(j.id); runsBar(jobs); pollRun(true); },
    textContent: `${j.system ? "Render" : "Claude"} · ${new Date(j.started * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hourCycle: "h23" })} · ${
      !j.done ? `running ${since(j.started)}` : j.code ? `stopped (exit ${j.code})` : `done in ${clock(j.ended - j.started)}`}${i === 0 ? " · latest" : ""}` }))
    : [el("div", { className: "empty", textContent: "No runs for this video yet in this dashboard session." })]));
}

const agentName = (r, id) => id === "main" ? "Main" : (r.agents[id] ? r.agents[id].name : "Sub-agent");

function agentCard(r, id, a) {
  const main = id === "main";
  const steps = main ? runEvents.filter(e => e.agent === "main" && e.kind === "tool").length : a.steps;
  const state = main ? (!r.done ? "running" : r.code ? "stopped" : "done") : (!a.done ? "running" : a.error ? "error" : "done");
  const took = main ? (r.ended || Date.now() / 1000) - r.started : (a.ended || Date.now() / 1000) - a.started;
  const panel = (key, label, body) => {
    const d = el("details", { open: opened.has(`${id}:${key}`) }, [el("summary", { textContent: label }), el("pre", { textContent: body })]);
    d.ontoggle = () => (d.open ? opened.add(`${id}:${key}`) : opened.delete(`${id}:${key}`));
    return d;
  };
  return el("div", { className: `agent agent-${state}${lane === id ? " selected" : ""}` }, [
    el("div", { className: "vhead" }, [el("strong", { textContent: main ? (r.system ? "Render job (make)" : "Main Claude") : a.name }),
      el("span", { className: `turn turn-${state === "running" ? "working" : state === "done" ? "done" : "you"}`,
        textContent: `${state}${!main && a.background ? " in background" : ""} · ${clock(took)}` })]),
    el("div", { className: "muted", textContent: main && r.system ? `${runEvents.length} output lines · ${r.prompt}`
      : `${steps} tool call${steps === 1 ? "" : "s"} · now: ${main ? r.now : a.last}` }),
    el("div", { className: "buttons" }, [el("button", { type: "button", className: "btn", dataset: { variant: "ghost" },
      textContent: lane === id ? "Showing its steps" : "Show its steps", onclick: () => { lane = id; renderLog(r); renderAgents(r); } })]),
    ...(!main && a.task ? [panel("task", "Task it was given", a.task)] : []),
    ...(!main && a.report ? [panel("report", "Its report", a.report)] : [])]);
}

function renderAgents(r) {
  const subs = Object.entries(r.agents || {});
  $("agents").replaceChildren(agentCard(r, "main", null), ...subs.map(([id, a]) => agentCard(r, id, a)));
  $("log-filter-label").textContent = lane ? `Steps of: ${agentName(r, lane)}` : `All agents (${subs.length} sub-agent${subs.length === 1 ? "" : "s"})`;
  $("log-all").hidden = !lane;
}
$("log-all").onclick = () => { lane = null; pollRun(true); };

function renderLog(r) {
  const box = $("log"), atEnd = box.scrollTop + box.clientHeight >= box.scrollHeight - 30;
  const lines = runEvents.filter(e => !lane || e.agent === lane).slice(-500);
  box.replaceChildren(...(lines.length ? lines.map(e => el("div", { className: `log-${e.kind}` }, [
    el("span", { className: "who", textContent: agentName(r, e.agent || "main") }), text(e.text)]))
    : [el("div", { className: "empty", textContent: "Nothing yet." })]));
  if (atEnd) box.scrollTop = box.scrollHeight;
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
  $("stale").hidden = !s.stale;
  $("stale-text").textContent = s.videos.some(v => v.running)
    ? "The dashboard's code changed after it started. When the running jobs finish, stop it (Ctrl+C in its terminal) and run make dashboard again: a restart stops running jobs."
    : "The dashboard's code changed after it started. Stop it (Ctrl+C in its terminal), run make dashboard again, then reload this page.";
  cards = s.videos;
  renderBoard();
  const sys = s.system[0];
  $("system-job").hidden = !sys;
  if (sys) $("system-job").textContent = `${sys.done ? (sys.code ? "Failed" : "Done") : "Running"}: ${sys.prompt}. ${sys.last}`;
  await refreshDetail();
}

// ---------- New video and samples ----------

// The slug follows the topic until you edit it: "How DNS works" -> how-dns-works.
const slugify = t => t.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim().split(" ").slice(0, 5).join("-").slice(0, 60);
// A source that is one path to an .html or .htm file makes a video from that page (make from-html):
// it starts with ~, /, ./, ../, or a folder name and a slash, so "explain index.html" stays a topic.
const htmlPage = t => (/^(~|\/|\.{1,2}\/|[^\s\/]+\/)[^\n]*\.html?$/i.test(t.trim()) ? t.trim() : null);
const pageSlug = p => p.split("/").pop().replace(/\.html?$/i, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60);
let slugEdited = false, webEdited = false;
$("slug").oninput = () => { slugEdited = $("slug").value.trim() !== ""; };
$("web").onchange = () => { webEdited = true; };
// Auto: the server asks Claude for a name when you press Start. Manual: you type it (it follows the source until you edit it).
$("name-mode").onchange = () => {
  const manual = $("name-mode").value === "manual";
  $("slug").hidden = !manual;
  $("slug").required = manual;
};
$("source").oninput = () => {
  const page = htmlPage($("source").value);
  if (!slugEdited) $("slug").value = page ? pageSlug(page) : slugify($("source").value);
  if (!webEdited) $("web").checked = !page;  // a page is its own source; a topic needs research
  $("html-note").hidden = !page;
};

// Catalogs for the New video form: "Recommend for me" by default, or one entry, with its swatch.
async function loadCatalogs() {
  const c = await fetch("/api/catalog").then(r => r.json()).catch(() => ({ moodboards: [], video_formats: [] }));
  const fill = (id, items) => $(id).replaceChildren(el("option", { value: "recommend", textContent: "Recommend for me" }),
    ...items.filter(x => ID.test(x.name)).map(x => el("option", { value: x.name, textContent: `${x.name}: ${x.description}` })));
  fill("vformat", c.video_formats);
  fill("mood", c.moodboards);
}
const pickNote = () => {
  const mood = $("mood").value, both = $("vformat").value !== "recommend" && mood !== "recommend";
  $("mood-swatch").hidden = mood === "recommend";
  if (mood !== "recommend") $("mood-swatch").src = `/swatch/${mood}.jpg`;
  $("pick-note").textContent = both ? "Your picks: the storyboard uses them as they are."
    : "Claude recommends the rest, with 2 alternatives, in the storyboard.";
};
$("mood").onchange = pickNote;
$("vformat").onchange = pickNote;

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

// The request, from the form. For a dashboard job, an HTML page is copied by the server and named there;
// for Claude Code, the page's path goes in the request and the skill runs make from-html with it.
function request(forTerminal) {
  const vf = $("vformat").value, mood = $("mood").value, page = htmlPage($("source").value);
  const source = page ? (forTerminal ? `Source: the HTML page ${page}.` : "Make a video from an HTML page.")
    : `Source: ${$("source").value.trim()}.`;
  const manual = $("name-mode").value === "manual" && $("slug").value.trim();
  return `Use the explainer-video skill. ${source} Format: ${$("format").value}. ` +
    (vf !== "recommend" && !page ? `Video format: ${vf}. ` : "") + (mood !== "recommend" ? `Moodboard: ${mood}. ` : "") +
    `3D: ${$("three").checked && !page ? "allowed (three: true)" : "off (three: false)"}. ` +
    `Voice: ${$("voice").value}. Length: ${$("length").value}, one video, no parts. ` +
    (forTerminal ? (manual ? `Name: ${$("slug").value.trim()}. ` : "") +
      ($("web").checked ? "Web research: on. " : "Web research: off: use only the source and the extra folders, and write no research.md. ") +
      ($("plan-check").checked ? "Plan check: stop after step 1. " : "") : "") +
    "Use defaults for anything else.";
}

// One word for the shell: single quotes, with each ' inside written as '\''.
const shq = t => `'${String(t).replace(/'/g, "'\\''")}'`;

$("to-claude").onclick = async () => {
  if (!$("source").value.trim()) return alert("Type a source first.");
  const dirs = $("dir").value.split("\n").map(d => d.trim()).filter(Boolean);
  const cmd = `cd ${shq(ROOT_DIR || ".")} && claude ${dirs.map(d => `--add-dir ${shq(d)} `).join("")}` +
    `${$("web").checked ? "" : "--disallowedTools WebSearch WebFetch "}${shq(request(true))}`;
  $("claude-cmd-text").textContent = cmd;
  $("claude-cmd").hidden = false;
  try { await navigator.clipboard.writeText(cmd); } catch { $("claude-cmd").querySelector("p").textContent = "Copy this and paste it in a terminal:"; }
};

$("new").onsubmit = async e => {
  e.preventDefault();
  const newSlug = $("slug").value.trim(), page = htmlPage($("source").value);
  const prompt = request(false);
  const auto = $("name-mode").value === "auto";
  $("start").disabled = true;
  $("start").textContent = auto ? "Naming the project" : "Starting";
  const r = await post("/api/jobs", { prompt, slug: auto ? "" : newSlug, auto_name: auto, source: $("source").value.trim(),
    add_dir: $("dir").value.trim(), html: page, plan_check: $("plan-check").checked, web: $("web").checked })
    .finally(() => { $("start").textContent = "Start"; refreshSystem(); });
  if (r.error) return alert(r.error);
  // Ready for the next topic: each video runs on its own and has its own card, under its project id.
  $("source").value = ""; $("slug").value = ""; $("dir").value = ""; $("plan-check").checked = false; slugEdited = false;
  $("web").checked = true; webEdited = false;
  $("html-note").hidden = true;
  $("claude-cmd").hidden = true;
  await refresh();
  open(r.slug || newSlug, "activity");
};

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
