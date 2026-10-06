---
name: brain-recall
description: Retrieval procedure for the second brain — how to turn a question into searches, read and cross-check notes, respect supersession, and answer with citations and confidence. Use when the user asks "do I/we know…", "what did I decide…", "nhớ lại", "tìm trong ghi chú", "what do my notes say", or when /brain:recall is invoked.
---

# Brain recall

Goal: answer from the vault, say exactly where the answer came from, and be
honest when the vault does not know.

## Procedure

1. **Decompose the question** into 2–4 search strings: the user's own words,
   a paraphrase, the likely note title, and the key entity names. Search in
   both Vietnamese and English when the vault is bilingual.
2. **Search** each with `brain_search` (k = 5–8). Narrow with `types` when the
   question is clearly about a decision / person / procedure. Use `tag` when a
   project tag is known.
3. **Read** the top 2–4 distinct notes with `brain_read`. Then walk one hop:
   backlinks and *Related* lines often hold the actual answer.
4. **Check validity.** Skip `status: archived`. For `superseded` notes follow
   `superseded_by` and answer from the successor; mention the change if the
   history matters ("you switched from X to Y on 2026-03-02").
5. **Answer** in the user's language. End with a short *Sources* line listing
   note paths. State confidence when a note's `confidence` < 0.8 or when you
   had to infer across notes.
6. **If nothing relevant exists**, say so plainly, then offer to capture the
   answer once the user provides it (`brain_capture` or `brain_remember`).
7. **Log** a `[recall]` line only when the lookup itself is worth remembering
   (e.g. it exposed a contradiction) — not for routine lookups.

## Query tips

- FTS matches word prefixes of 3+ letters: "quyết" finds "quyết định".
- Diacritics are ignored: "bo nao" finds "bộ não".
- Numbers and short tokens match exactly; include them when they are the key
  (ticket numbers, versions, dates).
- Episodic logs are down-weighted; pass `types: ["episode"]` to search them on purpose
  ("what did we do last Tuesday?").
