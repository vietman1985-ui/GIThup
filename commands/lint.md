---
description: Health check of the second brain — broken links, orphans, duplicates, stale notes, inbox backlog — and fix what is mechanical.
---

Run `brain_lint` on the second brain and act on the report:

- `error` (broken links): fix the link target or create the missing note. Never delete the referring note.
- `warn` (orphans, duplicates, superseded-without-successor): link orphans from a wiki/MOC page or merge; resolve duplicates with UPDATE + SUPERSEDE per the `brain` skill.
- `info` (stale, low-confidence, inbox backlog, raw-uncompiled): list them for the user and offer `/brain:review` or `/brain:compile`.

If there are more than ~10 mechanical fixes, delegate them to the `brain-librarian` agent. Finish with a one-paragraph summary of what changed and what still needs the user's judgement.
