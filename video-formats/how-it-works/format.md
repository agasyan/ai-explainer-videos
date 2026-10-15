---
name: how-it-works
description: A mechanism told as the question, the parts, one flow through the parts, and the limits, for technology and science topics.
fits: [technology, science, protocols, machines]
acts:
  - name: question
    goal: Ask the question and give the short answer in sentence one.
    beats: [1, 2]
  - name: parts
    goal: Name the parts, five or fewer, each with one job.
    beats: [1, 4]
  - name: flow
    goal: Follow one flow through the parts in order, one step per beat, with the step count on screen.
    beats: [2, 6]
  - name: limits
    goal: Show where the mechanism stops working, and what happens then.
    beats: [1, 2]
scenes: [4, 7]
ending: The viewer can trace the flow without help, and the next action is to see the same flow in a real tool or log.
---
## When to use

A house format, with no outside source.

- A topic that asks how a machine, a protocol, or a process works.
- A topic with a small set of parts and one main path through them.
- A topic with two or more main paths becomes one part per path.
- A story part (60 s or less, about 140 words) uses the low end of each beat range. A landscape part (3 min or less, about 420 words) can use the high end.

## Example arc

Example topic: how DNS works.

1. **question**: How does a browser find a website? It asks DNS for the IP address of the name.
2. **parts**: The browser, the resolver, the root server, the TLD server, and the name server for the domain.
3. **flow**: The resolver asks each server in turn, gets the IP address, and stores it in a cache.
4. **limits**: A cached answer can be out of date, so a change takes time to reach every user.
