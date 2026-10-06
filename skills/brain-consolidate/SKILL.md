---
name: brain-consolidate
description: The consolidation loop (hippocampus → cortex) for the second brain — turning the inbox and episodic logs into durable semantic notes, deduplicating, superseding contradictions, re-scoring importance, and fixing lint. Use for the weekly review (/brain:review), when the inbox has a backlog, or when the user says "dọn dẹp bộ não", "tổng hợp ghi chú", "consolidate memory".
user-invocable: false
---

# Brain consolidation

Run this weekly (10–15 min of model time), or whenever `brain_lint` reports
an inbox backlog. Work from the packet; never from memory of the chat.

## Steps

1. **Get the brief:** `brain_packet {days: 7}` (CLI: `brain packet --days 7`).
   It lists recent episodes, inbox items, `[remember]` candidates, duplicates,
   stale and low-confidence notes, and the decision table.
2. **Process every inbox item** (`brain_read` each):
   - Decide ADD / UPDATE / SUPERSEDE / NOOP (table below).
   - Write the semantic note with `brain_remember` — type, tags, importance,
     confidence, `sources` (the inbox item's `source` and any URLs).
   - Then archive the inbox item: `brain_set_status {path, status: "archived"}`.
3. **Process every `[remember]` line** from the episodic log the same way.
   Facts about *the user* (preferences, constraints, identity) get importance ≥ 7.
4. **Resolve duplicates:** for each pair, keep the better-titled note, move
   unique content into it (UPDATE), supersede the other.
5. **Re-verify stale / low-confidence notes:** read them; if still true bump
   `updated` via a one-line UPDATE; if doubtful lower `confidence` or set
   `status: draft`; if obsolete `archived`.
6. **Re-score core memory:** list `importance ≥ 8` notes (`brain_list`). Core
   memory must stay small (≈ 15 notes). Demote what is not needed every session.
7. **Lint:** `brain_lint`. Fix every `error` (broken links), then `warn`
   (orphans — link them from a wiki/MOC page or merge them). Delegate to
   `brain-librarian` if there are many.
8. **Compile:** every `raw-uncompiled` source → `/brain:compile` (or the
   `brain-researcher` agent).
9. **Close:** `brain_log {text: "weekly review: N inbox filed, M superseded, …", kind: "review"}`.
   Report the summary to the user in their language, with the list of notes
   created/updated/superseded.

## Decision table

| situation | action |
|---|---|
| genuinely new | **ADD** (`if_exists: "new"`) |
| same subject, more detail | **UPDATE** (default) |
| contradicts an active note | **SUPERSEDE** (`supersedes: "<old>"`) — never silently overwrite |
| already captured / trivia | **NOOP**, archive the inbox item |

## Quality bar for a semantic note

- Title reads like a search query; one idea; 1–5 sentences.
- States *why it matters* or *when it applies* if not obvious.
- Links to at least one related note (`[[…]]`) so it is not an orphan.
- Has `sources` when it came from a document or conversation worth tracing.
