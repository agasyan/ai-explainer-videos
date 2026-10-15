---
name: incident-review
description: An incident told as what happened, the timeline, the cause, what changed, and the lesson, for blameless reviews of outages.
fits: [incidents, outages, postmortems, reliability]
acts:
  - name: what-happened
    goal: State the impact in sentence one, with what broke, for how long, and how many requests failed.
    beats: [1, 2]
  - name: timeline
    goal: Show the timeline in order, from the first alert to recovery, with times in 24-hour format.
    beats: [2, 4]
  - name: cause
    goal: Show the cause as systems and conditions, and name no person.
    beats: [1, 3]
  - name: what-changed
    goal: Show what changed after the incident, and which check now stops a repeat.
    beats: [1, 3]
  - name: lesson
    goal: State one lesson that the viewer can use in their own system.
    beats: [1, 2]
scenes: [4, 8]
ending: The viewer knows the cause and the change that stops a repeat, and the next action is to check their own system for the same weak point.
---
## When to use

A house format, with no outside source. It is blameless: name systems, never people.

- An outage, a data error, or a failed release that a team must learn from.
- Use fake values, and put zero customer data or secrets in the video.
- A story part (60 s or less, about 140 words) uses the low end of each beat range. A landscape part (3 min or less, about 420 words) can use the high end.

## Example arc

Example topic: a cache outage.

1. **what-happened**: The cache fails, and page loads slow down for all users until the cache refills.
2. **timeline**: The keys expire, the database overloads, the alert fires, and the cache refills.
3. **cause**: All keys share one expiry time, so every request goes to the database at once.
4. **what-changed**: Keys now expire at random times, and a load test checks the database limit.
5. **lesson**: Plan for the moment when the cache is empty.
