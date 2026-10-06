"""Vault health checks.

Everything here is deterministic.  Judgement calls (is this fact still true?
do these two notes contradict?) are left to the ``brain-critic`` agent, which
reads this report as its starting point.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, asdict
from typing import Dict, List

from .config import Config
from .index import Index


@dataclass
class Issue:
    level: str  # error | warn | info
    code: str
    rel: str
    message: str
    hint: str = ""

    def as_dict(self) -> Dict[str, str]:
        return asdict(self)


def _days_since(date_str: str) -> float:
    try:
        return float((_dt.date.today() - _dt.date.fromisoformat(str(date_str)[:10])).days)
    except (TypeError, ValueError):
        return 0.0


def run_lint(config: Config, index: Index) -> List[Issue]:
    issues: List[Issue] = []

    for src, target in index.broken_links():
        issues.append(
            Issue("error", "broken-link", src, f"[[{target}]] does not resolve to a note",
                  "Create the note, fix the spelling, or remove the link.")
        )

    for rel in index.orphans():
        issues.append(
            Issue("warn", "orphan", rel, "no inbound or outbound links",
                  "Link it from a wiki/MOC page or from a related note so it can be found by browsing.")
        )

    for title, rels in index.duplicate_titles():
        issues.append(
            Issue("warn", "duplicate-title", rels[0], f"title '{title}' used by {len(rels)} notes: {', '.join(rels)}",
                  "Merge them, or mark the older one status: superseded with superseded_by.")
        )

    stale_after = float(config.get("stale_after_days", 180))
    for row in index.notes(types=["fact", "entity", "decision", "preference", "procedure", "wiki"], status="active"):
        rel = row["rel"]
        if not row["created"]:
            issues.append(Issue("warn", "missing-created", rel, "frontmatter has no created date",
                                "Add `created: YYYY-MM-DD` so recency ranking works."))
        age = _days_since(row["updated"] or row["created"])
        if row["updated"] and age > stale_after and int(row["importance"]) >= 6:
            issues.append(Issue("info", "stale", rel, f"important note not updated for {int(age)} days",
                                "Re-verify it; bump `updated` or set status: archived."))
        if float(row["confidence"]) < 0.5:
            issues.append(Issue("info", "low-confidence", rel, f"confidence {row['confidence']:.2f} but status active",
                                "Find a source and raise confidence, or mark it draft."))

    for row in index.notes(status="superseded"):
        rel = row["rel"]
        note_row = index.get(rel)
        if note_row is not None:
            # look for a superseded_by link in the outgoing links table
            has_successor = index.conn.execute(
                "SELECT 1 FROM links WHERE src=? AND dst IS NOT NULL LIMIT 1", (rel,)
            ).fetchone()
            if not has_successor:
                issues.append(Issue("warn", "superseded-without-successor", rel,
                                    "status is superseded but no [[link]] points to the replacement",
                                    "Add `superseded_by: \"[[New note]]\"` or a link in the body."))

    inbox = index.notes(types=["inbox"])
    if inbox:
        issues.append(Issue("info", "inbox-backlog", "inbox/", f"{len(inbox)} item(s) waiting to be processed",
                            "Run /brain:review (or the brain-consolidator agent) to file them."))

    raw_rows = index.notes(types=["raw"])
    for row in raw_rows:
        if not index.backlinks(row["rel"]):
            issues.append(Issue("info", "raw-uncompiled", row["rel"], "source has not been cited by any wiki/memory note",
                                "Run /brain:compile on it so its knowledge enters the wiki."))

    order = {"error": 0, "warn": 1, "info": 2}
    issues.sort(key=lambda i: (order.get(i.level, 9), i.code, i.rel))
    return issues


def format_issues(issues: List[Issue]) -> str:
    if not issues:
        return "OK — no issues found."
    lines = []
    counts: Dict[str, int] = {}
    for i in issues:
        counts[i.level] = counts.get(i.level, 0) + 1
        lines.append(f"[{i.level}] {i.code}: {i.rel} — {i.message}")
        if i.hint:
            lines.append(f"    ↳ {i.hint}")
    head = ", ".join(f"{n} {lvl}" for lvl, n in sorted(counts.items(), key=lambda kv: {'error': 0, 'warn': 1, 'info': 2}.get(kv[0], 9)))
    return f"{head}\n" + "\n".join(lines)
