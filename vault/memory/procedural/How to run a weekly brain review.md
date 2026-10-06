---
type: procedure
title: How to run a weekly brain review
tags: [procedure, review, consolidation, brain]
created: 2026-10-06
updated: 2026-10-06
importance: 7
confidence: 0.9
status: active
---

# How to run a weekly brain review

The consolidation loop (hippocampus → cortex). Run `/brain:review` in Claude Code, or follow by hand:

1. `brain packet --days 7` — read the consolidation packet: episodes, inbox, candidate facts, duplicates, stale notes.
2. For every inbox item and every `[remember]` line, apply the decision table in [[_schema]]: **ADD / UPDATE / SUPERSEDE / NOOP**.
3. `brain lint` — fix broken links first (errors), then orphans (warn), then stale/low-confidence (info).
4. For each `raw/` source without a citing wiki page, run `/brain:compile <source>`.
5. Re-read notes with importance ≥ 8: still true? still that important? Adjust `importance`, `confidence`, `updated`.
6. Finish by appending one `[review]` line to today's episodic log with what changed.

Takes 10–15 minutes for a week of normal use. Delegate steps 2 and 4 to the `brain-consolidator` and `brain-researcher` agents; step 5 to `brain-critic`.

Related: [[Home]] · [[GIThup brain project]]
