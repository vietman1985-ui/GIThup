---
type: wiki
title: Second brain landscape 2026
tags: [second-brain, pkm, ai-memory, survey]
created: 2026-10-06
updated: 2026-10-06
importance: 6
confidence: 0.85
status: active
sources: [[[second-brain-repos-survey-2026-10-06]]]
---

# Second brain landscape 2026

## Summary
"Second brain" on GitHub means two things: (1) Markdown note-taking apps people use as their personal knowledge base, and (2) AI systems that remember for an agent. The durable projects in both groups share three traits: plain files the user owns, a small deterministic core, and an explicit consolidation step. This brain copies all three. [[second-brain-repos-survey-2026-10-06]]

## What the best projects do

- **Capture is frictionless, filing is deferred.** memos (63.5k★) and the inbox pattern in claude-obsidian (15.4k★) separate *capturing* from *organising*; review happens later. → `brain capture` + `/brain:review`. [[second-brain-repos-survey-2026-10-06]]
- **Memory has tiers.** Letta/MemGPT (25k★) keeps a small always-in-context core plus archival storage; Generative Agents score observations by importance and reflect periodically. → `importance` 0–10, core memory (≥ 8 or `#pinned`) injected at session start, the rest retrieved on demand. [[second-brain-repos-survey-2026-10-06]]
- **Facts are mutable with history.** mem0 (66.6k★) decides ADD / UPDATE / DELETE / NOOP per fact; Graphiti (31.5k★) never deletes, it closes an edge's validity interval. → `status: superseded` + `supersedes`/`superseded_by` links; nothing is lost. [[second-brain-repos-survey-2026-10-06]]
- **Knowledge is compiled, not just stored.** Karpathy's LLM-wiki pattern (llm-wiki-agent, claude-obsidian): raw sources are immutable, wiki pages are regenerated from them and every claim cites a source; a lint pass finds broken links and orphans. → `raw/` → `wiki/`, `brain lint`. [[second-brain-repos-survey-2026-10-06]]
- **Hooks make memory automatic.** claude-mem (96.7k★) captures what the agent did and injects it into the next session without the user asking. → SessionStart / UserPromptSubmit / PostToolUse / SessionEnd hooks here do the same with no API call. [[second-brain-repos-survey-2026-10-06]]

## Where they fall short (and what this brain changes)

- Most AI memory layers need an API key and a vector database at runtime (mem0 cloud, Zep, Khoj embeddings). → SQLite FTS5 only; see [[Decision - build on Markdown plus SQLite, no vector DB]].
- Several promising "second brains" died when their company pivoted (Quivr, Reor, Second-Me). → the vault is Markdown that any tool can read; the code is small enough to fork.
- Skill-pack repos (second-brain-os, obsidian-second-brain) rely on the model to remember to search. → recall is injected per prompt by a hook, so the model sees relevant notes before it answers.

## Open questions
- Would a tiny local embedding model (ONNX) be worth the dependency once vaults get large?
- How to share one vault between several agents safely (file locks vs. git).

## Sources
- [[second-brain-repos-survey-2026-10-06]]
