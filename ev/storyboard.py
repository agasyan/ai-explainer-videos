"""storyboard.md: the plan as one document, made from script.yaml and the narration. Never edit it by hand.

It opens with the picks (a recommended video format and moodboard, each with 2 alternatives and a reason), then the
video direction (the moodboard's color, type, and motion roles), then one table per part: one row per beat, with its
time, voice, picture, treatment, 2D or 3D, sources, and frame. `make narrate` writes it, and a full 720p render adds
the frames. The dashboard reads the same data from build/storyboard.json and shows it as text, never as HTML.

Standard library only at the top level; refresh() loads the catalogs (YAML) inside Docker.
"""
import json
from pathlib import Path

HEADER = "Generated from script.yaml; edit that file."
CATALOGS = (("video_format", "Video format"), ("moodboard", "Moodboard"))
ROLES = (("accent", "main idea"), ("accent-2", "second idea"), ("good", "right, gain"), ("bad", "wrong, loss"))


def stamp(t):
    """Seconds as mm:ss.d, for example 00:07.5."""
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def cell(text):
    """One markdown table cell: no line breaks, and a | cannot open a new column."""
    return " ".join(str(text).split()).replace("|", "\\|")


def picks(spec, known):
    """{catalog: {"chosen", "how", "options": [{"name", "why"}]}} for the catalogs this video uses, and CHECK lines.
    `known` maps each catalog to its entry names. No `picks:` list means the New video form chose that entry."""
    out, issues = {}, []
    given = spec.get("picks") or {}
    for key, label in CATALOGS:
        if key not in spec:
            continue
        chosen = str(spec[key])
        options = [{"name": str(o.get("name", "")), "why": " ".join(str(o.get("why", "")).split())}
                   for o in (given.get(key) or []) if isinstance(o, dict)]
        out[key] = {"chosen": chosen, "how": "recommended" if options else "form", "options": options}
        if chosen == "recommend":
            issues.append(f"{key}: recommend is still in script.yaml: run the recommender (SKILL step 1)")
        elif chosen not in known[key]:
            issues.append(f"{key}: no {label.lower()} named {chosen!r}; choose one of {', '.join(known[key])}")
        if options:
            names = [o["name"] for o in options]
            if len(options) != 3 or len(set(names)) != 3:
                issues.append(f"picks.{key}: 3 different entries, the recommended one first, then 2 alternatives")
            issues += [f"picks.{key}: no {label.lower()} named {n!r}" for n in names if n not in known[key]]
            issues += [f"picks.{key}: {o['name']} needs a one-line why" for o in options if not o["why"]]
    return out, issues


def build(spec, narration, mood=None, known=None, research_rows=(), frames=None):
    """Everything storyboard.md and the dashboard show, as plain data. `frames` maps "scene/beat" to a frame path."""
    known = known or {"video_format": [], "moodboard": []}
    chosen, issues = picks(spec, known)
    treatments = list((mood or {}).get("treatments") or [])
    brief = spec.get("brief") or {}
    parts = []
    for n, part in enumerate(spec["parts"], 1):
        t, rows, three = 0.0, [], 0
        for scene in part["scenes"]:
            treatment = str(scene.get("treatment") or "")
            if mood and not treatment:
                issues.append(f"{scene['id']}: add treatment: one of {', '.join(treatments)} (moodboard {mood['name']})")
            elif mood and treatment not in treatments:
                issues.append(f"{scene['id']}: treatment {treatment} is not in moodboard {mood['name']}: "
                              f"use one of {', '.join(treatments)}")
            dim = "3D" if treatment == "stage-3d" or scene.get("three_why") else "2D"
            if dim == "3D" and spec.get("three") is not True:
                issues.append(f"{scene['id']}: three is off for this video: draw it in 2D")
            elif dim == "3D" and not str(scene.get("three_why") or "").strip():
                issues.append(f"{scene['id']}: add three_why: one line on why 3D explains it better than 2D")
            three += dim == "3D"
            for beat, clip in zip(scene["beats"], narration["scenes"][scene["id"]]):
                where = f"{scene['id']}/{clip['id']}"
                rows.append({"n": where, "scene": scene["id"], "beat": clip["id"], "time": stamp(t),
                             "voice": clip["text"], "show": " ".join(str(beat.get("show", "")).split()),
                             "treatment": treatment, "dim": dim,
                             "sources": [str(c) for c in beat.get("sources") or []],
                             "frame": (frames or {}).get(where)})
                t += clip["duration"] + narration["gap"] + float(beat.get("hold", 0))
        if three > 2:
            issues.append(f"Part {n}: 3D in {three} scenes: keep 3D for spatial ideas, 2 per part at most")
        parts.append({"n": n, "title": str(part.get("title", "")), "length": round(t, 1), "rows": rows})
    direction = None
    if mood:
        c, ty, m = mood["colors"], mood["typography"], mood["motion"]
        direction = {"moodboard": mood["name"], "description": mood["description"],
                     "colors": [{"role": "bg", "use": "background", "hex": c["bg"]},
                                {"role": "ink", "use": "text", "hex": c["ink"]},
                                *({"role": r, "use": use, "hex": c[r]} for r, use in ROLES)],
                     "type": {"display": ty["display"], "body": ty["body"], "mono": ty["mono"]},
                     "motion": f"{m['ease']}, {m['duration']} s, text enters by {m['enter']}"}
    research = list(research_rows)
    return {"source": narration.get("source"), "title": str(spec.get("title", "")),
            "reading": (f"Reading this as: {cell(brief['takeaway']).rstrip('. ')}. "
                        f"For: {cell(brief.get('viewer', '')).rstrip('. ')}." if brief.get("takeaway") else ""),
            "picks": chosen, "direction": direction, "parts": parts,
            "research": {"rows": research, "claims": len(research),
                         "one_source": sum(r["status"] == "one source" for r in research),
                         "no_source": sum(r["status"] == "no source" for r in research)},
            "checks": issues}


def markdown(data):
    out = [f"# {cell(data['title'])}: storyboard", "", HEADER, ""]
    if data["reading"]:
        out += [data["reading"], ""]
    if data["picks"]:
        out += ["## Picks", ""]
        for key, label in CATALOGS:
            p = data["picks"].get(key)
            if not p:
                continue
            out.append(f"**{label}: `{p['chosen']}`**" + (" (chosen in the New video form)" if p["how"] == "form" else ""))
            out += [f"- {'Recommended' if i == 0 else 'Alternative'}: `{o['name']}`: {o['why']}"
                    for i, o in enumerate(p["options"])]
            out.append("")
    if data["direction"]:
        d = data["direction"]
        out += ["## Video direction", "", f"- Moodboard `{d['moodboard']}`: {d['description']}",
                "- Colors: " + ", ".join(f"{c['role']} `{c['hex']}` ({c['use']})" for c in d["colors"]),
                f"- Type: display {d['type']['display']}, body {d['type']['body']}, mono {d['type']['mono']}",
                f"- Motion: {d['motion']}", ""]
    r = data["research"]
    if r["claims"]:
        out += [f"Research: {r['claims']} claim{'' if r['claims'] == 1 else 's'}, {r['one_source']} with one source, "
                f"{r['no_source']} with none (research.md).", ""]
    for part in data["parts"]:
        out += [f"## Part {part['n']}: {cell(part['title'])} ({part['length']:.0f} s)", "",
                "| # | Time | Voice | On screen | Treatment | 2D or 3D | Sources | Frame |",
                "|---|------|-------|-----------|-----------|----------|---------|-------|"]
        for row in part["rows"]:
            frame = f"![{row['n']}]({row['frame']})" if row["frame"] else ""
            out.append(f"| {row['n']} | {row['time']} | {cell(row['voice'])} | {cell(row['show'])} | "
                       f"{row['treatment']} | {row['dim']} | {', '.join(row['sources'])} | {frame} |")
        out.append("")
    if data["checks"]:
        out += ["## Open checks", "", *(f"- {cell(c)}" for c in data["checks"]), ""]
    return "\n".join(out)


def frames(video, spec):
    """{"scene/beat": "frames/<format>/<scene>/<beat>.jpg"} for frames a full 720p render saved (first format wins)."""
    fmt = spec.get("format", "landscape")
    found = {}
    for f in (["landscape", "story"] if fmt == "both" else [fmt]):
        for path in sorted((Path(video) / "frames" / f).glob("*/*.jpg")):
            found.setdefault(f"{path.parent.name}/{path.stem}", str(path.relative_to(video)))
    return found


def refresh(video, spec, narration):
    """Write storyboard.md and build/storyboard.json. Runs in Docker, where the catalogs and research.md are read."""
    from ev import catalog, research
    known = {"video_format": catalog.names("video_format"), "moodboard": catalog.names("moodboard")}
    name = spec.get("moodboard")  # only `moodboard:` loads one; an old `look:` video has no direction block
    mood = catalog.moodboard(name) if name in known["moodboard"] else None
    data = build(spec, narration, mood, known, research.rows(Path(video) / "research.md"), frames(video, spec))
    (Path(video) / "storyboard.md").write_text(markdown(data))
    (Path(video) / "build" / "storyboard.json").write_text(json.dumps(data, indent=1))
    return data
