---
type: entity
title: GIThup brain project
tags: [project, brain, claude-code, pinned]
created: 2026-10-06
updated: 2026-10-06
importance: 8
confidence: 0.9
status: active
aliases: [GIThup, brain]
---

# GIThup brain project

**What it is:** the repository `vietman1985-ui/GIThup` — a plain-Markdown second brain that Claude Code uses through a plugin (skills, commands, agents, hooks) and an MCP server. Development branch: `claude/server-work-sj4s9x`.

## Facts
- Zero third-party dependencies: Python ≥ 3.8 standard library only. See [[Brain uses SQLite FTS5 for retrieval]].
- The vault lives in `vault/` (configured by `.brain.toml`); the index cache lives in `vault/.brain/` and is git-ignored.
- Architecture choice recorded in [[Decision - build on Markdown plus SQLite, no vector DB]].

## Relations
- borrows ideas from the projects surveyed in [[Second brain landscape 2026]]
- maintained with [[How to run a weekly brain review]]

## Open questions
- Should episodic logs be committed to git by default, or kept local?
