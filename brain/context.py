"""Context packets: what the brain tells Claude at session start and per prompt.

Everything is trimmed to a character budget so the brain never floods the
model's context window.  ~4 characters ≈ 1 token.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Sequence

from .config import Config
from .index import Hit, Index
from .memory import recent_episodes


def _trim(lines: List[str], budget: int) -> str:
    out: List[str] = []
    used = 0
    for line in lines:
        if used + len(line) + 1 > budget:
            if out and not out[-1].endswith("…"):
                out.append("…")
            break
        out.append(line)
        used += len(line) + 1
    return "\n".join(out).rstrip()


def project_notes(index: Index, cwd: str, k: int = 4) -> List[Hit]:
    """Entity/wiki notes that mention the current project (directory name)."""
    if not cwd:
        return []
    name = Path(cwd).name
    if not name or len(name) < 3:
        return []
    terms = [name] + [t for t in re.split(r"[-_. ]+", name) if len(t) >= 3]
    hits = index.search(" ".join(dict.fromkeys(terms)), k=k * 2, types=["entity", "wiki", "procedure", "decision", "preference", "fact"])
    name_l = name.lower()
    strong = [h for h in hits if name_l in h.title.lower() or name_l in h.snippet.lower() or name_l in " ".join(h.tags).lower()]
    return (strong or hits)[:k]


def build_context(config: Config, index: Index, cwd: str = "", budget: int = 0) -> str:
    """Session-start packet: identity line, project notes, pinned/core memory, recent episodes."""
    budget = budget or int(config.get("context_budget", 2400))
    index.refresh()
    stats = index.stats()
    lines: List[str] = []
    lines.append(
        f"[brain] vault={config.vault} · {stats['notes']} notes · "
        "tools: `brain search <q>` / `brain read <note>` / `brain remember` / `brain capture` (CLI) "
        "or the brain MCP tools; skills: /brain:recall, /brain:remember, /brain:review."
    )

    proj = project_notes(index, cwd)
    if proj:
        lines.append("")
        lines.append(f"## About this project ({Path(cwd).name})")
        for h in proj:
            lines.append(f"- {h.title} ({h.rel}) — {h.summary or h.snippet}")

    shown = {h.rel for h in proj}
    core_rows = [
        r
        for r in index.notes(types=["preference", "procedure", "entity", "fact", "decision"], status="active", limit=60)
        if (int(r["importance"]) >= 8 or "pinned" in (r["tags"] or "").split()) and r["rel"] not in shown
    ]
    if core_rows:
        lines.append("")
        lines.append("## Core memory (importance ≥ 8 or #pinned)")
        for r in core_rows[:10]:
            lines.append(f"- [{r['type']}] {r['title']} — {r['summary']}")

    eps = recent_episodes(config, days=2, max_lines=6)
    if eps:
        lines.append("")
        lines.append("## Recent activity")
        lines.extend(f"- {e}" for e in eps)

    inbox = index.notes(types=["inbox"], limit=50)
    if inbox:
        lines.append("")
        lines.append(f"Inbox: {len(inbox)} unprocessed item(s) — offer to run /brain:review when convenient.")

    return _trim(lines, budget)


def format_recall(hits: Sequence[Hit], budget: int = 1200, header: str = "[brain recall] notes relevant to this prompt:") -> str:
    if not hits:
        return ""
    lines = [header]
    for h in hits:
        desc = h.summary or h.snippet
        lines.append(f"- {h.title} ({h.rel}; {h.type}, importance {h.importance}, updated {h.updated or '?'}) — {desc}")
    lines.append("Use `brain read <path>` (or the brain_read tool) for the full note before relying on it.")
    return _trim(lines, budget)


def format_hits(hits: Sequence[Hit], show_snippets: bool = True) -> str:
    if not hits:
        return "(no results)"
    out = []
    for i, h in enumerate(hits, 1):
        out.append(f"{i}. {h.title}  [{h.type} · imp {h.importance} · {h.status} · {h.updated or '?'} · score {h.score}]")
        out.append(f"   {h.rel}")
        if show_snippets and (h.snippet or h.summary):
            out.append(f"   {h.snippet or h.summary}")
    return "\n".join(out)
