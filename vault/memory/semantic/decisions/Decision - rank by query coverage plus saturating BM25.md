---
type: decision
title: Decision - rank by query coverage plus saturating BM25
tags: [architecture, search, brain]
created: 2026-10-06
updated: 2026-10-06
importance: 7
confidence: 0.8
status: active
sources: ["[[Brain uses SQLite FTS5 for retrieval]]"]
---

# Decision - rank by query coverage plus saturating BM25

FTS5's bm25() goes positive (negative IDF) when a term appears in more than half the notes, which made every hit score ~0 on a 2,000-note test vault and silenced per-prompt recall. Score = 1 + 4·coverage + 3·bm25/(bm25+5), then × importance × recency × status. Coverage counts query tokens found in the title (weight 2) and body (weight 1), diacritics-insensitive, after removing Vietnamese and English stopwords. Hooks inject a note only if score ≥ recall_min_score (3.5) and it has a title match or two body matches. Revisit when: a real vault shows paraphrased facts being missed in the weekly review.
