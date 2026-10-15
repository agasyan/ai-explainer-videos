"""Approval checks: what a hash covers, and which file holds approvals."""
import json
import tempfile
import unittest
from pathlib import Path

from ev import gates

SCRIPT = "title: T\nlook: clean\nscenes:\n  - id: hook\n    beats:\n      - id: hook\n        say: Hello there.\n"


class GatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.video = Path(self.tmp.name) / "demo"
        self.video.mkdir()
        (self.video / "script.yaml").write_text(SCRIPT)

    def tearDown(self):
        self.tmp.cleanup()

    def approval(self, name):
        entry = {"plan": {"hash": gates.fingerprint(self.video, "plan"), "by": "t", "at": "now"}}
        (self.video / name).write_text(json.dumps(entry))

    def test_look_line_does_not_change_the_plan_hash(self):
        before = gates.fingerprint(self.video, "plan")
        (self.video / "script.yaml").write_text(SCRIPT.replace("look: clean", "look: dark"))
        self.assertEqual(before, gates.fingerprint(self.video, "plan"))

    def test_say_line_changes_the_plan_hash(self):
        before = gates.fingerprint(self.video, "plan")
        (self.video / "script.yaml").write_text(SCRIPT.replace("Hello there.", "Hi."))
        self.assertNotEqual(before, gates.fingerprint(self.video, "plan"))

    def test_plan_hash_covers_research_only_when_it_exists(self):
        before = gates.fingerprint(self.video, "plan")
        (self.video / "research.md").write_text("| c1 | a claim | https://a | https://b | two sources |\n")
        self.assertNotEqual(before, gates.fingerprint(self.video, "plan"))
        (self.video / "research.md").unlink()
        self.assertEqual(before, gates.fingerprint(self.video, "plan"))

    def test_exact_name_counts(self):
        self.approval("approved.json")
        self.assertTrue(gates.approved(self.video, "plan"))

    def test_case_variant_alone_does_not_count(self):
        self.approval("Approved.json")
        if (self.video / "approved.json").exists() and "approved.json" in [p.name for p in self.video.iterdir()]:
            self.skipTest("case-sensitive name collision on this file system")
        self.assertFalse(gates.approved(self.video, "plan"))

    def test_exact_name_plus_case_variant_does_not_count(self):
        self.approval("approved.json")
        self.approval("APPROVED.JSON")
        if len([p for p in self.video.iterdir() if p.name.lower() == "approved.json"]) < 2:
            self.skipTest("case-insensitive file system holds only one of the two names")
        self.assertFalse(gates.approved(self.video, "plan"))

    def test_approve_removes_a_case_variant(self):
        self.approval("Approved.json")
        (self.video / "build").mkdir()
        (self.video / "build" / "narration.json").write_text(
            json.dumps({"source": gates.fingerprint(self.video, "plan")}))
        gates.approve(self.video, "plan")
        self.assertEqual(["approved.json"], [p.name for p in self.video.iterdir() if p.name.lower() == "approved.json"])
        self.assertTrue(gates.approved(self.video, "plan"))


    def narrated(self):
        (self.video / "build").mkdir(exist_ok=True)
        (self.video / "build" / "narration.json").write_text(json.dumps({"source": gates.fingerprint(self.video, "plan")}))

    def previewed(self):
        (self.video / "build" / "rendered.json").write_text(
            json.dumps({"landscape-720p": gates.fingerprint(self.video, "preview")}))

    def test_approve_refuses_a_fingerprint_nobody_saw(self):
        self.narrated()
        with self.assertRaisesRegex(SystemExit, "Changed since you looked: check again"):
            gates.approve(self.video, "plan", expected="0000000000000000")
        gates.approve(self.video, "plan", expected=gates.fingerprint(self.video, "plan"))
        self.assertTrue(gates.approved(self.video, "plan"))

    def test_auto_consent_allows_720p_but_not_1080p(self):
        with self.assertRaises(SystemExit):
            gates.require(self.video, "720p")
        gates.consent(self.video, by="t")
        gates.require(self.video, "720p")
        self.assertEqual("auto", gates.status(self.video)["plan"])
        with self.assertRaises(SystemExit):
            gates.require(self.video, "1080p", "landscape")

    def test_preview_approval_under_auto_approves_the_plan_once(self):
        gates.consent(self.video, by="t")
        self.narrated()
        self.previewed()
        gates.approve(self.video, "preview")
        data = gates.read(self.video, "approved.json")
        self.assertEqual("preview", data["plan"]["with"])
        self.assertNotIn("auto", data)
        self.assertEqual({"plan": "approved", "preview": "approved"}, gates.status(self.video))
        (self.video / "script.yaml").write_text(SCRIPT.replace("Hello there.", "Hi."))
        with self.assertRaises(SystemExit):  # the consent is used up: an edited plan needs a check again
            gates.require(self.video, "720p")

    def test_any_approval_uses_the_consent_up(self):
        gates.consent(self.video, by="t")
        self.narrated()
        gates.approve(self.video, "plan")
        self.assertFalse(gates.auto(self.video))


class HashReadsWhatYamlReadsTest(unittest.TestCase):
    """The hash reads script.yaml line by line; the pipeline reads it as YAML. load() refuses any script where they differ."""

    def load(self, text):
        from ev.common import load
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "script.yaml").write_text(text)
            return load(Path(tmp))

    def test_plain_script_loads(self):
        self.assertEqual("hook", self.load(SCRIPT.replace("look: clean", "moodboard: clean  # the look"))["parts"][0]["scenes"][0]["id"])

    def test_template_and_nested_picks_load(self):
        from ev.common import ROOT
        self.load((ROOT / "templates" / "video" / "script.yaml").read_text())
        before = "title: T\npicks:\n  moodboard:\n    - {name: clean, why: a}\n" + SCRIPT.split("\n", 1)[1]
        self.load(before)
        with tempfile.TemporaryDirectory() as tmp:  # picks are part of the plan
            video = Path(tmp)
            (video / "script.yaml").write_text(before)
            first = gates.fingerprint(video, "plan")
            (video / "script.yaml").write_text(before.replace("why: a", "why: b"))
            self.assertNotEqual(first, gates.fingerprint(video, "plan"))

    def test_hold_line_inside_a_say_block_is_refused(self):
        text = SCRIPT.replace("say: Hello there.", "say: |\n          Hello there.\n          hold: this line is narration too")
        with self.assertRaises(SystemExit):
            self.load(text)

    def test_quoted_or_repeated_moodboard_is_refused(self):
        for text in (SCRIPT + 'moodboard: "instrument"\n', SCRIPT + "moodboard: clean\nmoodboard: instrument\n",
                     SCRIPT + "moodboard:\n  instrument\n"):
            with self.assertRaises(SystemExit, msg=text):
                self.load(text)

    def test_moodboard_file_is_in_the_preview_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp)
            (video / "script.yaml").write_text(SCRIPT + "moodboard: instrument\n")
            self.assertEqual([gates.MOODBOARDS / "instrument" / "moodboard.md"], gates.moodboard_file(video))

    def test_old_look_loads_no_moodboard(self):
        from ev.render import moodboard_name
        self.assertIsNone(moodboard_name(self.load(SCRIPT.replace("look: clean", "look: instrument"))))
        with self.assertRaises(SystemExit):
            moodboard_name(self.load(SCRIPT + "moodboard: dark\n"))  # aliases are for look: only


if __name__ == "__main__":
    unittest.main()
