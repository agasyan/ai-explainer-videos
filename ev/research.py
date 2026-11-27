"""research.md: the facts a video states, each with the sources that back it. Standard library only.

One markdown table, one row per claim:

    | id | claim | source 1 | source 2 | status |
    |----|-------|----------|----------|--------|
    | c1 | Sperry flew hands-off in 1914 | [NASM](https://...) | [FAA](https://...) | two sources |

A source is a web link, or a file in backticks (`sources/page.md`, `src/rank.py:L40-L52`): a page, a doc, a folder
file, a PR diff. A beat cites claims with `sources: [c1]` in script.yaml. A claim with one source is "one source";
with none, "no source". A source that the researcher could not open does not count: its cell says "not opened".
A claim whose status says "conflict" has sources that disagree: a beat cannot state it.
"""
import re
from pathlib import Path

LINK = re.compile(r"https?://[^\s)>\]|]+")
FILE = re.compile(r"`([^`\s]+?\.[A-Za-z0-9]{1,5})(?::[^`\s]*)?`")  # a file in backticks; a line range after : is not part of it
ROW = re.compile(r"^\|\s*(c\d+)\s*\|(.*)\|\s*$")
# Words that make a number worth a source. One to ten are too common in plain speech ("one zone") to count.
NUMBER = re.compile(r"\d|\b(eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|"
                    r"forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|percent)\b", re.I)


def rows(path):
    """[{"id", "claim", "links", "files", "status"}] from research.md; [] when the file does not exist.
    The status counts different sources, web links and files together, or is "conflict" when the row says so."""
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
        opened = [cell for cell in cells[1:3] if "not opened" not in cell.lower()]
        links = [link for cell in opened for link in LINK.findall(cell)]
        files = sorted({name for cell in opened for name in FILE.findall(LINK.sub("", cell))})
        count = len(set(links)) + len(files)
        status = ("conflict" if any("conflict" in cell.lower() for cell in cells[3:]) else
                  "two sources" if count >= 2 else "one source" if count else "no source")
        out.append({"id": match[1], "claim": claim, "links": links, "files": files, "status": status})
    return out


def summary(path):
    found = rows(path)
    return {"claims": len(found), "one_source": sum(r["status"] == "one source" for r in found),
            "no_source": sum(r["status"] == "no source" for r in found),
            "conflict": sum(r["status"] == "conflict" for r in found)}


def checks(spec, path):
    """CHECK lines for narrate: a beat that cites a claim research.md lacks, cites a claim whose sources disagree,
    or states a number with no source. With no research.md, one line when any beat states a number: every video
    that states a fact has the claims table, whatever its sources (a topic, a page, a folder, a PR)."""
    numbered = [f"{scene['id']}/{beat.get('id', i)}" for part in spec["parts"] for scene in part["scenes"]
                for i, beat in enumerate(scene["beats"]) if NUMBER.search(str(beat.get("say", "")))]
    if not Path(path).is_file():
        return ([f"research.md is missing, and {len(numbered)} beat{'s state' if len(numbered) > 1 else ' states'} a "
                 f"number ({', '.join(numbered[:3])}{', ...' if len(numbered) > 3 else ''}): write one row per claim, "
                 "with its sources (docs/writing.md, Research)"] if numbered else [])
    found = rows(path)
    known = {r["id"] for r in found}
    disputed = {r["id"] for r in found if r["status"] == "conflict"}
    issues = []
    for part in spec["parts"]:
        for scene in part["scenes"]:
            for i, beat in enumerate(scene["beats"]):
                where = f"{scene['id']}/{beat.get('id', i)}"
                cited = [str(c) for c in beat.get("sources") or []]
                issues += [f"{where} cites {c}, which research.md lacks" for c in cited if c not in known]
                issues += [f"{where} cites {c}, where the sources disagree: settle it with the user, or leave it out"
                           for c in cited if c in disputed]
                if NUMBER.search(str(beat.get("say", ""))) and not cited:
                    issues.append(f"{where} has a number and no source: add sources: [c<n>] from research.md")
    return issues
