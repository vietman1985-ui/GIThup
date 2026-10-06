---
description: Show the second brain's state — vault location, note counts, core memory, inbox backlog, recent activity.
---

Give the user a short status of their second brain:

1. `brain_stats` — vault path, note counts by type, links, tags.
2. `brain_list {types: ["preference","entity","fact","decision","procedure"], limit: 15}` — show the notes with importance ≥ 8 (core memory) as a compact list.
3. `brain_lint` — mention only the counts per level and whether there is an inbox backlog.
4. `brain_context` — summarise the "Recent activity" section in one or two lines.

Reply in the user's language, in at most ~15 lines, and suggest the single most useful next action (`/brain:review`, `/brain:compile`, or nothing).
