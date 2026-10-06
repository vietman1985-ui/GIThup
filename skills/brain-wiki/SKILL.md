---
name: brain-wiki
description: Compile knowledge pages (LLM-wiki pattern) in the second brain — turning immutable sources in raw/ into cited, cross-linked wiki pages, updating maps of content, and keeping the wiki lint-clean. Use for /brain:compile, when a new document/article/transcript is added to the vault, or when the user says "tổng hợp tài liệu", "viết trang wiki", "compile this source".
---

# Brain wiki compilation

Pattern (Karpathy's LLM-wiki, as used by claude-obsidian and llm-wiki-agent):
`raw/` is immutable evidence; `wiki/` is the synthesis; every claim cites its
evidence; a lint pass keeps the graph connected.

## Adding a source

1. Put the material in `raw/<descriptive-name>.md` with frontmatter
   `type: raw`, `title`, `created`, `source: <URL or origin>`. Paste text as-is
   (convert PDFs/HTML to Markdown first; do not summarise here).
2. Never edit a raw file afterwards. If the source changes, add a new raw note
   and supersede the old wiki claims.

## Compiling

1. `brain_read` the raw note. Identify 3–8 claims worth keeping, and any
   entities (people, tools, projects) that deserve their own `entity` notes.
2. Search first (`brain_search`) for existing wiki pages on the topic — extend
   them (UPDATE) instead of creating near-duplicates.
3. Write or update the wiki page with `brain_remember {type: "wiki", sources: ["[[raw note]]"]}`:
   - **Summary** — 2–3 sentences a newcomer can act on.
   - **Details** — each paragraph or bullet ends with its citation `[[raw note]]` or a URL.
   - **Open questions** — what the source does not settle.
   - **Sources** — the list of `[[raw/…]]` links (this is what makes the raw
     note "compiled" for lint).
4. Create `entity`/`fact` notes for things that will be asked about on their
   own; link them from the wiki page.
5. Link the page from a map of content (`Home.md` or a topic MOC) so it is not
   an orphan. Edit the MOC file directly.
6. `brain_lint` — fix anything you introduced.
7. `brain_log {text: "compiled <raw> → <wiki>", kind: "wiki"}`.

## Style

- Write in the user's language; keep technical terms, names and code as-is.
- Prefer concrete numbers, dates and names over adjectives.
- Mark disagreement between sources explicitly rather than averaging it away.
