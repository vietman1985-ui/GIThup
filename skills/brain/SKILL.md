---
name: brain
description: The user's second brain — a Markdown vault of episodic logs, semantic memory (facts, entities, decisions, preferences), procedures and a compiled wiki. Use whenever the user asks to remember, recall, note or look up something; asks about past decisions, preferences, people or projects; says "bộ não", "ghi nhớ", "nhớ lại", "ghi chú", "second brain", "memory", "notes"; or when a task would clearly benefit from what the user already knows or decided. Covers how to search, read, store (ADD / UPDATE / SUPERSEDE / NOOP), capture, log, and when to hand work to the brain agents.
---

# Brain — how to use the user's second brain

The brain is a folder of Markdown notes (Obsidian-compatible) plus a SQLite
full-text index. Nothing here needs an API key. You are the intelligence; the
tools are deterministic.

## Tools (prefer MCP, fall back to CLI)

| MCP tool (server `brain`) | CLI equivalent | use it to |
|---|---|---|
| `brain_search {query, k, types, tag}` | `brain search "<q>" -k 8 --type fact` | find notes (BM25 × importance × recency; diacritics-insensitive, so Vietnamese with or without dấu both work) |
| `brain_read {path}` | `brain read "<path or [[title]]>" --meta` | read one note in full, with backlinks and related notes |
| `brain_remember {title, content, type, tags, importance, confidence, sources, supersedes, if_exists}` | `brain remember "<title>" "<body>" --type fact --tags a,b --importance 6` | store durable knowledge (see decision table) |
| `brain_capture {text, title, tags}` | `brain capture "<text>"` | drop something into `inbox/` without deciding where it goes |
| `brain_log {text, kind}` | `brain log "<text>" --kind decision` | append to today's episodic log; `kind=remember` flags a candidate fact |
| `brain_related {path}` | `brain related "<ref>"` | walk the link/tag graph |
| `brain_context {cwd}` | `brain context` | the session-start packet (project notes, core memory, recent activity) |
| `brain_lint` / `brain_packet {days}` | `brain lint` / `brain packet --days 7` | health report / weekly consolidation brief |
| `brain_set_status {path, status}` | `brain status "<ref>" archived` | active · superseded · archived · draft |

If MCP tools are not loaded, use the CLI: `python3 "${CLAUDE_PLUGIN_ROOT}/bin/brain" …`
(inside the GIThup repository itself: `python3 bin/brain …`). `brain where`
prints which vault is in use; the default is `~/.brain/vault`, created on
first use.

## The loop: RECALL → ACT → REMEMBER → LOG

1. **Recall first.** Before answering anything about the user, their projects,
   people, tools or past decisions, run `brain_search` (two phrasings: the
   user's words and your own paraphrase; Vietnamese and English if relevant).
   Read the top hits with `brain_read`. Trust `status: active` notes; treat
   `superseded` notes as history and follow `superseded_by`.
2. **Act** using what you found. Cite notes by path when you rely on them.
3. **Remember** durable outcomes — a decision made, a preference revealed, a
   fact learned, a procedure that worked. One idea per note. Pick the type:
   `fact` · `entity` (person, project, tool) · `decision` · `preference` ·
   `procedure` · `wiki`.
4. **Log** the episode with `brain_log` when something notable happened that
   is not yet a durable fact (`kind=remember` so the weekly review picks it up).
   Hooks already log session start/end and edited files; do not duplicate that.

## Decision table before every `brain_remember` (mem0-style)

| situation | action | how |
|---|---|---|
| nothing similar exists | **ADD** | `if_exists: "new"` or default |
| same subject, more detail or a correction that does not contradict | **UPDATE** | default `if_exists: "update"` — appends an *Update* section, keeps history |
| contradicts an existing note (fact changed, preference reversed) | **SUPERSEDE** | pass `supersedes: "<old title or path>"` — old note keeps its text, gets `status: superseded` + `superseded_by` |
| already known, or trivia nobody will look up | **NOOP** | store nothing (maybe `brain_log`) |

`brain_remember` returns near-duplicate candidates with its result. If it lists
one you did not expect, read it and reconsider UPDATE/SUPERSEDE.

## Importance and confidence

- `importance` 10 = identity-level (who the user is, hard constraints, language);
  8–9 = always relevant (injected at every session start); 5 = normal; ≤ 2 = trivia.
  Be stingy: core memory should stay under ~15 notes.
- `confidence` 0.95 = the user said it directly; 0.7 = inferred from behaviour;
  < 0.5 = guess — mark it `status: draft` instead.
- Add `tags: ["pinned"]` to force a note into the session-start context regardless of importance.

## Rules of the vault

- Titles are the identity of a note (`[[Title]]`). Write them as a reader
  would search: "Decision - use SQLite not a vector DB", "Minh (frontend lead)".
- Vietnamese titles and bodies are fine; keep code identifiers and paths as-is.
- Never edit files under `raw/`. Knowledge extracted from them goes to `wiki/`
  and cites the source with `[[raw note]]`.
- Never delete notes to "clean up" — archive (`status: archived`) or supersede.
- Episodic logs are append-only.
- The vault layout and frontmatter are documented in the vault's `_schema.md`.

## When to delegate

- Weekly review, inbox filing, dedup → `brain-consolidator` agent (or `/brain:review`).
- Fix broken links, orphans, tags → `brain-librarian` agent (cheap, mechanical).
- Turn a `raw/` source into a wiki page → `brain-researcher` agent (or `/brain:compile`).
- Challenge core memory for contradictions and stale facts → `brain-critic` agent.
