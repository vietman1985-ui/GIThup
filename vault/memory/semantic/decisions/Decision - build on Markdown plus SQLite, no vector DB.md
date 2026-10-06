---
type: decision
title: Decision - build on Markdown plus SQLite, no vector DB
tags: [decision, architecture, brain]
created: 2026-10-06
updated: 2026-10-06
importance: 8
confidence: 0.9
status: active
sources: [[[second-brain-repos-survey-2026-10-06]]]
---

# Decision - build on Markdown plus SQLite, no vector DB

**Context:** 282 "second brain" repositories were surveyed on 2026-10-06 (see [[Second brain landscape 2026]]). The ones that stayed usable for years were plain-Markdown vaults (Obsidian ecosystem, Logseq, Foam); the ones that died or pivoted depended on a hosted vector DB, an embedding API or a single vendor (Reor archived, Second-Me dormant, Quivr pivoted).

**Decision:** store everything as Obsidian-compatible Markdown; index with SQLite FTS5; let Claude Code be the intelligence through skills, subagents and hooks; expose the same operations over MCP for other clients.

**Alternatives considered:**
- mem0 / Letta as the memory layer — powerful but needs an LLM API key and a vector store at runtime.
- Embedding-based retrieval — better recall on paraphrases, but adds a dependency and an API cost per note.

**Consequences:** works offline, zero install beyond Python; retrieval is lexical (diacritics-insensitive) so good tags and titles matter; semantic similarity is delegated to the model reading the top-k hits.

**Revisit when:** the vault exceeds ~20k notes or lexical search demonstrably misses paraphrased facts in the weekly review.

Related: [[Brain uses SQLite FTS5 for retrieval]] · [[GIThup brain project]]
