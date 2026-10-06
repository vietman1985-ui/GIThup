"""SQLite + FTS5 index over the vault.

The index is a disposable cache (``<vault>/.brain/index.sqlite``): it can be
deleted at any time and is rebuilt incrementally from the Markdown files.

Ranking = BM25 (from FTS5) × importance boost × recency boost × status
penalty, so the brain surfaces what matters now, not just what matches.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import math
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .config import Config
from .notes import Note, iter_note_paths, load_note

SCHEMA_VERSION = 3

SCHEMA = f"""
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS notes (
    rel TEXT PRIMARY KEY,
    stem TEXT NOT NULL,
    title TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    importance INTEGER NOT NULL,
    confidence REAL NOT NULL,
    created TEXT,
    updated TEXT,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    hash TEXT NOT NULL,
    summary TEXT NOT NULL,
    tags TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS notes_type ON notes(type);
CREATE INDEX IF NOT EXISTS notes_stem ON notes(stem);
CREATE TABLE IF NOT EXISTS links (
    src TEXT NOT NULL,
    target TEXT NOT NULL,
    dst TEXT,
    PRIMARY KEY (src, target)
);
CREATE INDEX IF NOT EXISTS links_dst ON links(dst);
CREATE TABLE IF NOT EXISTS tags (
    rel TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (rel, tag)
);
CREATE INDEX IF NOT EXISTS tags_tag ON tags(tag);
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    rel UNINDEXED,
    title,
    tags,
    body,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


@dataclass
class Hit:
    rel: str
    title: str
    type: str
    status: str
    importance: int
    updated: str
    score: float
    snippet: str
    summary: str
    tags: List[str]


def _hash(text: bytes) -> str:
    return hashlib.sha1(text).hexdigest()


def _days_since(date_str: str) -> Optional[float]:
    if not date_str:
        return None
    try:
        d = _dt.date.fromisoformat(str(date_str)[:10])
    except ValueError:
        return None
    return max(0.0, (_dt.date.today() - d).days)


class Index:
    def __init__(self, config: Config):
        self.config = config
        self.vault = config.vault
        self.config.index_dir.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(config.index_path))
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    # ------------------------------------------------------------------ setup
    def _ensure_schema(self) -> None:
        cur = self.conn.cursor()
        try:
            row = cur.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
        except sqlite3.OperationalError:
            row = None
        if row is not None and int(row["value"]) != SCHEMA_VERSION:
            # schema changed: wipe and rebuild lazily
            for table in ("notes_fts", "notes", "links", "tags", "meta"):
                cur.execute(f"DROP TABLE IF EXISTS {table}")
            self.conn.commit()
        cur.executescript(SCHEMA)
        cur.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('schema', ?)", (str(SCHEMA_VERSION),))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Index":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --------------------------------------------------------------- indexing
    def refresh(self, full: bool = False) -> Dict[str, int]:
        """Incrementally (re)index changed files.  Returns counters."""
        cur = self.conn.cursor()
        known: Dict[str, Tuple[float, int, str]] = {
            r["rel"]: (r["mtime"], r["size"], r["hash"])
            for r in cur.execute("SELECT rel, mtime, size, hash FROM notes")
        }
        seen = set()
        added = updated = unchanged = 0
        for path in iter_note_paths(self.vault):
            rel = path.relative_to(self.vault).as_posix()
            seen.add(rel)
            try:
                st = path.stat()
            except OSError:
                continue
            prev = known.get(rel)
            if prev is not None and not full and abs(prev[0] - st.st_mtime) < 1e-6 and prev[1] == st.st_size:
                unchanged += 1
                continue
            raw = path.read_bytes()
            digest = _hash(raw)
            if prev is not None and prev[2] == digest and not full:
                cur.execute("UPDATE notes SET mtime=?, size=? WHERE rel=?", (st.st_mtime, st.st_size, rel))
                unchanged += 1
                continue
            note = load_note(self.vault, path)
            self._upsert(cur, note, st.st_mtime, st.st_size, digest)
            if prev is None:
                added += 1
            else:
                updated += 1
        removed = 0
        for rel in set(known) - seen:
            self._delete(cur, rel)
            removed += 1
        # resolve link targets to actual notes (by stem or by rel path)
        self._resolve_links(cur)
        self.conn.commit()
        return {"added": added, "updated": updated, "removed": removed, "unchanged": unchanged}

    def _upsert(self, cur: sqlite3.Cursor, note: Note, mtime: float, size: int, digest: str) -> None:
        self._delete(cur, note.rel)
        cur.execute(
            """INSERT INTO notes(rel, stem, title, type, status, importance, confidence, created, updated,
                                 mtime, size, hash, summary, tags)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                note.rel,
                note.stem,
                note.title,
                note.type,
                note.status,
                note.importance,
                note.confidence,
                note.created,
                note.updated,
                mtime,
                size,
                digest,
                note.summary(),
                " ".join(note.tags),
            ),
        )
        cur.execute(
            "INSERT INTO notes_fts(rel, title, tags, body) VALUES(?,?,?,?)",
            (note.rel, note.title, " ".join(note.tags), note.body),
        )
        for target in note.links:
            cur.execute("INSERT OR IGNORE INTO links(src, target, dst) VALUES(?,?,NULL)", (note.rel, target))
        for tag in note.tags:
            cur.execute("INSERT OR IGNORE INTO tags(rel, tag) VALUES(?,?)", (note.rel, tag.lower()))

    def _delete(self, cur: sqlite3.Cursor, rel: str) -> None:
        cur.execute("DELETE FROM notes WHERE rel=?", (rel,))
        cur.execute("DELETE FROM notes_fts WHERE rel=?", (rel,))
        cur.execute("DELETE FROM links WHERE src=?", (rel,))
        cur.execute("DELETE FROM tags WHERE rel=?", (rel,))

    def _resolve_links(self, cur: sqlite3.Cursor) -> None:
        by_stem: Dict[str, str] = {}
        by_rel: Dict[str, str] = {}
        for r in cur.execute("SELECT rel, stem FROM notes"):
            by_rel[r["rel"].lower()] = r["rel"]
            by_rel[r["rel"][:-3].lower()] = r["rel"]  # without .md
            # last writer wins on duplicate stems; lint reports duplicates
            by_stem.setdefault(r["stem"].lower(), r["rel"])
        rows = cur.execute("SELECT src, target FROM links").fetchall()
        for r in rows:
            target = r["target"].strip()
            key = target.lower()
            dst = by_rel.get(key) or by_rel.get(key + ".md") or by_stem.get(key.rsplit("/", 1)[-1])
            cur.execute("UPDATE links SET dst=? WHERE src=? AND target=?", (dst, r["src"], r["target"]))

    # ----------------------------------------------------------------- search
    @staticmethod
    def build_fts_query(query: str) -> str:
        """Turn free text into a safe FTS5 query: OR of quoted (prefix) tokens."""
        tokens = [t for t in re.findall(r"\w+", query, flags=re.UNICODE) if t]
        if not tokens:
            return ""
        parts = []
        for t in tokens[:24]:
            t = t.replace('"', "")
            if len(t) >= 3:
                parts.append(f'"{t}"*')
            else:
                parts.append(f'"{t}"')
        return " OR ".join(parts)

    def search(
        self,
        query: str,
        k: int = 8,
        types: Optional[Sequence[str]] = None,
        include_archived: bool = False,
        tag: Optional[str] = None,
    ) -> List[Hit]:
        fts = self.build_fts_query(query)
        if not fts:
            return []
        half_life = float(self.config.get("recency_half_life_days", 30)) or 30.0
        sql = """
            SELECT n.rel, n.title, n.type, n.status, n.importance, n.updated, n.summary, n.tags,
                   bm25(notes_fts, 4.0, 2.0, 1.0) AS rank,
                   snippet(notes_fts, 3, '[', ']', '…', 18) AS snip
            FROM notes_fts JOIN notes n ON n.rel = notes_fts.rel
            WHERE notes_fts MATCH ?
        """
        params: List[object] = [fts]
        if types:
            sql += " AND n.type IN (%s)" % ",".join("?" * len(types))
            params.extend(types)
        sql += " AND n.type != 'template'"
        if not include_archived:
            sql += " AND n.status != 'archived'"
        if tag:
            sql += " AND EXISTS (SELECT 1 FROM tags t WHERE t.rel = n.rel AND t.tag = ?)"
            params.append(tag.lower().lstrip("#"))
        sql += " ORDER BY rank LIMIT ?"
        params.append(max(k * 4, 20))
        hits: List[Hit] = []
        for r in self.conn.execute(sql, params):
            base = -float(r["rank"])  # bm25() is negative; higher is better after negation
            if base <= 0:
                base = 0.01
            importance_boost = 1.0 + 0.08 * (int(r["importance"]) - 5)
            days = _days_since(r["updated"])
            recency_boost = 1.0 + (0.5 * math.exp(-math.log(2) * days / half_life) if days is not None else 0.0)
            status_penalty = {"active": 1.0, "draft": 0.9, "superseded": 0.5, "archived": 0.3}.get(r["status"], 1.0)
            type_weight = {"episode": 0.75, "raw": 0.7, "inbox": 0.85, "template": 0.2}.get(r["type"], 1.0)
            score = base * importance_boost * recency_boost * status_penalty * type_weight
            hits.append(
                Hit(
                    rel=r["rel"],
                    title=r["title"],
                    type=r["type"],
                    status=r["status"],
                    importance=int(r["importance"]),
                    updated=r["updated"] or "",
                    score=round(score, 3),
                    snippet=re.sub(r"\s+", " ", r["snip"] or "").strip(),
                    summary=r["summary"] or "",
                    tags=[t for t in (r["tags"] or "").split() if t],
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    # ------------------------------------------------------------------ graph
    def related(self, rel: str, k: int = 8) -> List[Tuple[str, str, float]]:
        """Neighbours by wikilinks (both directions) and shared tags.

        Returns ``[(rel, reason, weight)]`` sorted by weight.
        """
        scores: Dict[str, float] = {}
        reasons: Dict[str, str] = {}
        for r in self.conn.execute("SELECT dst FROM links WHERE src=? AND dst IS NOT NULL", (rel,)):
            scores[r["dst"]] = scores.get(r["dst"], 0) + 3.0
            reasons.setdefault(r["dst"], "links to")
        for r in self.conn.execute("SELECT src FROM links WHERE dst=?", (rel,)):
            scores[r["src"]] = scores.get(r["src"], 0) + 2.0
            reasons.setdefault(r["src"], "linked from")
        tags = [r["tag"] for r in self.conn.execute("SELECT tag FROM tags WHERE rel=?", (rel,))]
        for tag in tags:
            for r in self.conn.execute("SELECT rel FROM tags WHERE tag=? AND rel != ?", (tag, rel)):
                scores[r["rel"]] = scores.get(r["rel"], 0) + 1.0
                reasons.setdefault(r["rel"], f"shares #{tag}")
        scores.pop(rel, None)
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:k]
        return [(r, reasons[r], w) for r, w in ranked]

    def backlinks(self, rel: str) -> List[str]:
        return [r["src"] for r in self.conn.execute("SELECT src FROM links WHERE dst=? ORDER BY src", (rel,))]

    def broken_links(self) -> List[Tuple[str, str]]:
        return [
            (r["src"], r["target"])
            for r in self.conn.execute(
                """SELECT l.src, l.target FROM links l JOIN notes n ON n.rel = l.src
                   WHERE l.dst IS NULL AND n.type != 'template' ORDER BY l.src, l.target"""
            )
        ]

    def orphans(self, exclude_types: Sequence[str] = ("episode", "template", "raw", "moc", "inbox")) -> List[str]:
        sql = """
            SELECT n.rel FROM notes n
            WHERE n.type NOT IN (%s)
              AND NOT EXISTS (SELECT 1 FROM links l WHERE l.dst = n.rel)
              AND NOT EXISTS (SELECT 1 FROM links l WHERE l.src = n.rel AND l.dst IS NOT NULL)
            ORDER BY n.rel
        """ % ",".join("?" * len(exclude_types))
        return [r["rel"] for r in self.conn.execute(sql, list(exclude_types))]

    # ------------------------------------------------------------------ stats
    def notes(
        self,
        types: Optional[Sequence[str]] = None,
        status: Optional[str] = None,
        order: str = "importance DESC, updated DESC",
        limit: int = 1000,
    ) -> List[sqlite3.Row]:
        sql = "SELECT * FROM notes WHERE 1=1"
        params: List[object] = []
        if types:
            sql += " AND type IN (%s)" % ",".join("?" * len(types))
            params.extend(types)
        if status:
            sql += " AND status = ?"
            params.append(status)
        allowed_orders = {
            "importance DESC, updated DESC",
            "updated DESC",
            "created DESC",
            "rel",
            "title",
        }
        if order not in allowed_orders:
            order = "importance DESC, updated DESC"
        sql += f" ORDER BY {order} LIMIT ?"
        params.append(limit)
        return self.conn.execute(sql, params).fetchall()

    def get(self, rel: str) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM notes WHERE rel=?", (rel,)).fetchone()

    def find_by_stem(self, stem: str) -> List[str]:
        return [r["rel"] for r in self.conn.execute("SELECT rel FROM notes WHERE lower(stem)=lower(?)", (stem,))]

    def duplicate_titles(self) -> List[Tuple[str, List[str]]]:
        rows = self.conn.execute(
            """SELECT lower(title) AS t, group_concat(rel, '|') AS rels, count(*) AS c
               FROM notes WHERE type NOT IN ('episode','template') GROUP BY lower(title) HAVING c > 1 ORDER BY t"""
        ).fetchall()
        return [(r["t"], r["rels"].split("|")) for r in rows]

    def stats(self) -> Dict[str, object]:
        by_type = {
            r["type"]: r["c"] for r in self.conn.execute("SELECT type, count(*) AS c FROM notes GROUP BY type ORDER BY type")
        }
        total = sum(by_type.values())
        links = self.conn.execute("SELECT count(*) AS c FROM links WHERE dst IS NOT NULL").fetchone()["c"]
        broken = len(self.broken_links())
        tags = self.conn.execute("SELECT count(DISTINCT tag) AS c FROM tags").fetchone()["c"]
        return {
            "vault": str(self.vault),
            "notes": total,
            "by_type": by_type,
            "links": links,
            "broken_links": broken,
            "tags": tags,
            "index": str(self.config.index_path),
        }
