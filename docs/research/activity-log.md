# Research: a readable activity log

Gathered 2026-11-18 by a researcher agent, each source opened on the web. It shaped the dashboard's Activity tab ([dashboard.md](../dashboard.md)).

| id | claim | source 1 | source 2 | status |
|---|---|---|---|---|
| G1 | Group events into named steps with expandable sections | https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands | https://github.blog/engineering/how-github-actions-renders-large-scale-logs | confirmed |
| G2 | Step headers carry status and duration | https://docs.github.com/en/actions/how-tos/monitor-workflows/use-workflow-run-logs | https://octopus.com/blog/task-log | confirmed |
| G3 | Open the failed step automatically and keep the rest folded | https://docs.github.com/en/actions/how-tos/monitor-workflows/use-workflow-run-logs | https://buildkite.com/docs/pipelines/configure/managing-log-output | confirmed |
| G4 | A short list first, detail on request, two levels at most | https://www.nngroup.com/articles/progressive-disclosure/ | https://pair.withgoogle.com/chapter/explainability-trust/ | confirmed |
| G5 | Use the user's language: no jargon or codes | https://www.nngroup.com/articles/ten-usability-heuristics/ | https://www.nngroup.com/articles/error-message-guidelines/ | confirmed (one publisher) |
| G6 | Fold tool calls into one-line summaries, detail one click away | https://code.claude.com/docs/en/interactive-mode | https://docs.devin.ai/work-with-devin/devin-session-tools | confirmed |
| G8 | A current-activity line that names the item in progress | https://www.nngroup.com/articles/response-times-3-important-limits/ | https://octopus.com/blog/task-log | confirmed |
| G9 | Errors in color plus text or an icon, never color alone | https://vercel.com/docs/deployments/logs | https://www.nngroup.com/articles/error-message-guidelines/ | confirmed |
| G10 | Explain each error in plain words, with a next step | https://www.nngroup.com/articles/error-message-guidelines/ | https://docs.netlify.com/deploy/deploy-overview/ | confirmed |
| G11 | Offer search and failed-only views | https://docs.github.com/en/actions/how-tos/monitor-workflows/use-workflow-run-logs | https://github.blog/2020-09-23-a-better-logs-experience-with-github-actions/ | confirmed |
| G12 | A focus view: the prompt, a one-line tool summary, the answer | https://code.claude.com/docs/en/fullscreen | (none) | one source |
| G13 | A view per sub-agent | https://code.claude.com/docs/en/sub-agents | (none) | one source |
| G14 | Per-line timestamps behind a toggle, not by default | https://octopus.com/blog/task-log | https://buildkite.com/docs/pipelines/configure/managing-log-output | confirmed |
| G15 | Stop auto-follow when the user scrolls up; a jump button counts new lines | https://code.claude.com/docs/en/fullscreen | https://issues.jenkins.io/browse/JENKINS-44167 | confirmed (one is a complaint) |

## How the Activity tab follows it

- Each run chip says what the run is for: `[Intent]`, `[Plan + preview]`, `[Change]`, `[Render 720p]` (G1, G2).
- Each thing Claude says opens a step; the actions after it fold into one line, "4 actions: Read intent.md" (G1, G6).
- Actions read as plain verbs with short paths: "Read intent.md", "Run make narrate SLUG=x", "Read web page: host/path" (G5).
- Problems stay open, red, with a mark and a plain reason: "Not allowed: Bash. A dashboard job may use only its listed commands and files, so Claude tries another way. Nothing to do." (G3, G9, G10).
- Filters: Everything, What Claude says, Problems; and Show its steps per agent (G11, G12, G13).
- While you read higher up, the log stays still, and "N new lines: jump to the end" brings you back (G15).
- The status line above the tabs names what Claude does now, with the time (G8).
