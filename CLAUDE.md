# GIThup — Brain (second brain for Claude Code)

A plain-Markdown second brain Claude Code uses through a plugin (skills,
commands, agents, hooks) and an MCP server. Standard library only, no API key.

## Layout

- `brain/` — Python package: `notes.py` (frontmatter/wikilinks), `index.py` (SQLite FTS5 index + ranking),
  `memory.py` (capture / remember / episodic log / sessions / consolidation packet), `lint.py`,
  `context.py` (session packets), `hooks.py` (Claude Code hook handlers), `mcp_server.py` (stdio JSON-RPC), `cli.py`.
- `bin/brain` — launcher; `python3 bin/brain --help`.
- `vault/` — the seed vault (Obsidian-compatible). `.brain.toml` points the tooling at it when run inside this repo.
  `vault/.brain/` is the index cache and is git-ignored.
- Plugin surface: `.claude-plugin/plugin.json`, `skills/*/SKILL.md`, `commands/*.md`, `agents/*.md`,
  `hooks/hooks.json`, `.mcp.json`. `.claude-plugin/marketplace.json` lets users install from this repo.
- `tests/` — stdlib `unittest`.

## Commands

```bash
python3 -m unittest discover -s tests -t .      # run tests (no deps)
claude plugin validate . --strict                # validate plugin + marketplace manifests
claude --plugin-dir . -p "/brain:status"         # try the plugin without installing
python3 bin/brain doctor                         # environment check
python3 bin/brain lint                           # vault health
```

## Conventions

- Python ≥ 3.8 compatible, standard library only — do not add dependencies.
- Deterministic parts (indexing, ranking, lint, logging) live in Python; judgement lives in skills/agents.
- Hooks must never fail a session: catch everything, print nothing, exit 0 on error.
- Never edit `vault/raw/` or rewrite episodic logs; archive/supersede instead of deleting notes.
- Keep the seed vault lint-clean (`python3 bin/brain lint` shows no `error`). `vault/memory/episodic/`
  and `vault/.brain/` are git-ignored: the hooks write there whenever someone opens this repo.
- Commit messages: imperative mood, explain *why* in the body when it is not obvious.

## When working in this repo

Use the brain itself: recall before changing architecture (`python3 bin/brain recall "<question>"`),
and record decisions with `python3 bin/brain remember "Decision - …" "…" --type decision`.

Opening this repo in Claude Code gives you the brain MCP server (`.mcp.json`) and the memory hooks
(`.claude/settings.json`) without installing the plugin. Slash commands (`/brain:…`) and the agents
only exist when the plugin is loaded: `claude --plugin-dir .` or install from the marketplace.
The core skill is imported below so the usage rules apply either way.

@skills/brain/SKILL.md
