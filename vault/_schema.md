---
type: moc
title: _schema
created: 2026-10-06
updated: 2026-10-06
importance: 9
tags: [schema, pinned]
---

# Note schema

Every note is Markdown with YAML frontmatter. Only these keys matter to the
tooling; add anything else you like.

| key | values | meaning |
|---|---|---|
| `type` | `fact` · `entity` · `decision` · `preference` · `procedure` · `wiki` · `raw` · `episode` · `inbox` · `moc` | What kind of note. Folders imply a default type, frontmatter overrides it. |
| `title` | text | Display title (defaults to the first `# heading`, then the filename). |
| `tags` | `[a, b]` | Topic tags; `pinned` forces the note into the session-start context. |
| `created` / `updated` | `YYYY-MM-DD` | Drive recency ranking and the *stale* lint. |
| `importance` | 0–10 | 10 = identity-level (who the user is, hard constraints); 8+ is injected at session start; 5 = normal; 1 = trivia. |
| `confidence` | 0.0–1.0 | How sure we are. < 0.5 is flagged by lint; the critic agent re-verifies. |
| `status` | `active` · `superseded` · `archived` · `draft` | Only `active`/`draft` rank normally. `superseded` keeps history but ranks half as high. |
| `supersedes` / `superseded_by` | `[[Note]]` | Temporal chain (borrowed from Graphiti's valid/invalid edges). |
| `sources` | `[raw/x.md, https://…]` | Where this came from. Wiki pages must cite `raw/` sources. |

## Memory tiers

- **Episodic** (`memory/episodic/`): append-only, one file per day, lines `- HH:MM [kind] text`. Written by hooks automatically; `[remember]` lines are candidate facts.
- **Semantic** (`memory/semantic/`): atomic notes. One idea per note. Written by `brain remember` / `brain_remember`.
- **Procedural** (`memory/procedural/`): how-tos the brain learned; written like a checklist.
- **Wiki** (`wiki/`): compiled from `raw/`, every claim cites its source. Rebuilt by `/brain:compile`.

## Consolidation decision table (mem0-style)

| situation | action | command |
|---|---|---|
| new information, nothing similar | **ADD** | `brain remember "Title" "body" --if-exists new` |
| same subject, more detail | **UPDATE** | `brain remember "Title" "body"` (appends an *Update* section) |
| contradicts an existing note | **SUPERSEDE** | `brain remember "New title" "body" --supersedes "Old title"` |
| already known / trivial | **NOOP** | nothing; `brain archive <inbox item>` |
