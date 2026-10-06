---
description: Store a durable fact, decision, preference, entity or procedure in the second brain (ADD / UPDATE / SUPERSEDE after checking for duplicates).
argument-hint: <what to remember>
---

Store this in the user's second brain, following the `brain` skill:

> $ARGUMENTS

1. Search first (`brain_search`) for existing notes on the same subject.
2. Decide: ADD (new), UPDATE (more detail), SUPERSEDE (contradiction → pass `supersedes`), or NOOP (already known — tell the user).
3. Choose `type` (fact · entity · decision · preference · procedure), a title that reads like a search query, 1–3 tags, `importance` (10 identity, 8–9 always relevant, 5 normal, ≤2 trivia) and `confidence` (0.95 if the user stated it directly).
4. Call `brain_remember`. If it reports near-duplicates you did not expect, read them and reconsider.
5. Reply in one or two lines: the action taken, the note path, and the importance you chose. Ask only if the fact is ambiguous.
