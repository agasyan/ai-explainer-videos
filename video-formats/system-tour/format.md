---
name: system-tour
description: A repo told as purpose, main parts, one request through it, and how to start, for onboarding to a codebase.
fits: [repo, codebase, service, architecture, onboarding]
acts:
  - name: purpose
    goal: Say the payoff in sentence one, then state the purpose of the repo, the job it does, and for whom.
    beats: [1, 2]
  - name: main-parts
    goal: Name the main parts, five or fewer, each with one job.
    beats: [2, 4]
  - name: one-request
    goal: Follow one request through it, from the entry point to the result, one part per beat.
    beats: [2, 5]
  - name: how-to-start
    goal: Show how to start, with the one command to run and the first file to read.
    beats: [1, 2]
scenes: [4, 7]
ending: The viewer knows where each main part lives, and the next action is to run the start command.
---
## When to use

From the explainer-video skill, step 1, for a repo: "tell it as purpose, main parts, one request through it, how to start".

- A new team member must learn a repo or a service.
- A repo with a clear entry point and one request path that you can follow.
- A repo with more than one main flow becomes one part per flow.
- A story part (60 s or less, about 140 words) uses the low end of each beat range. A landscape part (3 min or less, about 420 words) can use the high end.

## Example arc

Example topic: a URL shortener repo.

1. **purpose**: The service turns a long link into a short link, and sends visitors to the long link.
2. **main-parts**: The web server, the link store, the cache, and the stats worker.
3. **one-request**: A visitor opens a short link. The server reads the cache, then the store, and redirects.
4. **how-to-start**: Run the start command, then read the request handler first.
