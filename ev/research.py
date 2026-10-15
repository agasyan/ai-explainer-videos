"""research.md: the facts a video states, each with the sources that back it. Standard library only.

One markdown table, one row per claim:

    | id | claim | source 1 | source 2 | status |
    |----|-------|----------|----------|--------|
    | c1 | Sperry flew hands-off in 1914 | [NASM](https://...) | [FAA](https://...) | two sources |

A beat cites claims with `sources: [c1]` in script.yaml. A claim with one link is "one source"; with none, "no source".
"""
import re
from pathlib import Path

LINK = re.compile(r"https?://[^\s)>\]|]+")
ROW = re.compile(r"^\|\s*(c\d+)\s*\|(.*)\|\s*$")
# Words that make a number worth a source. One to ten are too common in plain speech ("one zone") to count.
NUMBER = re.compile(r"\d|\b(eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|"
                    r"forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|percent)\b", re.I)


def rows(path):
    """[{"id", "claim", "links", "status"}] from research.md; [] when the file does not exist."""
    path = Path(path)
    if not path.is_file():
        return []
    out = []
    for line in path.read_text().splitlines():
        match = ROW.match(line.strip())
        if not match:
            continue
        cells = [c.strip() for c in match[2].split("|")]
        claim = cells[0] if cells else ""
        links = [link for cell in cells[1:3] for link in LINK.findall(cell)]
        out.append({"id": match[1], "claim": claim, "links": links,
                    "status": "two sources" if len(links) >= 2 else "one source" if links else "no source"})
    return out


def summary(path):
    found = rows(path)
    return {"claims": len(found), "one_source": sum(r["status"] == "one source" for r in found),
            "no_source": sum(r["status"] == "no source" for r in found)}


def checks(spec, path):
    """CHECK lines for narrate: a beat that cites a claim research.md lacks, or states a number with no source.
    Runs only when research.md exists (a PR or repo video cites its own files instead)."""
    if not Path(path).is_file():
        return []
    known = {r["id"] for r in rows(path)}
    issues = []
    for part in spec["parts"]:
        for scene in part["scenes"]:
            for i, beat in enumerate(scene["beats"]):
                where = f"{scene['id']}/{beat.get('id', i)}"
                cited = [str(c) for c in beat.get("sources") or []]
                issues += [f"{where} cites {c}, which research.md lacks" for c in cited if c not in known]
                if NUMBER.search(str(beat.get("say", ""))) and not cited:
                    issues.append(f"{where} has a number and no source: add sources: [c<n>] from research.md")
    return issues
