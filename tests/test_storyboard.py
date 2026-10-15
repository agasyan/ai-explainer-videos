"""storyboard.md: picks, one row per beat, treatment checks, and the frames a full 720p render saves."""
import tempfile
import unittest
from pathlib import Path

from ev import catalog, storyboard

KNOWN = {"video_format": catalog.names("video_format"), "moodboard": catalog.names("moodboard")}
PICKS = {"video_format": [{"name": "history-lesson", "why": "Then and now: the topic is a lesson from the past."},
                          {"name": "how-it-works", "why": "Explains the autopilot loop."},
                          {"name": "compare", "why": "Pilot then and engineer now."}],
         "moodboard": [{"name": "instrument", "why": "Cockpit states map to alert colors."},
                       {"name": "archival", "why": "Old photos carry the history."},
                       {"name": "editorial", "why": "Dates and quotes."}]}


def spec(**extra):
    return {"title": "T", "brief": {"takeaway": "Train for the failure.", "viewer": "engineers"},
            "video_format": "history-lesson", "moodboard": "instrument", "picks": PICKS,
            "parts": [{"title": "One", "scenes": [
                {"id": "hook", "treatment": "title", "beats": [{"id": "payoff", "say": "Pilots *train* hard.", "show": "A title."},
                                                               {"id": "then", "say": "In 1914.", "show": "A | date.", "sources": ["c1"]}]},
                {"id": "now", "treatment": "timeline", "beats": [{"id": "now", "say": "Now.", "show": "A tape."}]}]}],
            **extra}


NARRATION = {"source": "abc", "gap": 0.5, "scenes": {
    "hook": [{"id": "payoff", "text": "Pilots train hard.", "duration": 2.0}, {"id": "then", "text": "In 1914.", "duration": 1.0}],
    "now": [{"id": "now", "text": "Now.", "duration": 1.0}]}}


class StoryboardTest(unittest.TestCase):
    def board(self, s=None, frames=None):
        s = s or spec()
        return storyboard.build(s, NARRATION, catalog.moodboard(s["moodboard"]), KNOWN, frames=frames)

    def test_picks_list_one_recommended_and_two_alternatives_with_reasons(self):
        text = storyboard.markdown(self.board())
        self.assertIn("**Video format: `history-lesson`**", text)
        self.assertIn("- Recommended: `instrument`: Cockpit states map to alert colors.", text)
        self.assertEqual(4, text.count("- Alternative: "))
        self.assertEqual([], self.board()["checks"])

    def test_two_scenes_three_beats_make_three_rows(self):
        rows = self.board()["parts"][0]["rows"]
        self.assertEqual(["hook/payoff", "hook/then", "now/now"], [r["n"] for r in rows])
        self.assertEqual(["00:00.0", "00:02.5", "00:04.0"], [r["time"] for r in rows])
        self.assertEqual("Pilots train hard.", rows[0]["voice"])
        self.assertEqual(["c1"], rows[1]["sources"])

    def test_markdown_opens_with_the_header_and_escapes_pipes(self):
        text = storyboard.markdown(self.board())
        self.assertEqual("Generated from script.yaml; edit that file.", text.splitlines()[2])
        self.assertIn("Reading this as: Train for the failure. For: engineers.", text)
        self.assertIn("A \\| date.", text)

    def test_treatment_not_in_the_moodboard_is_a_check(self):
        s = spec()
        s["parts"][0]["scenes"][1]["treatment"] = "quote"  # instrument has no quote treatment
        self.assertTrue(any("treatment quote is not in moodboard instrument" in c for c in self.board(s)["checks"]))
        s["parts"][0]["scenes"][1].pop("treatment")
        self.assertTrue(any("now: add treatment" in c for c in self.board(s)["checks"]))

    def test_picks_need_three_known_entries_with_a_why(self):
        s = spec(picks={"moodboard": PICKS["moodboard"][:2], "video_format": [*PICKS["video_format"][:2], {"name": "nope", "why": ""}]})
        checks = self.board(s)["checks"]
        self.assertTrue(any(c.startswith("picks.moodboard: 3 different entries") for c in checks))
        self.assertTrue(any("no video format named 'nope'" in c for c in checks))
        self.assertTrue(any("nope needs a one-line why" in c for c in checks))

    def test_recommend_left_in_the_script_is_a_check(self):
        s = spec(moodboard="recommend")
        board = storyboard.build(s, NARRATION, None, KNOWN)
        self.assertTrue(any(c.startswith("moodboard: recommend") for c in board["checks"]))

    def test_no_picks_list_means_the_form_chose(self):
        s = spec(picks={})
        board = self.board(s)
        self.assertEqual("form", board["picks"]["moodboard"]["how"])
        self.assertIn("(chosen in the New video form)", storyboard.markdown(board))

    def test_stage_3d_scene_reads_3d(self):
        s = spec()
        s["parts"][0]["scenes"][1]["treatment"] = "stage-3d"
        self.assertEqual("3D", self.board(s)["parts"][0]["rows"][2]["dim"])

    def test_frames_of_a_full_render_fill_the_frame_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp)
            from PIL import Image
            still = video / "still.jpg"
            Image.new("RGB", (1280, 720), "white").save(still)
            from ev.render import save_frames
            save_frames(video, "landscape", [(still, "hook/payoff", "A title.")])
            self.assertTrue((video / "frames/landscape/hook/payoff.jpg").is_file())
            self.assertEqual(640, Image.open(video / "frames/landscape/hook/payoff.jpg").size[0])
            found = storyboard.frames(video, {"format": "landscape"})
            self.assertEqual({"hook/payoff": "frames/landscape/hook/payoff.jpg"}, found)
            self.assertIn("![hook/payoff](frames/landscape/hook/payoff.jpg)", storyboard.markdown(self.board(frames=found)))


if __name__ == "__main__":
    unittest.main()
