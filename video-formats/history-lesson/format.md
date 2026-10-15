---
name: history-lesson
description: A history told as then, turning points, what went wrong, the fix, and what it means now, for topics with a lesson for today.
fits: [history, lessons, origins, technology]
acts:
  - name: then
    goal: Say the lesson in sentence one, then show the origin, its date, and the problem that people had then.
    beats: [1, 2]
  - name: turning-points
    goal: Show two or three turning points in date order, each as one change on a timeline.
    beats: [2, 4]
  - name: what-went-wrong
    goal: Show what went wrong and what it cost, with sourced numbers only.
    beats: [1, 3]
  - name: the-fix
    goal: Show the fix, and how it spread.
    beats: [1, 3]
  - name: now
    goal: Show what it means now, as one lesson that the viewer can use today.
    beats: [1, 2]
scenes: [5, 8]
ending: The viewer takes one lesson from the past, and the next action is to look for the same risk in their own work.
---
## When to use

A house format, with no outside source.

- A history topic with a clear lesson for today.
- An origin story where a choice from the past still causes problems now.
- A story part (60 s or less, about 140 words) uses the low end of each beat range. A landscape part (3 min or less, about 420 words) can use the high end.

## Example arc

Example topic: the year 2000 date bug.

1. **then**: Early programs store the year as two digits to save memory.
2. **turning-points**: The programs stay in use for decades, and the year 2000 comes closer.
3. **what-went-wrong**: In old systems, the year 00 can read as 1900, so date math gives wrong results.
4. **the-fix**: Teams find and change date fields, then test each system with dates after 2000.
5. **now**: Signed 32-bit time counters run out in 2038, so check the date types in your code.
