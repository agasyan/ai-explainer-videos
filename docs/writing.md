# Writing rules

These rules make a video easy to follow on the first watch. The agent applies them; use them when you edit a script by hand.

## Beats: say and show

Each beat in `script.yaml` has two lines:

- `say`: what the voice reads, 1 to 2 sentences.
- `show`: what the screen shows meanwhile, in concrete nouns and motion. Example: "A browser bar types example.com. An arrow runs to a box labelled DNS."

One beat is one visual change. The preview check compares each frame with its `show` line. `make narrate` turns the beats into `storyboard.md`: one row per beat with its time, voice, picture, treatment, and sources. Edit `script.yaml`, never `storyboard.md`.

## Research: every fact has a source

For a topic, the agent writes `research.md` before the script: one table, one row per claim.

| id | claim | source 1 | source 2 | status |
|----|-------|----------|----------|--------|
| c1 | 18 June 1914: Lawrence Sperry flew hands-off near Paris | [NASM](https://airandspace.si.edu/air-and-space-quarterly/issue-12/secret-history-of-drones) | [FAA](https://www.esc.gov/monroneynews/archive/Vol_5/TG/05_3.asp) | two sources |

1. Open every source you cite. Take each number and date from the page, never from memory.
2. A claim is checked when two independent sources agree; with one, its status is `one source`.
3. Each beat that states a fact lists its claims: `sources: [c1]`.
4. `make narrate` prints `CHECK` for a beat that cites an unknown claim, or states a number with no source.
5. Approving the preview (or an early plan check) approves `research.md`: the plan hash covers it.
6. A page that does not load is not a source. Write `not opened` and the reason in its cell: `https://... (not opened: 403)`. The link then does not count.
7. Say a number from a claim with one source as an estimate: "about", or "one study found". Keep a plain statement for a claim with two sources.

## Narration: about 80% of the way to ASD-STE100

ASD-STE100 is the controlled English of aircraft maintenance manuals. The full spec is strict, so aim for 80%.

1. One idea per sentence. 20 words or fewer; aim for 12.
2. Active voice, present tense: "The cache stores the result."
3. One word, one meaning. If you say "request", never switch to "call".
4. Ordinary words: "use", "start", "help". Not "utilize", "initiate", "facilitate".
5. Keep articles and verbs. Write full sentences, not telegram style.

## Structure: ADHD-friendly

Adapted from [i-have-adhd](https://github.com/ayghri/i-have-adhd) for video.

1. **Payoff first.** Sentence one says what the viewer gets. No greeting, no intro.
2. **One idea per beat.** One visual change per sentence.
3. **Visible progress.** Show "Step 2 of 4" or "Part 2 of 3" on screen.
4. **Concrete and capped.** Real numbers ("from 1.2 s to 300 ms"), not "much faster". Five items or fewer in any list on screen.
5. **End with the win and one next action.** No "thanks for watching".

## Skim: a viewer who scrubs still gets the point

Many viewers do not watch from start to end: they scrub, watch with the sound off, or look at one frame. Research: [L15 to L17](research/visual-patterns.md).

1. **Start from the viewer's questions.** `intent.md` lists up to 3 questions these viewers ask, each with its answer in 1 to 4 words, and `brief.questions` in `script.yaml` carries them. The video answers each one; the first beat answers the first.
2. **Answer first.** The first beat states the key message itself. "Checkout fails for two percent of users, and one timeout causes it", not "In one minute, you will know why checkout fails".
3. **A title per scene.** Give each scene a `title:` in `script.yaml`: its point as a short sentence, 8 words or fewer. "One timeout causes the failures", not "Root cause". Show the same words on screen in that scene.
4. **Chapters.** Each scene is a chapter mark in the MP4, named by its `title:`, so a viewer can jump. `out/<name>.chapters.txt` lists them as `0:00 Title` lines for a video description.
5. **Show what a person sees, then the system.** When the topic changes what a user or an operator sees, the scene after the hook shows that as one example. The parts and the mechanism come after it.
6. **The last frame is the takeaway.** It reads alone as a screenshot: the key message and one next action.
7. **Captions as a subtitle.** `captions: line` (the default) shows the whole sentence in 1 or 2 lines, and the said word lights up. A viewer with the sound off reads at their own speed. `captions: pop` shows one word at a time, which fits a short story clip and costs more eye movement.
8. **The skim test.** Read only the Skim part at the top of `storyboard.md` (the key message, the questions, the scene titles), then the contact sheets. They must give the key message and the reasons. If they do not, fix the titles and the pictures, not the narration.
9. **A fresh viewer checks it.** Before the preview approval, one reviewer gets only the contact sheets and the subtitle file, with the questions but not their answers. It states the key message and answers each question. A wrong or missing answer is a finding to fix.

## Write for the voice

- Spell out what the voice reads: "two percent", "x squared", "version three point two".
- Write acronyms as spoken: "A P I", "sequel". `make narrate` flags words the voice gets wrong.
- Put code and URLs in `show`, never in `say`. Say "the retry function"; show `retryWithBackoff()`.
- Wrap 1 to 2 key words per beat in `*asterisks*`: "Checkout fails for *two percent* of users." The voice ignores them, and the captions show them in the key color.
- About 140 words per minute at speed 1.0 ⚠️ estimate. `make narrate` prints the real length.

## On screen

- 8 words or fewer per text block; 2 blocks or fewer at once.
- Font size 28 px or more, so it reads on a phone.
- Same color, same concept, for the whole video.
- The screen shows keywords; the voice says the sentence.

## Retell a source, never replay it

A page, a doc, a PR, or a recording is a source. Retell its point in the video format's acts, in the order that makes the point clear, not in the source's order. Say less about each part of a long source; one idea per beat. Show pictures from [visual-patterns.md](visual-patterns.md), and show the source itself only as evidence for a beat.

## Long topics: multi-part videos

A video is one part by default: a long source gets less said about each part of it, not a split. Pick its length instead: `< 1 min`, `1-3 min` (the default), or `3-5 min` (`--length under-1m|1-3m|3-5m` in Claude Code). Split only when you ask for a length per part (`--parts 60s`). Then each part stays under that length and the limits below, and the plan names the parts.

| Format | One part, at most |
|--------|-------------------|
| `story` | 60 s, about 140 words |
| `landscape` | 3 min, about 420 words |

Each part:

1. Opens with one sentence of context: "Part 2 of 3. Part 1 showed why checkout failed."
2. Teaches one core idea.
3. Ends with a bridge ("Next: the fix"), or with the recap and next action in the last part.
4. Makes sense alone.

In `script.yaml`, replace `scenes:` with `parts:`:

```yaml
parts:
  - title: The problem
    scenes:
      - id: problem             # scenes/problem.html
        beats:
          - id: hook
            say: Two percent of payments failed last week. In this part, you see why.
            show: A payment counter ticks up. Red marks appear on 2 of 100 cards.
  - title: The fix
    scenes:
      - id: fix
        beats:
          - id: context
            say: Part 2 of 2. Part 1 showed the timeout. Now, the fix.
            show: A Part 2 of 2 badge, then a clock icon crossed out.
```

Output: `out/<slug>-part1-story-720p.mp4`, `out/<slug>-part2-story-720p.mp4`, and so on (and `-1080p` when you render it). Scene ids must be unique across all parts. One approval covers all parts.
