---
type: decision
title: Decision - create the default vault on first use
tags: [architecture, install, brain]
created: 2026-10-06
updated: 2026-10-06
importance: 6
confidence: 0.8
status: active
---

# Decision - create the default vault on first use

Hooks and the MCP server create ~/.brain/vault automatically (Home.md, _schema.md, templates, no example notes) when no vault exists and no BRAIN_VAULT or .brain.toml was set, so a fresh plugin install works with zero setup. An explicit path that is missing is never created: that is the user's call. Reason: every reference plugin that required a manual init step (claude-obsidian, second-brain-os) listed 'forgot to init' as a top support issue.
