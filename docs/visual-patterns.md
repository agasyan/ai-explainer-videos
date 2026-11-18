# Visual patterns

Which picture fits which content, in a 1 to 5 minute narrated explainer. Scene agents pick one pattern per beat from this page; each has a starter scene in `templates/patterns/` (beats `a`, `b`, `c`; copy it, then change the beat ids, words, and numbers). The evidence is in [research/visual-patterns.md](research/visual-patterns.md), with two sources per claim.

## Story shape for a decision

A video has no reader-driven middle, so tell a decision as a fixed slideshow that opens with the answer (P1 to P4):

```
verdict -> options side by side -> evidence for each criterion (zoom into the source) -> verdict again + the ask
```

This fits the `compare` and `problem-fix` video formats. The first scene names the parts before anything moves (L7).

## Content to pattern

| Content | Pattern | What the scene shows | Motion | Starter | Evidence |
|---|---|---|---|---|---|
| The verdict (open or close) | Verdict card | One-sentence verdict, a tag on the chosen option | The headline appears, then the tag pops in | `verdict-card.html` | P3, P4 |
| One key number | Big number | A large number, its unit, and a 3 to 6 word label | Counts up, then holds | `big-number.html` | P5 |
| 2 to 4 options | Option bars | Bars on one shared axis, values on top | All bars grow at once, then the losers dim | `option-bars.html` | P6, P10, P15 |
| A ranking | Ordered bars | Bars sorted by value | Bars grow in rank order, then rank 1 lights up | `ordered-bars.html` | P6, P13 |
| Change over time | Annotated line | 1 to 3 lines, a note at the turning point | The line draws left to right with the voice, then a dot and a note | `annotated-line.html` | P6, P12, P13 |
| Part of a whole | Stacked bar | One 100% bar, or a waterfall | Parts fill in order, then the key part brightens | `stacked-bar.html` | P6, P15 |
| A process | Step flow | 3 to 6 boxes joined by arrows | One step per beat, its arrow drawn as the voice names it | `step-flow.html` | P8, P13 |
| Before and after | Dumbbell | Each item's dot on a track | The same dot slides from before to after, all at once | `before-after.html` | P7, P10 |
| A rule or condition | Decision diamond | The condition, a yes and a no branch | The condition first, then the branch it takes lights up | `decision-diamond.html` | P8, P15 |
| Exact results | Progressive table | 5 rows by 4 columns at most | Header, then rows in story order, then the winner is colored | `progressive-table.html` | P9, P13, P15 |
| A part of the source page | Zoom into the evidence | The real page part; the camera zooms to one region, a box marks it | Zoom from the whole part to the region, then hold while the voice quotes it | `zoom-evidence.html` | P15 to P18 |
| Layers, a stack, depth | 3D layers | Slabs in 3D, labels in HTML beside them | The stack turns slowly, then the layers spread apart | `layers-3d.html` | house rule |
| A change of view | Morph | The same marks rearranged into the next chart | One move, all marks together, no stagger | (build from option bars) | P10, P11 |

## Scene rules

1. **Signal one thing.** Highlight or pulse only the element the voice names, when it names it, then let it go (L2, P15).
2. **Cut the rest.** Leave out any element, decoration, or fact the narration does not need (L1).
3. **Label on the shape.** Put each label inside or next to what it names: no legends, no far callouts (L4).
4. **Sync to the word.** Start each change with `EV.at(beat, "word")` on the word that names it (L5, P14).
5. **Do not repeat the narration on screen.** Show short labels; the captions carry the sentences (L3).
6. **Name the parts first.** The first scene shows the parts or terms before the process runs (L7).
7. **One idea per scene,** with a clear break between scenes (L6).
8. **Move the same mark.** When a value changes, move or morph the mark the viewer already sees, all at once (P10, P11).
9. **Build in story order:** axes first, then data in the order the voice tells it, then the highlight (P13).
10. **A new picture every few seconds.** A scene rarely holds longer than about 30 s without a new beat (an inference from L13 and L14, not a measured figure).
11. **Captions:** 2 lines at most (L9). EV's caption widths (28 characters a line for `pop`, 42 for `line`) and the voice's pace keep them readable.

## 3D, as an infographic

Use three.js where depth carries meaning: layers of a system, a stack, a flow through stages, a structure seen from an angle. Values the viewer compares stay 2D marks or labels, because perspective changes their apparent size (a house rule, not from the research). The rules in [scenes.md](scenes.md#3d) still apply: `three: true`, a `three_why` per scene, a moodboard with the `stage-3d` treatment, and 2 scenes with 3D per part at most.

## From an HTML page

A page is a source: retell its point with these patterns, in the video format's acts, never in the page's order. `make from-html` makes `scenes/page-<id>.html` for each section; use one only where a beat needs the evidence, with `p.zoom` and `p.mark` ([scenes.md](scenes.md#page-sections)). A full page tour, every page scene in order, is only for a request that asks for one.
