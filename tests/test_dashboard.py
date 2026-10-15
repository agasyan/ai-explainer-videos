"""The dashboard: its claude command is an exact allowlist, and its page loads nothing from the internet."""
import http.client
import importlib.util
import json
import re
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

spec = importlib.util.spec_from_file_location("server", Path(__file__).resolve().parent.parent / "dashboard" / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


def rules(cmd, flag):
    i = cmd.index(flag)
    rest = cmd[i + 1:]
    return rest[:next((k for k, r in enumerate(rest) if r.startswith("--")), len(rest))]


class CommandTest(unittest.TestCase):
    def test_jobs_edit_only_named_sources_of_their_own_video(self):
        edits = [r for r in rules(server.command("x", slug="dns"), "--allowedTools") if r.startswith("Edit")]
        self.assertTrue(edits)
        self.assertTrue(all(r.startswith("Edit(/generated_videos/dns/") for r in edits), edits)
        self.assertFalse(any("approved" in r.lower() for r in edits))

    def test_jobs_run_make_only_for_their_own_slug(self):
        allowed = rules(server.command("x", slug="dns"), "--allowedTools")
        self.assertIn("Bash(make narrate SLUG=dns)", allowed)
        self.assertIn("Bash(make preview SLUG=dns *)", allowed)
        self.assertFalse(any(r.startswith("Bash(make narrate:") or r.startswith("Bash(make preview:") for r in allowed))
        self.assertFalse(any("SLUG=dns2" in r for r in allowed))

    def test_jobs_run_in_dont_ask_mode_and_deny_ask_rules(self):
        cmd = server.command("x")
        self.assertEqual("dontAsk", cmd[cmd.index("--permission-mode") + 1])
        self.assertIn("Bash(make approve:*)", rules(cmd, "--disallowedTools"))

    def test_a_job_cannot_touch_other_videos(self):
        import tempfile
        saved = server.VIDEOS
        with tempfile.TemporaryDirectory() as tmp:
            server.VIDEOS = Path(tmp)
            for name in ("a", "b"):
                (Path(tmp) / name).mkdir()
            try:
                own = rules(server.command("x", slug="a"), "--disallowedTools")
                new = rules(server.command("x"), "--disallowedTools")
            finally:
                server.VIDEOS = saved
        self.assertIn("Read(/generated_videos/b/**)", own)
        self.assertIn("Read(/[gG][eE][nN][eE][rR][aA][tT][eE][dD]_[vV][iI][dD][eE][oO][sS]/[bB]/**)", own)
        self.assertNotIn("Read(/generated_videos/a/**)", own)
        self.assertTrue({"Read(/generated_videos/a/**)", "Edit(/generated_videos/b/**)"} <= set(new))

    def test_a_marker_for_another_video_is_ignored(self):
        job = {"session": None, "slug": "a", "waiting": None}
        out = server.events(job, json.dumps({"type": "result", "result": "Done. WAITING FOR APPROVAL: b plan"}))
        self.assertIsNone(job["waiting"])
        self.assertIn("Ignored a check for b", out[0]["text"])
        server.events(job, json.dumps({"type": "result", "result": "WAITING FOR APPROVAL: a plan"}))
        self.assertEqual({"slug": "a", "step": "plan"}, job["waiting"])

    def test_jobs_cannot_give_auto_consent(self):
        cmd = server.command("x", slug="dns")
        self.assertIn("Bash(make auto:*)", rules(cmd, "--disallowedTools"))
        self.assertFalse(any("auto" in r for r in rules(cmd, "--allowedTools")))

    def test_read_dir_is_read_only(self):
        allowed = rules(server.command("x", read_dir="/src/repo"), "--allowedTools")
        self.assertIn("Read(//src/repo/**)", allowed)
        self.assertFalse(any(r.startswith("Edit(//src") for r in allowed))


class ProgressTest(unittest.TestCase):
    """What the video cards and the Activity tab show: the step, the sub-agents, and whose turn it is."""

    def job(self, slug="x"):
        return {"id": "j", "prompt": "p", "session": None, "events": [], "done": False, "waiting": None, "system": False,
                "slug": slug, "started": 0, "ended": None, "agents": {}, "now": "Starting Claude", "code": None}

    def line(self, job, msg):
        return server.events(job, json.dumps(msg))

    def test_each_sub_agent_gets_its_own_lane_and_report(self):
        job = self.job()
        self.line(job, {"type": "assistant", "parent_tool_use_id": None, "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Agent", "input": {"description": "Research 1914", "prompt": "Find dates"}}]}})
        out = self.line(job, {"type": "assistant", "parent_tool_use_id": "t1", "message": {"content": [
            {"type": "tool_use", "id": "t2", "name": "WebSearch", "input": {"query": "Sperry 1914"}}]}})
        self.assertEqual("t1", out[0]["agent"])
        lane = job["agents"]["t1"]
        self.assertEqual(("Research 1914", "Find dates", 1, False), (lane["name"], lane["task"], lane["steps"], lane["done"]))
        self.assertEqual("Search: Sperry 1914", lane["last"])
        self.line(job, {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": [{"type": "text", "text": "DONE: 4 claims"}]}]}})
        self.assertTrue(lane["done"])
        self.assertEqual("DONE: 4 claims", lane["report"])

    def test_a_denied_tool_is_a_log_line_not_a_crash(self):
        job = self.job()
        out = self.line(job, {"type": "system", "subtype": "permission_denied", "tool_name": "Bash",
                              "message": "Permission to use Bash has been denied because Claude Code is running in don't ask mode."})
        self.assertEqual("Denied: Bash is not allowed in dashboard jobs", out[0]["text"])
        self.assertEqual([], self.line(job, {"type": "system", "subtype": "init", "message": "plain text"}))

    def test_a_background_sub_agent_runs_until_its_notification(self):
        job = self.job()
        self.line(job, {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t9", "name": "Agent", "input": {"description": "Scene gyro", "prompt": "Draw it", "run_in_background": True}}]}})
        self.line(job, {"type": "system", "subtype": "task_started", "task_id": "k1", "tool_use_id": "t9",
                        "description": "Scene gyro", "prompt": "Draw it", "is_backgrounded": True})
        self.line(job, {"type": "user", "tool_use_result": {"status": "async_launched"}, "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t9", "content": [{"type": "text", "text": "Async agent launched"}]}]}})
        lane = job["agents"]["t9"]
        self.assertEqual((False, True, "Running in the background"), (lane["done"], lane["background"], lane["last"]))
        self.line(job, {"type": "assistant", "parent_tool_use_id": "t9", "message": {"content": [
            {"type": "text", "text": "Scene gyro: zero LINT lines."}]}})
        out = self.line(job, {"type": "system", "subtype": "task_notification", "task_id": "k1", "status": "completed",
                              "summary": "Scene gyro: zero LINT lines.", "usage": {"tool_uses": 7}})
        self.assertEqual((True, False, 7, "Scene gyro: zero LINT lines."), (lane["done"], lane["error"], lane["steps"], lane["report"]))
        self.assertEqual("t9", out[0]["agent"])

    def test_report_loses_the_hand_back_wrapper(self):
        wrapped = "[Subagent hand-back] The text below is the report. The report follows:\n  DONE\n  4 claims\nagentId: a1 (use SendMessage)"
        self.assertEqual("DONE\n4 claims", server.clean_report(wrapped))

    def test_main_agent_says_what_it_does(self):
        job = self.job()
        self.line(job, {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "a", "name": "Bash", "input": {"command": "make narrate SLUG=x"}}]}})
        self.assertEqual("Making the voice", job["now"])
        self.line(job, {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "b", "name": "Write", "input": {"file_path": "/r/generated_videos/x/scenes/hook.html"}}]}})
        self.assertEqual("Drawing scene hook", job["now"])

    def with_videos(self, fn):
        import tempfile
        saved, jobs = server.VIDEOS, dict(server.JOBS)
        server.JOBS.clear()
        with tempfile.TemporaryDirectory() as tmp:
            server.VIDEOS = Path(tmp)
            try:
                return fn(Path(tmp))
            finally:
                server.VIDEOS = saved
                server.JOBS.clear()
                server.JOBS.update(jobs)

    def test_card_shows_render_progress_and_whose_turn(self):
        def check(root):
            v = root / "x"
            (v / "build").mkdir(parents=True)
            (v / "script.yaml").write_text("title: X\nscenes: []\n")
            self.assertEqual("next", server.summary("x")["turn"])
            job = self.job()
            job["now"] = "Rendering the 720p preview"
            server.JOBS["j"] = job
            (v / "build" / "progress.json").write_text(json.dumps(
                {"step": "Rendering 720p landscape", "detail": "scene 4 of 15 (gyro)", "at": server.time.time()}))
            card = server.summary("x")
            self.assertEqual(("working", "Rendering 720p landscape: scene 4 of 15 (gyro)"), (card["turn"], card["now"]))
            job["done"] = True
            (v / "build" / "progress.json").write_text(json.dumps({"step": "done", "detail": "", "at": server.time.time()}))
            (v / "build" / "narration.json").write_text(json.dumps({"source": server.gates.fingerprint(v, "plan")}))
            self.assertEqual(("you", "Your turn: check the plan (storyboard and voice)"),
                             (server.summary("x")["turn"], server.summary("x")["now"]))
        self.with_videos(check)

    def test_a_new_job_has_a_card_before_its_folder_exists(self):
        def check(root):
            server.JOBS["j"] = self.job("fresh")
            self.assertEqual("working", server.summary("fresh")["turn"])
        self.with_videos(check)

    def test_approval_resumes_the_saved_session_after_a_restart(self):
        def check(root):
            v = root / "x"
            v.mkdir()
            job = self.job()
            job["session"] = "0b2c4d6e-0000-4000-8000-123456789abc"
            server.remember(job)
            self.assertTrue((v / "build" / "dashboard.json").is_file())
            self.assertEqual(job["session"], server.last_session("x"))  # JOBS is empty, as after a restart
            (v / "build" / "dashboard.json").write_text(json.dumps({"session": "--resume evil"}))
            self.assertIsNone(server.last_session("x"))
        self.with_videos(check)

    def test_resume_or_start_uses_the_session_or_starts_from_status(self):
        def check(root):
            started, saved = [], server.start_job
            server.start_job = lambda prompt, session=None, slug=None, **kw: started.append((prompt, session, slug)) or {"id": "n"}
            try:
                server.resume_or_start("x", "Continue with the next step.")
                (root / "x" / "build").mkdir(parents=True)
                (root / "x" / "build" / "dashboard.json").write_text(json.dumps({"session": "0b2c4d6e-0000-4000-8000-123456789abc"}))
                server.resume_or_start("x", "Continue with the next step.")
            finally:
                server.start_job = saved
            self.assertIn("make status SLUG=x", started[0][0])
            self.assertIsNone(started[0][1])
            self.assertEqual("0b2c4d6e-0000-4000-8000-123456789abc", started[1][1])
            self.assertTrue(all(p.endswith(server.DASHBOARD_JOB) and s == "x" for p, _, s in started))
        self.with_videos(check)

    def test_runs_survive_a_restart(self):
        def check(root):
            (root / "x").mkdir()
            job = self.job()
            job["id"], job["prompt"] = "0a1b2c3d", "Use the explainer-video skill."
            job["events"] = [{"kind": "say", "text": "Planning.", "agent": "main"}]
            job["agents"] = {"t1": {"name": "Research", "done": True, "report": "4 claims", "steps": 3, "started": 1, "ended": 2}}
            server.persist(job, final=True)
            job["events"].append({"kind": "tool", "text": "$ make narrate SLUG=x", "agent": "main"})
            server.persist(job, final=True)  # appends only the new line
            server.JOBS.clear()
            server.load_jobs()
            loaded = server.JOBS["0a1b2c3d"]
            self.assertEqual(["Planning.", "$ make narrate SLUG=x", "This run stopped when the dashboard stopped."],
                             [e["text"] for e in loaded["events"]])
            self.assertEqual(("4 claims", True), (loaded["agents"]["t1"]["report"], loaded["done"]))
            self.assertEqual("0a1b2c3d", server.summary("x")["job"])
            (root / "x" / "build" / "jobs" / "zz.json").write_text(json.dumps({"id": "../../etc", "slug": "x"}))
            server.JOBS.clear()
            server.load_jobs()
            self.assertEqual(["0a1b2c3d"], list(server.JOBS))
        self.with_videos(check)

    def test_a_session_id_is_never_a_flag(self):
        def check(root):
            (root / "x" / "build" / "jobs").mkdir(parents=True)
            (root / "x" / "build" / "jobs" / "0a1b2c3d.json").write_text(json.dumps(
                {"id": "0a1b2c3d", "slug": "x", "session": "--dangerously-skip-permissions", "done": True, "started": 1,
                 "system": False, "prompt": "p"}))
            server.load_jobs()
            self.assertIsNone(server.JOBS["0a1b2c3d"]["session"])
            self.assertIsNone(server.last_session("x"))
            server.JOBS["0a1b2c3d"]["session"] = "--dangerously-skip-permissions"  # even if it gets in, it never reaches argv
            self.assertIsNone(server.last_session("x"))
            cmd = server.command("p", session="--dangerously-skip-permissions", slug="x")
            self.assertFalse(any(a.startswith("--resume") or a == "--dangerously-skip-permissions" for a in cmd))
            good = "0b2c4d6e-0000-4000-8000-123456789abc"
            self.assertIn(f"--resume={good}", server.command("p", session=good, slug="x"))
            self.assertEqual(" --help", server.command("--help", slug="x")[2])
            job = self.job()
            self.line(job, {"type": "system", "subtype": "init", "session_id": "--x"})
            self.assertIsNone(job["session"])
        self.with_videos(check)

    def test_changed_code_is_reported_as_stale(self):
        saved = dict(server.CODE)
        try:
            self.assertFalse(server.stale())
            server.CODE[next(iter(server.CODE))] = 0.0
            self.assertTrue(server.stale())
        finally:
            server.CODE.clear()
            server.CODE.update(saved)


class PageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def get(self, path, method="GET", headers=None, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=5)
        conn.request(method, path, body=body, headers={"Host": f"127.0.0.1:{server.PORT}", **(headers or {})})
        r = conn.getresponse()
        return r.status, dict(r.getheaders()), r.read()

    def test_every_response_has_a_strict_csp_and_nosniff(self):
        for path in ("/", "/app.js", "/nope"):
            status, headers, _ = self.get(path)
            self.assertIn("script-src 'self'", headers.get("Content-Security-Policy", ""), path)
            self.assertEqual("nosniff", headers.get("X-Content-Type-Options"), path)

    def test_page_has_no_inline_script_and_no_remote_files(self):
        _, _, body = self.get("/")
        page = body.decode()
        self.assertNotIn("__TOKEN__", page)
        self.assertEqual([], re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", page))
        self.assertEqual([], re.findall(r"(?:src|href)=\"(?:https?:)?//", page))

    def test_vendored_kit_and_page_files_are_served(self):
        for path, kind in (("/app.js", "text/javascript"), ("/app.css", "text/css"),
                           ("/vendor/basecoat-1.0.2/basecoat.min.css", "text/css")):
            status, headers, body = self.get(path)
            self.assertEqual(200, status, path)
            self.assertTrue(headers["Content-Type"].startswith(kind), path)
            self.assertTrue(body, path)

    def test_unknown_files_are_not_served(self):
        for path in ("/vendor/basecoat-1.0.2/LICENSE.md", "/server.py", "/../ev/gates.py", "/index.html"):
            self.assertEqual(404, self.get(path)[0], path)

    def test_post_without_the_token_is_refused(self):
        self.assertEqual(403, self.get("/api/jobs", "POST", body="{}")[0])

    def test_new_job_needs_a_fresh_valid_slug(self):
        import tempfile
        saved = server.VIDEOS
        with tempfile.TemporaryDirectory() as tmp:
            server.VIDEOS = Path(tmp)
            (Path(tmp) / "dns").mkdir()
            try:
                ask = lambda slug: json.loads(self.get("/api/jobs", "POST", {"X-EV-Token": server.TOKEN},
                                                       json.dumps({"prompt": "p", "slug": slug}))[2])["error"]
                self.assertIn("lowercase letters", ask("../x"))
                self.assertIn("already exists", ask("dns"))
            finally:
                server.VIDEOS = saved

    def test_system_action_refused_while_a_job_runs(self):
        server.JOBS["busy"] = {"id": "busy", "prompt": "p", "session": None, "events": [], "done": False, "waiting": None}
        try:
            status, _, body = self.get("/api/system/stop", "POST", {"X-EV-Token": server.TOKEN}, body="{}")
        finally:
            server.JOBS.pop("busy")
        self.assertEqual("A job is running: wait for it to finish.", json.loads(body)["error"])

    def with_video(self, fn):
        import tempfile
        saved = server.VIDEOS
        with tempfile.TemporaryDirectory() as tmp:
            server.VIDEOS = Path(tmp)
            (Path(tmp) / "x").mkdir()
            (Path(tmp) / "x" / "script.yaml").write_text("title: X\nscenes: []\n")
            (Path(tmp) / "x" / "storyboard.md").write_text("# X")
            try:
                return fn(Path(tmp) / "x")
            finally:
                server.VIDEOS = saved

    def test_storyboard_is_null_before_narrate_and_never_a_file(self):
        def check(video):
            info = json.loads(self.get("/api/videos/x")[2])
            self.assertIsNone(info["storyboard"])
            self.assertFalse(info["storyboard_stale"])
            self.assertEqual(404, self.get("/files/x/storyboard.md")[0])
            (video / "build").mkdir()
            (video / "build" / "storyboard.json").write_text(json.dumps({"source": "old", "parts": []}))
            info = json.loads(self.get("/api/videos/x")[2])
            self.assertIsNone(info["storyboard"])
            self.assertTrue(info["storyboard_stale"])
        self.with_video(check)

    def test_approve_with_a_stale_or_missing_fingerprint_is_refused(self):
        def check(video):
            for body in ({"step": "plan", "expected": "0000000000000000"}, {"step": "plan"}):
                r = json.loads(self.get("/api/videos/x/approve", "POST", {"X-EV-Token": server.TOKEN}, json.dumps(body))[2])
                self.assertEqual("Changed since you looked: check again", r["error"])
            self.assertFalse((video / "approved.json").exists())
        self.with_video(check)

    def test_swatches_are_served_by_plain_name_only(self):
        status, headers, _ = self.get("/swatch/clean.jpg")
        self.assertEqual((200, "image/jpeg"), (status, headers["Content-Type"]))
        for path in ("/swatch/..%2Fclean.jpg", "/swatch/Clean.jpg", "/swatch/clean.png"):
            self.assertEqual(404, self.get(path)[0], path)

    def test_catalog_lists_both(self):
        data = json.loads(self.get("/api/catalog")[2])
        self.assertIn("instrument", [m["name"] for m in data["moodboards"]])
        self.assertIn("history-lesson", [f["name"] for f in data["video_formats"]])

    def post(self, path, body):
        return json.loads(self.get(path, "POST", {"X-EV-Token": server.TOKEN}, json.dumps(body))[2])

    def stub_jobs(self):
        """Capture what a route would start, instead of running make or claude."""
        started, saved = [], server.start_job
        server.start_job = lambda prompt, session=None, read_dir="", argv=None, slug=None, then=None: (
            started.append({"prompt": prompt, "argv": argv, "slug": slug, "session": session}) or {"id": "job1"})
        self.addCleanup(setattr, server, "start_job", saved)
        return started

    def approved_video(self, video, formats=("landscape",)):
        from ev import gates
        (video / "script.yaml").write_text("title: X\nformat: both\nscenes: []\n")
        (video / "scenes").mkdir(exist_ok=True)
        (video / "scenes" / "hook.html").write_text("<p>x</p>")
        (video / "approved.json").write_text(json.dumps({
            "plan": {"hash": gates.fingerprint(video, "plan"), "by": "t", "at": "now"},
            "preview": {"hash": gates.fingerprint(video, "preview"), "by": "t", "at": "now", "formats": list(formats)}}))

    def test_render_buttons_need_their_approvals(self):
        def check(video):
            (video / "scenes").mkdir()
            (video / "scenes" / "hook.html").write_text("<p>x</p>")
            self.assertEqual("Approve the plan first", self.post("/api/videos/x/preview", {})["error"])
            self.assertEqual("Approve the preview first", self.post("/api/videos/x/final", {})["error"])
        self.with_video(check)

    def test_final_uses_only_approved_formats_and_waits_for_a_running_job(self):
        def check(video):
            self.approved_video(video)
            started = self.stub_jobs()
            self.assertEqual("job1", self.post("/api/videos/x/final", {})["id"])
            self.assertEqual(["make", "video", "SLUG=x", "FORMAT=landscape"], started[0]["argv"])
            server.JOBS["busy"] = {"id": "busy", "prompt": "p", "session": None, "events": [], "done": False,
                                   "waiting": None, "slug": "x", "system": False}
            try:
                self.assertIn("A job is running for x", self.post("/api/videos/x/final", {})["error"])
                self.assertIn("A job is running for x", self.post("/api/videos/x/preview", {})["error"])
            finally:
                server.JOBS.pop("busy")
        self.with_video(check)

    def test_preview_approval_does_not_resume_claude(self):
        def check(video):
            from ev import gates
            self.approved_video(video)
            data = json.loads((video / "approved.json").read_text())
            data.pop("preview")
            (video / "approved.json").write_text(json.dumps(data))
            (video / "build").mkdir()
            (video / "build" / "rendered.json").write_text(json.dumps({"landscape-720p": gates.fingerprint(video, "preview")}))
            server.JOBS["j"] = {"id": "j", "prompt": "p", "session": "s1", "events": [], "done": True, "waiting": None,
                                "slug": "x", "system": False}
            started = self.stub_jobs()
            try:
                r = self.post("/api/videos/x/approve", {"step": "preview", "expected": gates.fingerprint(video, "preview"), "job": "j"})
            finally:
                server.JOBS.pop("j")
            self.assertIn("approved", r)
            self.assertNotIn("id", r)
            self.assertEqual([], started)
        self.with_video(check)

    def test_download_names_only_plain_mp4_files(self):
        def check(video):
            (video / "out").mkdir()
            for name in ("x-landscape-1080p.mp4", "Weird Name.mp4"):
                (video / "out" / name).write_bytes(b"\0\0")
            _, headers, _ = self.get("/files/x/out/x-landscape-1080p.mp4?download=1")
            self.assertEqual('attachment; filename="x-landscape-1080p.mp4"', headers.get("Content-Disposition"))
            status, headers, _ = self.get("/files/x/out/Weird%20Name.mp4?download=1")
            self.assertEqual(200, status)
            self.assertNotIn("Content-Disposition", headers)
        self.with_video(check)

    def test_review_lists_whole_renders_only(self):
        def check(video):
            (video / "out").mkdir()
            for name in ("x-part1-landscape-720p.mp4", "x-part1-hook-landscape-720p.mp4", "x-landscape-1080p.mp4"):
                (video / "out" / name).write_bytes(b"\0")
            info = json.loads(self.get("/api/videos/x")[2])
            self.assertEqual(["/files/x/out/x-part1-landscape-720p.mp4"], info["previews"])
            self.assertEqual(["/files/x/out/x-landscape-1080p.mp4"], info["finals"])
        self.with_video(check)

    def test_final_is_done_only_when_every_part_is_rendered(self):
        def check(video):
            from ev import gates
            self.approved_video(video)
            (video / "build").mkdir()
            (video / "build" / "storyboard.json").write_text(json.dumps({"parts": [{"length": 60}] * 3}))
            (video / "out").mkdir()
            (video / "out" / "x-part1-landscape-1080p.mp4").write_bytes(b"\0")
            card = server.summary("x")
            self.assertEqual((False, [1, 3]), (card["finals"], card["parts"]))
            for n in (2, 3):
                (video / "out" / f"x-part{n}-landscape-1080p.mp4").write_bytes(b"\0")
            gates.record_render(video, "landscape", "1080p", gates.fingerprint(video, "preview"))
            self.assertEqual((True, [3, 3], "done"), (server.summary("x")["finals"], server.summary("x")["parts"], server.summary("x")["turn"]))
        self.with_video(check)

    def test_a_render_that_outlived_its_job_blocks_another(self):
        def check(video):
            self.approved_video(video)
            (video / "build").mkdir()
            (video / "build" / "progress.json").write_text(json.dumps(
                {"step": "Rendering 1080p landscape", "detail": "scene 6 of 9 (fix)", "at": server.time.time()}))
            card = server.summary("x")
            self.assertEqual((True, "working"), (card["running"], card["turn"]))
            self.assertIn("A job is running for x", self.post("/api/videos/x/final", {})["error"])
        self.with_video(check)

    def test_no_timings_means_no_estimate(self):
        def check(video):
            info = json.loads(self.get("/api/videos/x")[2])
            self.assertEqual("No estimate yet: first render", info["estimate"]["720p"])
            (video / "build").mkdir()
            (video / "build" / "timings.json").write_text(json.dumps({"playwright-720p": [0.1, 0.2, 0.3]}))
            (video / "build" / "storyboard.json").write_text(json.dumps({"source": "old", "parts": [{"length": 60}]}))
            info = json.loads(self.get("/api/videos/x")[2])
            self.assertEqual("About 6 min", info["estimate"]["720p"])  # 60 s x 30 frames x 0.2 s
        self.with_video(check)

    def test_auto_start_writes_your_consent_before_the_job(self):
        import tempfile
        saved = server.VIDEOS
        with tempfile.TemporaryDirectory() as tmp:
            server.VIDEOS = Path(tmp)
            started = self.stub_jobs()
            try:
                self.assertEqual("job1", self.post("/api/jobs", {"prompt": "p", "slug": "dns", "auto": True})["id"])
                self.post("/api/jobs", {"prompt": "p", "slug": "web"})
                consent = json.loads((Path(tmp) / "dns" / "approved.json").read_text())
            finally:
                server.VIDEOS = saved
        self.assertEqual("preview", consent["auto"]["until"])
        self.assertIn("Auto until preview.", started[0]["prompt"])
        self.assertNotIn("Auto until preview.", started[1]["prompt"])

    def with_samples(self, fn):
        import tempfile
        saved = server.SAMPLES, server.VIDEOS
        with tempfile.TemporaryDirectory() as tmp:
            server.SAMPLES, server.VIDEOS = Path(tmp) / "samples", Path(tmp) / "videos"
            server.VIDEOS.mkdir()
            try:
                return fn(Path(tmp))
            finally:
                server.SAMPLES, server.VIDEOS = saved

    def test_samples_list_is_empty_without_the_folder(self):
        self.with_samples(lambda tmp: self.assertEqual({"samples": []}, json.loads(self.get("/api/samples")[2])))

    def test_start_from_a_sample_runs_new_then_narrate(self):
        def check(tmp):
            sample = server.SAMPLES / "autopilot-training"
            (sample / "frames" / "landscape" / "hook").mkdir(parents=True)
            (sample / "script.yaml").write_text("title: A\n")
            (sample / "frames" / "landscape" / "hook" / "payoff.jpg").write_bytes(b"\xff\xd8")
            (sample / "sample.json").write_text(json.dumps({"title": "<b>Autopilot</b>", "moodboard": "instrument", "three": True}))
            listed = json.loads(self.get("/api/samples")[2])["samples"]
            self.assertEqual("<b>Autopilot</b>", listed[0]["title"])  # data, shown as text by the page
            self.assertEqual("/samples/autopilot-training/frames/landscape/hook/payoff.jpg", listed[0]["frame"])
            self.assertEqual(200, self.get(listed[0]["frame"])[0])
            self.assertEqual(404, self.get("/samples/autopilot-training/script.yaml")[0])
            self.assertEqual(404, self.get("/api/samples/nope/use", "POST", {"X-EV-Token": server.TOKEN}, "{}")[0])
            (server.VIDEOS / "x").mkdir()
            self.assertEqual("generated_videos/x already exists. Use another slug.",
                             self.post("/api/samples/autopilot-training/use", {"slug": "x"})["error"])
            started = []
            saved = server.start_job
            server.start_job = lambda prompt, session=None, read_dir="", argv=None, slug=None, then=None: (
                started.append((argv, then, slug)) or {"id": "j"})
            try:
                self.assertEqual("j", self.post("/api/samples/autopilot-training/use", {"slug": "y"})["id"])
            finally:
                server.start_job = saved
            self.assertEqual([(["make", "new", "SLUG=y", "SAMPLE=autopilot-training"], ["make", "narrate", "SLUG=y"], "y")], started)
        self.with_samples(check)

    def test_page_has_zero_gradients(self):
        _, _, body = self.get("/")
        self.assertNotIn("gradient", body.decode().lower())

    def test_continue_and_change_requests_wait_for_a_running_job(self):
        def check(video):
            server.JOBS["busy"] = {"id": "busy", "prompt": "p", "session": None, "events": [], "done": False, "waiting": None,
                                   "slug": "x", "system": False, "started": 0, "agents": {}, "now": "", "code": None}
            try:
                self.assertIn("still working on x", self.post("/api/videos/x/continue", {})["error"])
            finally:
                server.JOBS.pop("busy")
            self.assertEqual("Type the change first.", self.post("/api/videos/x/reply", {"text": "  "})["error"])
            started = self.stub_jobs()
            self.assertEqual("job1", self.post("/api/videos/x/reply", {"text": "Beat 3 is wrong."})["id"])
            self.assertIn("Change request: Beat 3 is wrong.", started[0]["prompt"])
        self.with_video(check)

    def test_unknown_system_action_is_404(self):
        status, _, _ = self.get("/api/system/explode", "POST", {"X-EV-Token": server.TOKEN}, body="{}")
        self.assertEqual(404, status)

    def test_page_css_has_zero_gradients(self):
        self.assertNotIn("gradient", (Path(server.__file__).parent / "app.css").read_text())


class SystemTest(unittest.TestCase):
    def setUp(self):
        self.saved = dict(server.TOOLS), server.probe, dict(server.JOBS), dict(server.LAST)
        server.TOOLS.update({"docker": "/x/docker", "colima": "/x/colima", "make": "/x/make", "claude": None, "open": None})
        server.JOBS.clear()

    def tearDown(self):
        tools, server.probe, jobs, last = self.saved
        server.TOOLS.clear(); server.TOOLS.update(tools)
        server.JOBS.clear(); server.JOBS.update(jobs)
        server.LAST.clear(); server.LAST.update(last)

    def wait(self, job):
        for _ in range(100):
            if job["done"]:
                return job
            threading.Event().wait(0.05)
        self.fail("job did not finish")

    def test_actions_are_fixed_commands(self):
        self.assertEqual(["make", "build"], server.system_argv("build"))
        self.assertEqual(["colima", "start"], server.system_argv("start"))
        self.assertIsNone(server.system_argv("rm -rf /"))

    def test_docker_missing(self):
        server.TOOLS["docker"] = None
        self.assertEqual("missing", server.system_state()["docker"])

    def test_docker_that_hangs_reads_not_responding(self):
        server.probe = lambda argv, timeout=5: None
        self.assertEqual("not responding", server.system_state()["docker"])

    def test_running_docker_without_the_image(self):
        server.probe = lambda argv, timeout=5: (0, "27.4.0") if argv[1] == "info" else (1, "")
        state = server.system_state()
        self.assertEqual(("running", "missing"), (state["docker"], state["image"]))

    def test_a_claude_job_carries_its_slug_for_make_to_enforce(self):
        seen = {}

        class FakePopen:
            def __init__(self, cmd, **kw):
                seen.update(kw, cmd=cmd)
                self.stdout = iter(())

            def wait(self):
                return 0

        real = server.subprocess.Popen
        server.subprocess.Popen = FakePopen
        try:
            self.wait(server.start_job("make a video", slug="dns"))
        finally:
            server.subprocess.Popen = real
        self.assertEqual("dns", seen["env"]["EV_JOB_SLUG"])
        self.assertIn("Bash(*SLUG*SLUG*)", rules(seen["cmd"], "--disallowedTools"))

    def test_failed_build_keeps_its_last_line(self):
        job = self.wait(server.start_job("System: build", argv=["sh", "-c", "echo step one; echo no space left; exit 1"]))
        self.assertEqual("Failed (exit 1): no space left", job["events"][-1]["text"])

    def test_a_failed_three_check_turns_3d_off(self):
        result = server.doctor_result(["ok   ffmpeg", "FAIL three.js WebGL: no context"])
        self.assertIs(False, result["three"])
        self.assertIs(True, server.doctor_result(["ok   three.js WebGL (0.186.1): same frame twice, same pixels"])["three"])
        saved = server.LAST["doctor"]
        server.LAST["doctor"] = result
        try:
            self.assertIs(False, server.system_state()["three"])
        finally:
            server.LAST["doctor"] = saved

    def test_doctor_result_is_remembered(self):
        self.wait(server.start_job("System: doctor", argv=["sh", "-c", "echo 'ok   ffmpeg'; echo 'FAIL whisper-cli'; true doctor"]))
        self.assertIsNone(server.LAST["doctor"])  # only a real doctor run (argv ends with doctor) counts
        self.wait(server.start_job("System: doctor", argv=["sh", "-c", "echo 'ok   ffmpeg'; echo 'FAIL whisper-cli'", "doctor"]))
        self.assertEqual((1, ["whisper-cli"]), (server.LAST["doctor"]["ok"], server.LAST["doctor"]["fail"]))


if __name__ == "__main__":
    unittest.main()
