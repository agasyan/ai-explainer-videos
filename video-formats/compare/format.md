---
name: compare
description: A choice told as the choice, the criteria, each option against the criteria, and the verdict with when the other option wins, for tool and design decisions.
fits: [choices, tools, tradeoffs, decisions]
acts:
  - name: choice
    goal: State the choice and the short verdict in sentence one, then name the options.
    beats: [1, 2]
  - name: criteria
    goal: Name three to five criteria that decide the choice, and why each one matters.
    beats: [1, 3]
  - name: options
    goal: Test each option against the same criteria, in the same order, on one table.
    beats: [2, 6]
  - name: verdict
    goal: Give the verdict, and say when the other option wins.
    beats: [1, 2]
scenes: [3, 6]
ending: The viewer can make the choice with the criteria, and the next action is to score their own case on the same table.
---
## When to use

A house format, with no outside source.

- A decision between two or three options, such as tools, designs, or methods.
- Each option has real strengths, so the verdict depends on the case.
- Keep to three options or fewer, so that the table stays readable on a phone.
- A story part (60 s or less, about 140 words) uses the low end of each beat range. A landscape part (3 min or less, about 420 words) can use the high end.

## Example arc

Example topic: a relational database or a document store for a new app.

1. **choice**: Which store fits a new app? For most apps, pick the relational database.
2. **criteria**: The data shape, the links between records, schema changes, and team skills.
3. **options**: The relational database wins on links and data checks. The document store wins on data with no fixed shape.
4. **verdict**: Pick relational, unless the data has no fixed shape and few links between records.
