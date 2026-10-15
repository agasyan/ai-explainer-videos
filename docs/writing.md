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
5. Approving the plan approves `research.md`: the plan check covers it.

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

## Long topics: multi-part videos

Split when a part runs over the limit, or when the topic has more than one main idea. The plan names the parts, so you approve the split before any picture exists.

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

Output: `out/<slug>-part1-story-1080p.mp4`, `out/<slug>-part2-story-1080p.mp4`, and so on. Scene ids must be unique across all parts. One approval covers all parts.
