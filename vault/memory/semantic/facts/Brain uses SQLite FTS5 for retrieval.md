---
type: fact
title: Brain uses SQLite FTS5 for retrieval
tags: [brain, search, architecture]
created: 2026-10-06
updated: 2026-10-06
importance: 6
confidence: 0.95
status: active
sources: [[[second-brain-repos-survey-2026-10-06]]]
---

# Brain uses SQLite FTS5 for retrieval

Search is BM25 from SQLite's FTS5 extension (tokenizer `unicode61 remove_diacritics 2`, so "bo nao" matches "bộ não"), multiplied by an importance boost, a recency boost with a 30-day half-life, and a status penalty. No embeddings, no vector database, no API key.

Why: every surveyed system that needed a vector store or a hosted API (mem0 cloud, Zep, Khoj's embedding models) became unusable offline or without a key; FTS5 ships inside Python's `sqlite3` on every platform.

Related: [[Decision - build on Markdown plus SQLite, no vector DB]] · [[GIThup brain project]]
