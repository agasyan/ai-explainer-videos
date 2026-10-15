---
name: problem-fix
description: A PR told as problem, change, effect, and risk, for code reviews and release notes.
fits: [pr, bugfix, feature, refactor, review]
acts:
  - name: problem
    goal: Say the payoff in sentence one, then state the problem that the PR solves and who it affects.
    beats: [1, 3]
  - name: change
    goal: Show the change as one before and one after, in plain words, with code in show only.
    beats: [1, 4]
  - name: effect
    goal: Show the effect of the change with one real number or one visible result.
    beats: [1, 3]
  - name: risk
    goal: Name the risk that stays, and how the team detects it or rolls the change back.
    beats: [1, 2]
scenes: [3, 6]
ending: The viewer knows what the PR fixes and what to watch, and the next action is to review the diff.
---
## When to use

From the explainer-video skill, step 1, for a PR: "tell it as problem, change, effect, risk".

- A pull request that fixes a bug, adds a feature, or changes behavior.
- A change that a team must review or understand before it ships.
- A large PR with more than one main idea becomes more than one part, one idea per part.
- A story part (60 s or less, about 140 words) uses the low end of each beat range. A landscape part (3 min or less, about 420 words) can use the high end.

## Example arc

Example topic: a PR that adds retries with backoff to an HTTP client.

1. **problem**: Short network errors make some requests fail, and the user sees an error page.
2. **change**: The client now retries up to three times, and waits longer before each retry.
3. **effect**: Fewer requests fail, and the error graph drops after the release.
4. **risk**: Retries add load to a slow server, so a retry cap and an alert limit the damage.
