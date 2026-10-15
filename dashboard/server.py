#!/usr/bin/env python3
"""Local dashboard: start Claude Code jobs, check the plan and the preview, approve them, and play the results.

Run `make dashboard`, then open http://127.0.0.1:8787. It runs on the host, not in Docker: each job
starts `claude -p` with your Claude Code login, and Claude runs `make` targets, which use Docker.
The Approve button records the approval through ev/gates.py; Claude itself cannot approve.
Listens on 127.0.0.1 only; checks the Host header; every POST needs the per-run token from the page.
Jobs run in dontAsk mode with an allowlist: they edit only a video's sources and run only the commands that
.claude/settings.json allows, so text hidden in a source cannot make Claude change the tool.
"""
import fnmatch
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))  # last, so a stray datetime.py in the repo cannot shadow the standard library
from ev import gates  # noqa: E402 (standard library only, so it runs on the host)

VIDEOS = ROOT / "generated_videos"
SAMPLES = ROOT / "videos" / "samples"
PORT = int(os.environ.get("PORT", "8787"))
TOKEN = secrets.token_urlsafe(24)
HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
SERVABLE = ["*/out/*.mp4", "*/out/*.vtt", "*/build/narration.wav", "*/build/review/*.png", "*/frames/*/*/*.jpg"]
TYPES = {".mp4": "video/mp4", ".vtt": "text/vtt; charset=utf-8", ".wav": "audio/wav", ".png": "image/png",
         ".jpg": "image/jpeg"}
CATALOG = {"moodboards": ROOT / "moodboards", "video_formats": ROOT / "video-formats"}
SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")
HERE = Path(__file__).resolve().parent
# The page's own files, by exact URL. The UI kit is vendored, so the page loads nothing from the internet.
STATIC = {"/app.js": ("app.js", "text/javascript; charset=utf-8"), "/app.css": ("app.css", "text/css; charset=utf-8"),
          "/vendor/basecoat-1.0.2/basecoat.min.css": ("vendor/basecoat-1.0.2/basecoat.min.css", "text/css; charset=utf-8")}
# Same-origin files only, no inline script: text that slips into the page cannot run or reach another site.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; "
       "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
WAITING = re.compile(r"WAITING FOR APPROVAL: ([a-z0-9-]+) (plan|preview)")
# A Claude session id is a UUID. Anything else is refused wherever an id enters (the stream, saved runs, dashboard.json):
# `--resume` takes an optional value, so an "id" such as --dangerously-skip-permissions would parse as its own flag.
SESSION = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def session_id(value):
    return value if isinstance(value, str) and SESSION.fullmatch(value) else None
AGENT_TOOLS = ("Agent", "Task")
JOBS = {}
# The Python this process loaded. The page files are read on each request, but this code is not: when it changes on
# disk, the page says "restart make dashboard" instead of mixing a new page with an old server.
CODE = {p: p.stat().st_mtime for p in (Path(__file__).resolve(), ROOT / "ev" / "gates.py")}


def stale():
    return any(not p.exists() or p.stat().st_mtime != t for p, t in CODE.items())
# What a job may write in its video folder, by exact name. Anything else (approved.json, build/, a Makefile, in any
# letter case) matches no rule and is refused: a disk that ignores case cannot widen an allowlist.
SOURCES = ["script.yaml", "research.md", "style.css", "scenes/*.html", "assets/**"]


# The make targets a job may run, always for its own slug only (the page fixes the slug when the job starts).
JOB_MAKE = ("new", "narrate", "storyboard", "status", "preview", "video")


def bound(slug):
    """Allow rules that name the job's own slug exactly: `make narrate SLUG=dns`, or with options after a space."""
    return [rule for target in JOB_MAKE for rule in (f"Bash(make {target} SLUG={slug})", f"Bash(make {target} SLUG={slug} *)")]


def command(prompt, session=None, read_dir="", slug=None):
    """The claude command for a job. An allowlist, not a denylist: anything not listed is refused without a prompt.
    A job works on one video, its slug: it may not run make for, read, or edit any other video's folder."""
    rules = json.loads((ROOT / ".claude" / "settings.json").read_text())["permissions"]
    general = [r for r in rules["allow"] if not r.startswith("Bash(make ") or r in ("Bash(make help)", "Bash(make doctor)")]
    allow = (general + bound(slug) + [f"Edit(/generated_videos/{slug}/{s})" for s in SOURCES]
             + ([f"Read(/{read_dir}/**)"] if read_dir else []))
    prompt = f" {prompt}" if prompt.startswith("-") else prompt  # a prompt is never read as a flag
    session = session_id(session)
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose", "--permission-mode", "dontAsk",
           "--allowedTools", *allow, "--disallowedTools", *rules["deny"], *rules["ask"], *others(slug),
           "Bash(*SLUG*SLUG*)"]  # no one to ask; and no second SLUG= that would switch the video
    return cmd + ([f"--resume={session}"] if session else [])


# The System panel's actions: fixed commands, found once. Nothing from a request ever enters an argv.
TOOLS = {name: shutil.which(name) for name in ("docker", "colima", "make", "claude", "open")}
DOCKER_APP = Path("/Applications/Docker.app")
LAST = {"doctor": None, "login": (0.0, "unknown")}


def system_argv(action):
    """The command for a System panel action, or None when this machine cannot do it."""
    if action in ("build", "doctor"):
        return ["make", action] if TOOLS["make"] else None
    if action == "start":
        return ["colima", "start"] if TOOLS["colima"] else ["open", "-a", "Docker"] if DOCKER_APP.exists() else None
    if action == "stop":
        return ["colima", "stop"] if TOOLS["colima"] else None
    return None


def probe(argv, timeout=5):
    """(exit code, output) of a quick check, or None when it does not answer in time."""
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip()
    except subprocess.TimeoutExpired:
        return None
    except OSError:
        return 127, ""


def system_state():
    """What the System panel shows: Docker, the image, the last doctor run, and the Claude Code login."""
    state = {"docker": "missing", "runtime": "colima" if TOOLS["colima"] else "docker-desktop" if DOCKER_APP.exists() else "none",
             "image": "unknown", "doctor": LAST["doctor"], "claude": "missing",
             "three": (LAST["doctor"] or {}).get("three"),  # None until doctor runs; False turns the 3D box off
             "busy": any(not j["done"] for j in JOBS.values())}
    if TOOLS["docker"]:
        r = probe(["docker", "info", "--format", "{{.ServerVersion}}"])
        state["docker"] = "not responding" if r is None else "running" if r[0] == 0 else "stopped"
        if state["docker"] == "running":
            r = probe(["docker", "image", "inspect", "ai-explainer-videos", "--format", "{{.Id}}"])
            state["image"] = "built" if r and r[0] == 0 else "missing"
    if TOOLS["claude"]:
        checked, login = LAST["login"]
        if time.time() - checked > 60:  # the login rarely changes; check once a minute
            r = probe(["claude", "auth", "status", "--json"], timeout=20)
            try:
                login = "logged in" if r and json.loads(r[1]).get("loggedIn") else "logged out"
            except ValueError:
                login = "logged out"
            LAST["login"] = (time.time(), login)
        state["claude"] = login
    return state


def doctor_result(lines):
    ok = [line[5:] for line in lines if line.startswith("ok   ")]
    fail = [line[5:] for line in lines if line.startswith("FAIL ")]
    three = (True if any(x.startswith("three.js WebGL") for x in ok)
             else False if any(x.startswith("three.js WebGL") for x in fail) else None)
    return {"ok": len(ok), "fail": fail, "at": time.strftime("%H:%M"), "three": three}


def anycase(text):
    """A path pattern that matches any letter case ([gG][eE]...): macOS ignores case, path rules may not."""
    return "".join(f"[{c.lower()}{c.upper()}]" if c.isalpha() else c for c in text)


def others(slug):
    """Deny rules for every video folder except the job's own, in plain and any-case form."""
    names = sorted(d.name for d in VIDEOS.glob("*") if d.is_dir() and d.name.lower() != slug) if VIDEOS.is_dir() else []
    paths = [p for name in names for p in (f"generated_videos/{name}", anycase(f"generated_videos/{name}"))]
    return [f"{tool}(/{path}/**)" for path in paths for tool in ("Read", "Edit")]


# ---------- run history on disk: generated_videos/<slug>/build/jobs/<id>.json (state) and .jsonl (log) ----------

JOB_ID = re.compile(r"[0-9a-f]{8}")
META = ("id", "prompt", "session", "done", "waiting", "system", "slug", "started", "ended", "agents", "now", "code")


def persist(job, final=False):
    """Save a video's run, so a restarted dashboard still shows its Activity. Throttled to once a second while it
    runs; a new video's folder may not exist yet, so the log waits until it does."""
    slug = job.get("slug")
    if not slug or not (VIDEOS / slug).is_dir() or (not final and time.time() - job.get("saved_at", 0) < 1):
        return
    folder = VIDEOS / slug / "build" / "jobs"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        new = job["events"][job.get("saved", 0):]
        with open(folder / f"{job['id']}.jsonl", "a") as log:
            log.writelines(json.dumps(e) + "\n" for e in new)
        job["saved"] = job.get("saved", 0) + len(new)
        tmp = folder / f"{job['id']}.json.tmp"
        tmp.write_text(json.dumps({k: job.get(k) for k in META}))
        tmp.replace(folder / f"{job['id']}.json")
        job["saved_at"] = time.time()
    except OSError:
        pass  # history is a nicety; the run itself goes on


def load_jobs(keep=20):
    """Read the saved runs of every video (the newest `keep` each). A run that was going when the dashboard stopped
    is shown as stopped: its process ended with the dashboard."""
    for folder in sorted(VIDEOS.glob("*/build/jobs")) if VIDEOS.is_dir() else []:
        metas = []
        for path in folder.glob("*.json"):
            try:
                meta = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
            if isinstance(meta, dict) and JOB_ID.fullmatch(str(meta.get("id", ""))) and meta.get("slug") == folder.parent.parent.name:
                metas.append(meta)
        for meta in sorted(metas, key=lambda m: float(m.get("started") or 0))[-keep:]:
            events = []
            try:
                for line in (folder / f"{meta['id']}.jsonl").read_text().splitlines():
                    e = json.loads(line)
                    if isinstance(e, dict) and isinstance(e.get("text"), str):
                        events.append({"kind": str(e.get("kind", "tool")), "text": e["text"], "agent": str(e.get("agent", "main"))})
            except (OSError, ValueError):
                pass
            job = {k: meta.get(k) for k in META} | {"events": events, "tasks": {}, "saved": len(events), "saved_at": time.time()}
            job["session"] = session_id(job["session"])  # a saved file is data: never pass its text to claude unchecked
            job["agents"] = job["agents"] if isinstance(job["agents"], dict) else {}
            job["prompt"], job["now"] = str(job["prompt"] or ""), str(job["now"] or "")
            job["system"], job["waiting"] = job["system"] is True, None
            try:
                job["started"] = float(job["started"] or 0)
                job["ended"] = float(job["ended"]) if job["ended"] is not None else None
            except (TypeError, ValueError):
                continue
            job["code"] = job["code"] if isinstance(job["code"], int) else None
            if not job["done"]:
                job.update(done=True, ended=job["started"], now="Stopped when the dashboard stopped")
                job["events"].append({"kind": "result", "text": "This run stopped when the dashboard stopped.", "agent": "main"})
            JOBS.setdefault(job["id"], job)


def start_job(prompt, session=None, read_dir="", argv=None, slug=None, then=None):
    """Run claude for a request, or a fixed command (argv, then `then` if it succeeds). All stream into the job log."""
    job = {"id": uuid.uuid4().hex[:8], "prompt": prompt, "session": session, "events": [], "done": False,
           "waiting": None, "system": bool(argv), "slug": slug, "started": time.time(), "ended": None,
           "agents": {}, "tasks": {}, "now": prompt if argv else "Starting Claude", "code": None}
    JOBS[job["id"]] = job
    cmd = argv or command(prompt, session, read_dir, slug)

    def work():
        lines, code = [], 0
        for step in [cmd, *([then] if then and argv else [])]:
            try:
                env = {**os.environ, "EV_JOB_SLUG": slug} if slug and not argv else None  # make refuses any other SLUG
                proc = subprocess.Popen(step, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, errors="replace", env=env)
            except OSError as e:
                job["events"].append({"kind": "result", "text": f"Failed: {e}"})
                job["code"], job["ended"], job["done"] = 127, time.time(), True
                return
            for raw in proc.stdout:
                if argv:
                    lines.append(raw.rstrip())
                try:
                    job["events"] += events(job, raw)
                except Exception as e:  # one odd line must never stop the log: Claude keeps working either way
                    job["events"].append({"kind": "tool", "agent": "main",
                                          "text": f"The dashboard could not read one line ({type(e).__name__}); it keeps reading."})
                    traceback.print_exc()
                persist(job)
            code = proc.wait()
            if code:
                break
        for lane in job["agents"].values():  # a sub-agent still open when the job ends stopped with it
            if not lane["done"]:
                lane.update(done=True, ended=time.time(), error=True, last="Stopped when the job ended")
        if argv:
            last = next((line for line in reversed(lines) if line.strip()), "no output")
            job["events"].append({"kind": "result", "text": f"Done: {last}" if code == 0 else f"Failed (exit {code}): {last}"})
            if argv[-1] == "doctor":
                LAST["doctor"] = doctor_result(lines)
        else:
            job["events"].append({"kind": "result", "text": f"(claude exited with code {code})"})
        job["code"], job["ended"], job["done"] = code, time.time(), True
        persist(job, final=True)

    threading.Thread(target=work, daemon=True).start()
    return job


def describe(name, i):
    """One short log line for a tool call."""
    if name == "Bash":
        return f"$ {i.get('command', '')}"
    if name in AGENT_TOOLS:
        return f"Start sub-agent: {i.get('description') or i.get('subagent_type') or ''}"
    if name == "SendMessage":
        return f"Message to {i.get('to', '')}: {' '.join(str(i.get('message', '')).split())[:160]}"
    detail = {"WebSearch": "query", "WebFetch": "url", "Skill": "skill"}.get(name)
    detail = i.get(detail) if detail else (i.get("file_path") or i.get("pattern") or i.get("path") or "")
    label = {"WebSearch": "Search", "WebFetch": "Read page", "Edit": "Write", "Write": "Write", "MultiEdit": "Write"}
    return f"{label.get(name, name)}: {detail}"


def doing(name, i):
    """What a job does now, in words, for its video card."""
    if name == "Bash":
        cmd = str(i.get("command", ""))
        for target, text in (("narrate", "Making the voice"), ("preview", "Rendering the 720p preview"),
                             ("video", "Rendering 1080p"), ("new", "Creating the video folder"),
                             ("storyboard", "Writing the storyboard"), ("status", "Checking where the video is")):
            if re.match(rf"make {target}\b", cmd):
                return text
        return "Running a command"
    if name in ("Edit", "Write", "MultiEdit"):
        path = str(i.get("file_path", ""))
        for end, text in (("script.yaml", "Writing the script"), ("research.md", "Writing the research"),
                          ("style.css", "Writing the style")):
            if path.endswith(end):
                return text
        found = re.search(r"scenes/([a-z0-9-]+)\.html$", path)
        return f"Drawing scene {found[1]}" if found else "Writing files"
    return {"WebSearch": "Researching", "WebFetch": "Reading sources", "Read": "Reading", "Glob": "Reading",
            "Grep": "Reading", "Skill": "Loading the skill"}.get(name, "Working")


def remember(job):
    """Keep a video's Claude session on disk, so Approve can resume it after the dashboard restarts."""
    folder = VIDEOS / (job.get("slug") or "")
    if job.get("slug") and session_id(job["session"]) and folder.is_dir():
        try:
            (folder / "build").mkdir(exist_ok=True)
            (folder / "build" / "dashboard.json").write_text(json.dumps({"session": job["session"]}))
        except OSError:
            pass


def last_session(slug):
    """The newest Claude session for a video: from this run's jobs, else from build/dashboard.json."""
    jobs = sorted((j for j in JOBS.values() if j.get("slug") == slug and not j["system"] and session_id(j.get("session"))),
                  key=lambda j: j["started"])
    if jobs:
        return jobs[-1]["session"]
    try:
        session = json.loads((VIDEOS / slug / "build" / "dashboard.json").read_text()).get("session", "")
    except (OSError, ValueError, AttributeError):
        return None
    return session_id(session)


def add_lane(job, lane_id, name, task, parent="main"):
    """One sub-agent, keyed by the id of the Agent call that started it."""
    return job["agents"].setdefault(lane_id, {
        "name": str(name or "sub-agent")[:80], "task": str(task or "")[:4000], "done": False, "error": False,
        "background": False, "last": "Starting", "steps": 0, "started": time.time(), "ended": None, "report": "",
        "said": "", "parent": parent})


def clean_report(text):
    """A sub-agent's report without the hand-back wrapper Claude Code puts around it."""
    text = str(text or "")
    if text.startswith("[Subagent hand-back]") and "The report follows:" in text:
        lines = text.split("The report follows:", 1)[1].splitlines()
        text = "\n".join(line[2:] if line.startswith("  ") else line for line in lines)
    return "\n".join(line for line in text.splitlines() if not line.startswith("agentId: ")).strip()


def finish(lane, status, report, usage):
    """Mark a sub-agent finished. Its report is the longest of: its result, its summary, its last words."""
    lane.update(done=True, ended=time.time(), error=status not in ("completed", ""))
    lane["report"] = max((lane["report"], clean_report(report), lane.get("said", "")), key=len)[:20000]
    if isinstance(usage, dict) and isinstance(usage.get("tool_uses"), int):
        lane["steps"] = max(lane["steps"], usage["tool_uses"])
    return lane


def events(job, raw):
    """Turn one stream-json line into short log lines, each tagged with its agent: "main" or a sub-agent's id.
    Notes what the job does now, which sub-agents run, and when Claude waits for an approval."""
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        return [{"kind": "tool", "text": raw.rstrip(), "agent": "main"}] if raw.strip() else []
    if not isinstance(msg, dict):
        return []
    job.setdefault("agents", {})
    job.setdefault("now", "")
    if session_id(msg.get("session_id")) and msg["session_id"] != job["session"]:
        job["session"] = msg["session_id"]
        remember(job)
    job.setdefault("tasks", {})
    parent = msg.get("parent_tool_use_id")
    agent = parent if isinstance(parent, str) and parent in job["agents"] else "main"
    out = []
    message = msg.get("message")  # an object for chat messages; plain text for some system lines
    content = message.get("content") if isinstance(message, dict) else None
    content = [c for c in content if isinstance(c, dict)] if isinstance(content, list) else []
    kind, sub = msg.get("type"), msg.get("subtype")
    if kind == "system":
        if sub == "task_started" and isinstance(msg.get("tool_use_id"), str):  # a sub-agent starts
            lane = add_lane(job, msg["tool_use_id"], msg.get("description"), msg.get("prompt"))
            lane["background"] = msg.get("is_backgrounded") is True
            if isinstance(msg.get("task_id"), str):
                job["tasks"][msg["task_id"]] = msg["tool_use_id"]
        elif sub == "task_notification":  # a sub-agent ends: completed, failed, or stopped
            lane_id = msg.get("tool_use_id") if msg.get("tool_use_id") in job["agents"] else job["tasks"].get(msg.get("task_id"))
            if lane_id in job["agents"]:
                lane = finish(job["agents"][lane_id], str(msg.get("status") or ""), str(msg.get("summary") or ""), msg.get("usage"))
                out.append({"kind": "tool", "text": f"Sub-agent {msg.get('status') or 'ended'}: {lane['name']}", "agent": lane_id})
        elif sub == "permission_denied":
            out.append({"kind": "tool", "agent": agent,
                         "text": f"Denied: {msg.get('tool_name') or 'a tool'} is not allowed in dashboard jobs"})
        return out
    if kind == "assistant":
        for c in content:
            if c.get("type") == "text" and str(c.get("text", "")).strip():
                out.append({"kind": "say", "text": str(c["text"]), "agent": agent})
                if agent != "main":
                    job["agents"][agent]["said"] = str(c["text"])[:20000]
            elif c.get("type") == "tool_use":
                name, i = str(c.get("name", "")), c.get("input") if isinstance(c.get("input"), dict) else {}
                line = describe(name, i)[:300]
                out.append({"kind": "tool", "text": line, "agent": agent})
                if name in AGENT_TOOLS and isinstance(c.get("id"), str):
                    add_lane(job, c["id"], i.get("description") or i.get("subagent_type"), i.get("prompt"), agent)
                if agent == "main":
                    job["now"] = doing(name, i)
                else:
                    job["agents"][agent]["last"] = line[:120]
                    job["agents"][agent]["steps"] += 1
    elif kind == "user":
        for c in content:
            if c.get("type") == "tool_result" and c.get("tool_use_id") in job["agents"]:
                lane = job["agents"][c["tool_use_id"]]
                result = msg.get("tool_use_result") if isinstance(msg.get("tool_use_result"), dict) else {}
                status = str(result.get("status") or "")
                if status == "async_launched":  # it runs on in the background; task_notification says when it ends
                    lane.update(background=True, last="Running in the background")
                    continue
                body = c.get("content")
                report = body if isinstance(body, str) else "\n".join(
                    str(x.get("text", "")) for x in body or [] if isinstance(x, dict) and x.get("type") == "text")
                if not lane["done"]:
                    finish(lane, "failed" if c.get("is_error") else status or "completed", report, result.get("usage"))
                    out.append({"kind": "tool", "text": f"Sub-agent done: {lane['name']}", "agent": c["tool_use_id"]})
                elif len(clean_report(report)) > len(lane["report"]):
                    lane["report"] = clean_report(report)[:20000]
    elif kind == "result":
        text = msg.get("result") or msg.get("subtype", "")
        found = WAITING.search(text)
        if found and found[1] != job["slug"]:  # a job's slug is fixed at start; its own output cannot change it
            out.append({"kind": "tool", "text": f"Ignored a check for {found[1]}: this job works on {job['slug']}."})
            found = None
        job["waiting"] = {"slug": found[1], "step": found[2]} if found else None
        said = next((e["text"] for e in reversed(job.get("events", [])) if e.get("agent") == "main" and e["kind"] in ("say", "result")), "")
        if text.strip() != said.strip():  # the result repeats Claude's last message: show it once
            out.append({"kind": "result", "text": text, "agent": "main"})
    return out


def samples():
    """Committed samples (videos/samples/<name>/sample.json, written by make sample). Text only reaches the page."""
    out = []
    for path in sorted(SAMPLES.glob("*/sample.json")) if SAMPLES.is_dir() else []:
        try:
            info = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if SLUG.fullmatch(path.parent.name) and isinstance(info, dict):
            out.append({"name": path.parent.name, **{k: str(info.get(k, "")) for k in ("title", "format", "moodboard", "video_format")},
                        "three": info.get("three") is True,
                        "frame": next((f"/samples/{path.parent.name}/{f.relative_to(path.parent)}"
                                       for f in sorted(path.parent.glob("frames/*/*/*.jpg"))), None)})
    return out


def field(v, key):
    """A top-level `key: value` of script.yaml, read without YAML (the host has no YAML library)."""
    script = v / "script.yaml"
    match = re.search(rf"^{key}:[ \t]*([a-z0-9-]+)", script.read_text(), re.M) if script.is_file() else None
    return match[1] if match else ""


DASHBOARD_JOB = " Dashboard job: stop after the preview check; the page renders 1080p."


def resume_or_start(slug, text):
    """Continue a video in Claude: resume its last session (it keeps the context), else a new job that starts
    from make status. Used by Approve, Continue, and Request changes."""
    session = last_session(slug)
    if session:
        return start_job(f"{text} Slug: {slug}.{DASHBOARD_JOB}", session=session, slug=slug)
    return start_job(f"Use the explainer-video skill. Continue the video in generated_videos/{slug}: run "
                     f"make status SLUG={slug} and do the next step. {text} Slug: {slug}.{DASHBOARD_JOB}", slug=slug)


def jobs_for(slug):
    return sorted((j for j in JOBS.values() if j.get("slug") == slug), key=lambda j: j["started"], reverse=True)


def title(v):
    script = v / "script.yaml"
    match = re.search(r"^title:[ \t]*(.+?)[ \t]*$", script.read_text(), re.M) if script.is_file() else None
    return match[1].strip("\"'")[:120] if match else ""


def read_progress(v, after=None):
    """build/progress.json while the pipeline works: written after `after` (a running job's start), else in the last
    15 minutes (one 1080p scene can take several). None once it says done."""
    try:
        p = json.loads((v / "build" / "progress.json").read_text())
        at = float(p["at"])
        fresh = at >= after - 5 if after else time.time() - at < 900
        return p if p.get("step") != "done" and fresh else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def final_parts(v, board=None):
    """(1080p part videos made from the approved preview, parts expected): the final is done when they match."""
    approved = gates.read(v, "approved.json").get("preview") or {}
    formats = approved.get("formats") or []
    if not formats or not gates.approved(v, "preview"):
        return 0, 0
    if board is None:
        try:
            board = json.loads((v / "build" / "storyboard.json").read_text())
        except (OSError, ValueError):
            board = {}
    parts = len(board.get("parts") or []) or 1
    ready = [p for p in full(v, "out/*-1080p.mp4") if p.stat().st_mtime >= approved_time(approved)]
    rendered = gates.read(v, "build/rendered.json")
    complete = all(rendered.get(f"{f}-1080p") == approved.get("hash") for f in formats)
    return (parts * len(formats) if complete else min(len(ready), parts * len(formats) - 1)), parts * len(formats)


def approved_time(entry):
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(entry.get("at"))).timestamp()
    except ValueError:
        return 0


def summary(slug):
    """A video card: its checks, what happens now, and whose turn it is (working, you, next, or done)."""
    v = VIDEOS / slug
    st = gates.status(v) if (v / "script.yaml").is_file() else {"plan": "waiting", "preview": "waiting"}
    jobs = jobs_for(slug)
    live = next((j for j in jobs if not j["done"]), None)
    ready, total = final_parts(v)
    finals = bool(total) and ready == total
    orphan = None if live else read_progress(v)
    if orphan:  # a render still running in Docker after its job ended
        now, turn = f"{orphan['step']}: {orphan['detail']}", "working"
    elif live:
        now, turn = live["now"], "working"
        progress = read_progress(v, after=live["started"])
        if progress and (live["system"] or now.startswith(("Making", "Rendering"))):
            now = f"{progress['step']}: {progress['detail']}"
        busy = sum(not a["done"] for a in live["agents"].values())
        if busy:
            now += f" · {busy} sub-agent{'s' if busy > 1 else ''} working"
        if total and not finals and st["preview"] == "approved":
            now += f" · {ready} of {total} parts ready"
    elif st["plan"] in ("ready", "changed"):
        now, turn = "Your turn: check the plan (storyboard and voice)", "you"
    elif st["preview"] in ("ready", "changed"):
        now, turn = "Your turn: check the 720p preview", "you"
    elif st["preview"] == "approved":
        now, turn = ("Done: the 1080p video is ready", "done") if finals else ("Your turn: render 1080p", "you")
    elif st["plan"] in ("approved", "auto"):
        now, turn = "Next: Claude writes the scenes and renders 720p. Press Continue.", "next"
    elif jobs and jobs[0]["code"] not in (0, None):
        now, turn = "The last job stopped with an error: see Activity, then press Continue", "next"
    else:
        now, turn = "Not finished: press Continue", "next"
    return {"slug": slug, "title": title(v) or slug, "status": st, "running": bool(live or orphan), "now": now, "turn": turn,
            "since": live["started"] if live else None, "finals": finals, "parts": [ready, total],
            "job": jobs[0]["id"] if jobs else None,
            "last": max([j["started"] for j in jobs] + [v.stat().st_mtime if v.exists() else 0])}


def running(slug):
    """The running job for this video, or a running System job (a build or doctor would break a render)."""
    return next((j for j in JOBS.values() if not j["done"]
                 and (j.get("slug") == slug or (j.get("system") and not j.get("slug")))), None)


def timings(v):
    """Seconds per frame of earlier renders: this video's, else any video's (the machine is the same)."""
    found = {}
    for path in [v / "build" / "timings.json", *sorted(VIDEOS.glob("*/build/timings.json"))]:
        try:
            for key, values in json.loads(path.read_text()).items():
                found.setdefault(key, []).extend(x for x in values if isinstance(x, (int, float)))
        except (OSError, ValueError, AttributeError):
            continue
        if path == v / "build" / "timings.json" and found:
            break
    return found


def estimate(v, quality, board):
    """'About 4 min' for a full render: frames (from the storyboard) x the median seconds per frame."""
    per = sorted(timings(v).get(f"{field(v, 'engine') or 'playwright'}-{quality}", []))
    if not per or not board:
        return "No estimate yet: first render"
    formats = (gates.read(v, "approved.json").get("preview", {}).get("formats") or ["landscape"]) if quality == "1080p" \
        else (["landscape", "story"] if field(v, "format") == "both" else ["one"])
    frames = sum(p.get("length", 0) for p in board.get("parts", [])) * 30 * len(formats)
    return f"About {max(1, round(frames * per[len(per) // 2] / 60))} min"


def storyboard(v):
    """build/storyboard.json from the last narrate, or None when there is none or script.yaml changed since.
    Data only: the page shows every string through textContent."""
    try:
        board = json.loads((v / "build" / "storyboard.json").read_text())
    except (OSError, ValueError):
        return None, False
    fresh = isinstance(board, dict) and board.get("source") == gates.fingerprint(v, "plan")
    return (board, False) if fresh else (None, True)


def full(v, pattern):
    """Files of whole renders only: <slug>[-partN]-<format>-<quality>, not the one-scene renders made while drawing."""
    whole = re.compile(rf"{re.escape(v.name)}(-part\d+)?-(landscape|story)-(720p|1080p)(-contact-\d+)?\.(mp4|png)")
    return [p for p in sorted(v.glob(pattern)) if whole.fullmatch(p.name)]


def video_info(slug):
    v = VIDEOS / slug
    url = lambda p: f"/files/{p.relative_to(VIDEOS)}"  # noqa: E731
    script = v / "script.yaml"
    board, stale = storyboard(v)
    try:
        last = json.loads((v / "build" / "storyboard.json").read_text())  # for the estimate, even if stale
    except (OSError, ValueError):
        last = None
    job = running(slug)
    return {"slug": slug, "status": gates.status(v), "checklist": gates.CHECK, "summary": summary(slug),
            "jobs": [{k: j[k] for k in ("id", "prompt", "done", "started", "ended", "code", "system")} for j in jobs_for(slug)],
            "has_scenes": any((v / "scenes").glob("*.html")), "running": bool(job),
            "estimate": {q: estimate(v, q, last) for q in ("720p", "1080p")},
            "fingerprints": {step: gates.fingerprint(v, step) for step in gates.STEPS},
            "storyboard": board, "storyboard_stale": stale,
            "script": script.read_text() if script.exists() else "",
            "audio": url(v / "build/narration.wav") if (v / "build/narration.wav").exists() else None,
            "previews": [url(p) for p in full(v, "out/*-720p.mp4")],
            "finals": [url(p) for p in full(v, "out/*-1080p.mp4")],
            "downloads": [url(p) + "?download=1" for p in full(v, "out/*-1080p.mp4")],
            "contacts": [url(p) for p in full(v, "build/review/*-720p-contact-*.png")]}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get("Host") not in HOSTS:
            return self.send_error(403)
        url = urlparse(self.path)
        parts = url.path.strip("/").split("/")
        if url.path == "/":
            page = (HERE / "index.html").read_text().replace("__TOKEN__", TOKEN)
            return self.send_body(page.encode(), "text/html; charset=utf-8")
        if url.path in STATIC:
            name, kind = STATIC[url.path]
            return self.send_body((HERE / name).read_bytes(), kind)
        if parts == ["api", "system"]:
            return self.send_json(system_state())
        if parts == ["api", "samples"]:
            return self.send_json({"samples": samples()})
        if parts == ["api", "catalog"]:  # written by make catalog; names only reach the page as text
            return self.send_json({k: json.loads((d / "catalog.json").read_text()) if (d / "catalog.json").is_file() else []
                                   for k, d in CATALOG.items()})
        if (len(parts) == 6 and parts[0] == "samples" and parts[2] == "frames" and parts[5].endswith(".jpg")
                and all(SLUG.fullmatch(x) for x in (parts[1], parts[3], parts[4], parts[5][:-4]))):
            path = SAMPLES.joinpath(*parts[1:])  # samples/<name>/frames/<format>/<scene>/<beat>.jpg, plain ids only
            if path.is_file():
                return self.send_file(path)
        if len(parts) == 2 and parts[0] == "swatch" and parts[1].endswith(".jpg") and SLUG.fullmatch(parts[1][:-4]):
            path = CATALOG["moodboards"] / parts[1][:-4] / "swatch.jpg"
            if path.is_file():
                return self.send_file(path)
        if parts == ["api", "state"]:
            slugs = {d.name for d in VIDEOS.glob("*") if (d / "script.yaml").exists()} | {
                j["slug"] for j in JOBS.values() if j.get("slug") and SLUG.fullmatch(j["slug"])}
            cards = sorted((summary(s) for s in slugs), key=lambda c: (not c["running"], -c["last"]))
            system = [{k: j[k] for k in ("id", "prompt", "done", "code")} | {"last": next(
                (e["text"] for e in reversed(j["events"]) if e["text"].strip()), "")} for j in JOBS.values()
                if j["system"] and not j.get("slug")]
            return self.send_json({"videos": cards, "system": system[-1:], "stale": stale()})
        if len(parts) == 3 and parts[:2] == ["api", "jobs"] and parts[2] in JOBS:
            job, since = JOBS[parts[2]], int(parse_qs(url.query).get("since", ["0"])[0])
            keys = ("prompt", "done", "waiting", "now", "started", "ended", "code", "agents", "system", "session")
            return self.send_json({**{k: job[k] for k in keys}, "events": job["events"][since:], "total": len(job["events"])})
        if len(parts) == 3 and parts[:2] == ["api", "videos"] and SLUG.fullmatch(parts[2]) and (
                (VIDEOS / parts[2]).is_dir() or jobs_for(parts[2])):  # a new job's folder may not exist yet
            return self.send_json(video_info(parts[2]))
        if parts[0] == "files":
            rel = unquote(url.path[len("/files/"):])
            path = (VIDEOS / rel).resolve()
            if (path.is_relative_to(VIDEOS.resolve()) and path.is_file()
                    and any(fnmatch.fnmatch(rel, pattern) for pattern in SERVABLE)):
                download = parse_qs(url.query).get("download") == ["1"] and re.fullmatch(r"[a-z0-9-]+\.mp4", path.name)
                return self.send_file(path, path.name if download else None)
        self.send_error(404)

    def do_POST(self):
        if self.headers.get("Host") not in HOSTS or self.headers.get("X-EV-Token") != TOKEN:
            return self.send_error(403)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) == 3 and parts[:2] == ["api", "system"]:
            argv = system_argv(parts[2]) if parts[2] in ("start", "stop", "build", "doctor") else None
            if parts[2] not in ("start", "stop", "build", "doctor"):
                return self.send_error(404)
            if any(not j["done"] for j in JOBS.values()):
                return self.send_json({"error": "A job is running: wait for it to finish."})
            if not argv:
                return self.send_json({"error": {"start": "Install Colima or Docker Desktop first (README, Quick start).",
                                                   "stop": "Stop Docker Desktop from its own menu."}.get(parts[2], "make is not installed.")})
            labels = {"start": "System: start Docker", "stop": "System: stop Docker", "build": "System: build the image",
                      "doctor": "System: run doctor"}
            return self.send_json({"id": start_job(labels[parts[2]], argv=argv)["id"]})
        if parts == ["api", "jobs"]:
            slug = str(body.get("slug", ""))
            if not SLUG.fullmatch(slug) or len(slug) > 60:
                return self.send_json({"error": "Slug: lowercase letters, digits, and dashes, for example how-dns-works."})
            if any(d.name.lower() == slug for d in VIDEOS.glob("*")):
                return self.send_json({"error": f"generated_videos/{slug} already exists. Use another slug."})
            read_dir = str(Path(body["add_dir"]).expanduser().resolve()) if body.get("add_dir") else ""
            if read_dir and not Path(read_dir).is_dir():
                return self.send_json({"error": f"Not a folder: {read_dir}"})
            prompt = f"{body['prompt']} Slug: {slug}. Dashboard job: stop after the preview check; the page renders 1080p."
            if body.get("auto") is True:  # your Start click is the consent; the job itself can never write it
                (VIDEOS / slug).mkdir()
                gates.consent(VIDEOS / slug)
                prompt += " Auto until preview."
            return self.send_json({"id": start_job(prompt, read_dir=read_dir, slug=slug)["id"]})
        if len(parts) == 4 and parts[:2] == ["api", "samples"] and parts[3] == "use":
            name, slug = parts[2], str(body.get("slug", ""))
            if not SLUG.fullmatch(name) or not (SAMPLES / name / "script.yaml").is_file():
                return self.send_error(404)
            if not SLUG.fullmatch(slug) or len(slug) > 60:
                return self.send_json({"error": "Slug: lowercase letters, digits, and dashes, for example how-dns-works."})
            if any(d.name.lower() == slug for d in VIDEOS.glob("*")):
                return self.send_json({"error": f"generated_videos/{slug} already exists. Use another slug."})
            job = start_job(f"Sample {name}: {slug}", argv=["make", "new", f"SLUG={slug}", f"SAMPLE={name}"],
                            slug=slug, then=["make", "narrate", f"SLUG={slug}"])
            return self.send_json({"id": job["id"]})
        if (len(parts) == 4 and parts[:2] == ["api", "videos"] and parts[3] in ("continue", "reply")
                and SLUG.fullmatch(parts[2]) and ((VIDEOS / parts[2]).is_dir() or jobs_for(parts[2]))):
            slug, text = parts[2], " ".join(str(body.get("text", "")).split())[:2000]
            if running(slug):
                return self.send_json({"error": f"Claude is still working on {slug}: wait for this step to finish."})
            if parts[3] == "reply" and not text:
                return self.send_json({"error": "Type the change first."})
            ask = (f"Change request: {text} Apply it, run the step again, then ask for the check again."
                   if parts[3] == "reply" else "Continue with the next step.")
            return self.send_json({"id": resume_or_start(slug, ask)["id"]})
        if (len(parts) == 4 and parts[:2] == ["api", "videos"] and parts[3] in ("preview", "final")
                and SLUG.fullmatch(parts[2]) and (VIDEOS / parts[2] / "script.yaml").is_file()):
            slug, v = parts[2], VIDEOS / parts[2]
            if running(slug) or read_progress(v):  # a render can outlive its job (it runs on in Docker)
                return self.send_json({"error": f"A job is running for {slug}: wait for it to finish."})
            if parts[3] == "preview":
                if not (gates.approved(v, "plan") or gates.auto(v)):
                    return self.send_json({"error": "Approve the plan first"})
                if not any((v / "scenes").glob("*.html")):
                    return self.send_json({"error": "No scenes yet: step 2 writes them"})
                argv = ["make", "preview", f"SLUG={slug}"]
            else:
                if not gates.approved(v, "preview"):
                    return self.send_json({"error": "Approve the preview first"})
                formats = gates.read(v, "approved.json")["preview"].get("formats") or []
                argv = ["make", "video", f"SLUG={slug}", f"FORMAT={'both' if len(formats) > 1 else formats[0]}"]
            label = f"{'Preview 720p' if parts[3] == 'preview' else 'Final 1080p'}: {slug}"
            return self.send_json({"id": start_job(label, argv=argv, slug=slug)["id"]})
        if len(parts) == 4 and parts[:2] == ["api", "videos"] and parts[3] == "approve" and SLUG.fullmatch(parts[2]):
            slug, step, expected = parts[2], body.get("step", ""), body.get("expected")
            if not isinstance(expected, str) or not expected:  # the page always sends what it showed
                return self.send_json({"error": "Changed since you looked: check again"})
            try:
                entry = gates.approve(VIDEOS / slug, step, expected)
            except SystemExit as e:
                return self.send_json({"error": str(e)})
            if step == "plan" and not running(slug):  # after the preview, Claude stops: 1080p is your button
                follow = resume_or_start(slug, "Approved: the plan. Continue with step 2.")
                return self.send_json({"approved": entry, "id": follow["id"]})
            return self.send_json({"approved": entry})
        self.send_error(404)

    def end_headers(self):
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def send_json(self, data):
        self.send_body(json.dumps(data).encode(), "application/json")

    def send_body(self, data, kind):
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_file(self, path, download=None):
        """Serve media with HTTP Range support, so players can seek. `download` is a checked plain file name."""
        size = path.stat().st_size
        start, end = 0, size - 1
        ranged = self.headers.get("Range", "").startswith("bytes=")
        if ranged:
            a, _, b = self.headers["Range"][6:].split(",")[0].partition("-")
            start, end = (int(a), int(b) if b else size - 1) if a else (max(size - int(b), 0), size - 1)
            end = min(end, size - 1)
        self.send_response(206 if ranged else 200)
        self.send_header("Content-Type", TYPES[path.suffix])
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{download}"')
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if ranged:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with path.open("rb") as f:
            f.seek(start)
            left = end - start + 1
            try:
                while left > 0 and (chunk := f.read(min(1 << 16, left))):
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the player closed the connection to seek

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    if not shutil.which("claude"):
        sys.exit("Claude Code is not installed: https://docs.claude.com/en/docs/claude-code")
    load_jobs()
    print(f"Dashboard: http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
