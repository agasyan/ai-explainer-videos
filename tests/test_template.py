"""templates/video/: every word a starter scene waits for is in that beat's `say` line of the starter script."""
import re
import unittest
from pathlib import Path

import yaml

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "video"


def norm(word):
    return re.sub(r"[^a-z0-9]", "", word.lower())


class TemplateTest(unittest.TestCase):
    def test_each_timed_word_is_said_in_its_beat(self):
        spec = yaml.safe_load((TEMPLATE / "script.yaml").read_text().replace("__TITLE__", "T"))
        said = {b["id"]: [norm(w) for w in b["say"].split()] for s in spec["scenes"] for b in s["beats"]}
        missing = []
        for scene in sorted((TEMPLATE / "scenes").glob("*.html")):
            for beat, word in re.findall(r'at\("([a-z0-9-]+)",\s*"([^"]+)"\)', scene.read_text()):
                if norm(word) not in said.get(beat, []):
                    missing.append(f"{scene.name}: {word!r} is not in beat {beat!r}")
        self.assertEqual([], missing)

    def test_the_starter_uses_line_captions_and_a_scene_title(self):
        spec = yaml.safe_load((TEMPLATE / "script.yaml").read_text().replace("__TITLE__", "T"))
        self.assertEqual("line", spec["captions"])
        self.assertTrue(spec["scenes"][0].get("title"))


if __name__ == "__main__":
    unittest.main()
