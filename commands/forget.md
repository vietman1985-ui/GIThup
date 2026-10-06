---
description: Retire a memory — archive a note, or supersede it with a corrected one. Nothing is deleted; history stays in the vault.
argument-hint: <note title or path> [— replacement fact]
---

The user wants the second brain to stop using this memory:

> $ARGUMENTS

1. Find the note with `brain_search` / `brain_read` and confirm it is the one meant (quote its title and first line).
2. If the user gave a replacement fact → `brain_remember` the new note with `supersedes: "<old>"` (old note becomes `status: superseded`).
3. If there is no replacement → `brain_set_status {status: "archived"}` so it stops ranking in searches and context.
4. If the note contains sensitive personal data the user wants gone from disk entirely, tell them the exact file path so they can delete it themselves, and offer to remove any links to it; do not delete files yourself.
5. Confirm in one line what changed.
